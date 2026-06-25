"""
Main TorrentContentDetector orchestrator.

This module provides the main interface for identifying torrent content,
coordinating between multiple parsers, preprocessing, file structure analysis,
and TMDB validation.

Hierarchical Media Type Detection:
Media type is determined using a hierarchical approach with confidence-based fallback:
1. Torrent name patterns (definitive indicators like S01E01 = TV episode)
2. File structure analysis (folder patterns, file sizes, video count)
3. TMDB dual-type checking (when uncertain, checks both movie and TV, picks best match)

The system uses the most confident source at each level, with name patterns taking
precedence for definitive indicators (confidence >= 0.95), and file structure being
preferred when it has high confidence (>= 0.7) and name patterns are not definitive.

Title Selection:
When TMDB validation succeeds, the TMDB-returned title is used as the authoritative
title. TMDB titles are considered canonical (e.g., "The Dark Knight" instead of
"Batman The Dark Knight" from parser consensus). When TMDB validation fails, the
parser consensus title is used instead.

Confidence Scoring:
The confidence score represents "how sure we are that the detected title is correct,"
based ENTIRELY on weighted parser consensus. Parsers are assigned trust weights
(e.g., GuessIt=1.0, PTN=0.8, Regex=0.2), and confidence is calculated from how many
parsers agreed on the same title, weighted by their trust levels.

Parser-provided confidence values are INTENTIONALLY IGNORED. Only parser agreement
on the title matters for the final confidence score.

Automatic LLM Fallback:
When the consensus confidence is LOW or VERY_LOW, the system automatically invokes
the LLM parser (if available) as a fallback. The LLM parser's output is used directly,
replacing the low-confidence consensus result. The LLM result is validated with TMDB
if possible, and assigned MEDIUM confidence. This ensures difficult or ambiguous cases
get a second chance at accurate parsing.
"""

import os
from typing import Optional, List, Tuple, Dict, Any, Union
from concurrent.futures import ThreadPoolExecutor, as_completed

from .models import (
    MediaType, ConfidenceLevel, ParseResult, TorrentContent,
    MediaIdentification, DatasetSample
)
from .preprocessor import PreProcessor
from .file_structure_detector import FileStructureDetector
from .episode_extractor import EpisodeExtractor
from .parsers import create_parser_pipeline
from .tmdb_validator import create_tmdb_validator
from .tmdb_enricher import create_tmdb_enricher
from .verbose import vprint
from .title_confidence import build_title_and_confidence


class TorrentContentDetector:
    """
    Main orchestrator for torrent content detection.

    This class coordinates the entire detection pipeline:
    1. Pre-processes torrent names and file structures
    2. Runs multiple parsers using consensus-based voting
    3. Automatically invokes LLM parser for low-confidence results
    4. Validates results against TMDB
    5. Returns the best possible identification

    Features:
    - Multi-parser consensus with weighted voting
    - Automatic LLM fallback for low confidence
    - Configurable parser selection
    - TMDB validation and enrichment
    - Episode extraction for TV content
    """

    def __init__(
        self,
        tmdb_api_key: str = None,
        llm_api_key: str = None,
        llm_api_endpoint: str = None,
        llm_model: str = None,
        cache_db_path: str = "/tmp/torrent_interpret.db",
        use_llm_fallback: bool = False,
        enable_caching: bool = True,
        enable_enricher: bool = False,
        enricher_cache_path: str = "/tmp/torrent_match/tmdb.sqlite",
        enricher_use_local_cache: bool = True,
        enricher_min_popularity: float = 10.0,
        parsers: Optional[List[str]] = None
    ):
        """
        Initialize the torrent content detector.

        Args:
            tmdb_api_key: TMDB API key for validation and IMDB lookup
            llm_api_key: LLM API key for LLM fallback parser (OpenRouter or OpenAI)
            llm_api_endpoint: LLM API endpoint (OpenRouter or OpenAI)
            llm_model: LLM model to use
            cache_db_path: Path to redislite database file for caching
            use_llm_fallback: Whether to use LLM parser as last resort
            enable_caching: Whether to enable caching
            enable_enricher: Whether to enable TMDB enricher for additional media info (default: False)
            enricher_cache_path: Path to SQLite cache for enricher
            enricher_use_local_cache: Whether enricher should use local cache
            enricher_min_popularity: Minimum popularity threshold for enricher cache
            parsers: Optional list of parser names to use (e.g., ['guessit', 'ptn', 'llm']).
                    Valid names: 'guessit', 'ptn', 'rebulk', 'regex', 'llm'.
                    If None, uses all available parsers.
        """
        self.preprocessor = PreProcessor()
        self.file_structure_detector = FileStructureDetector()
        self.episode_extractor = EpisodeExtractor()

        # Initialize TMDB validator if API key provided
        self.tmdb_validator = None
        if tmdb_api_key:
            try:
                self.tmdb_validator = create_tmdb_validator(
                    tmdb_api_key,
                    cache_db_path if enable_caching else None
                )
            except Exception as e:
                vprint(f"Warning: Failed to initialize TMDB validator: {e}")

        # Initialize TMDB enricher if enabled
        self.tmdb_enricher = None
        if enable_enricher:
            if not tmdb_api_key:
                vprint("Warning: TMDB enricher requires tmdb_api_key, enricher disabled")
            else:
                try:
                    self.tmdb_enricher = create_tmdb_enricher(
                        api_key=tmdb_api_key,
                        cache_db_path=enricher_cache_path,
                        use_local_cache=enricher_use_local_cache,
                        min_popularity=enricher_min_popularity
                    )
                    vprint(f"TMDB enricher initialized with local cache: {enricher_use_local_cache}")
                except Exception as e:
                    vprint(f"Warning: Failed to initialize TMDB enricher: {e}")

        # Initialize parser pipeline
        self.parsers = create_parser_pipeline(
            include_llm=use_llm_fallback,
            llm_api_key=llm_api_key,
            llm_api_endpoint=llm_api_endpoint,
            llm_model=llm_model,
            parser_names=parsers
        )

        if not self.parsers:
            raise RuntimeError("No parsers available. Please install at least one parsing library.")

        vprint(f"Initialized detector with {len(self.parsers)} parsers: {[p.__class__.__name__ for p in self.parsers]}")

    def identify(
        self,
        torrent_name: str,
        files: Optional[Union[List[str], List[Dict[str, Any]]]] = None
    ) -> MediaIdentification:
        """
        Identify content from torrent name and optional file list.

        Args:
            torrent_name: The torrent name to analyze
            files: Optional list of file paths (strings) or file info dicts.
                   If dicts, should have 'path' and 'length' keys for file structure analysis.

        Returns:
            MediaIdentification with the best possible identification
        """
        # Pre-process
        normalized_name = self.preprocessor.normalize_name(torrent_name)

        # Initialize episode list (for TV content)
        episode_list = None
        episode_summary = None

        # HIERARCHICAL MEDIA TYPE DETECTION
        # Step 1: Check torrent name patterns for definitive indicators
        name_media_type, name_confidence = self.preprocessor.detect_media_type_from_name(torrent_name)
        vprint(f"Name-based detection: {name_media_type.value if name_media_type else 'None'} (confidence: {name_confidence:.2f})")

        # Step 2: Analyze file structure if provided
        file_media_type = None
        file_confidence = 0.0

        if files:
            # Convert files to list of paths for preprocessor
            if files and isinstance(files[0], dict):
                file_paths = [f.get('path', f.get('name', '')) for f in files]
            else:
                file_paths = files

            content = self.preprocessor.analyze_file_structure(file_paths, torrent_name)
            content.normalized_name = normalized_name

            # Use FileStructureDetector if we have file size information
            if files and isinstance(files[0], dict) and ('length' in files[0] or 'size' in files[0]):
                # Normalize 'size' to 'length' for consistency
                normalized_files = []
                for f in files:
                    file_dict = dict(f)  # Copy
                    if 'size' in file_dict and 'length' not in file_dict:
                        file_dict['length'] = file_dict['size']
                    normalized_files.append(file_dict)

                file_media_type, file_confidence = self.file_structure_detector.detect_media_type_with_confidence(normalized_files, torrent_name)
                vprint(f"File structure detection: {file_media_type.value if file_media_type else 'None'} (confidence: {file_confidence:.2f})")

                # HIERARCHICAL DECISION: Choose best media type based on confidence
                if name_confidence >= 0.95:
                    # Name patterns are definitive (e.g., S01E01)
                    content.media_type = name_media_type
                    vprint(f"Using name-based type (definitive): {name_media_type.value}")
                elif file_confidence >= 0.7:
                    # File structure is confident and name is not definitive
                    content.media_type = file_media_type
                    vprint(f"Using file structure type (confident): {file_media_type.value}")
                elif name_confidence > file_confidence:
                    # Name has higher confidence than file structure
                    content.media_type = name_media_type if name_media_type else file_media_type
                    vprint(f"Using name-based type (higher confidence): {content.media_type.value if content.media_type else 'None'}")
                else:
                    # File structure has equal or higher confidence
                    content.media_type = file_media_type
                    vprint(f"Using file structure type: {file_media_type.value if file_media_type else 'None'}")

                # Extract episodes for TV content (only when we have file size info)
                if content.media_type in [MediaType.TV_SEASON, MediaType.TV_MULTI_SEASON, MediaType.TV_EPISODE]:
                    episode_list = self.episode_extractor.extract_episodes(normalized_files)
                    episode_summary = self.episode_extractor.get_episode_count_summary(normalized_files)
                    vprint(f"Extracted {len(episode_list)} episodes across {episode_summary['season_count']} season(s)")
            else:
                # No file size info, use name-based detection if available
                if name_media_type:
                    content.media_type = name_media_type
                    vprint(f"Using name-based type (no file sizes): {name_media_type.value}")
        else:
            # No files provided, use name-based detection if available
            media_type = name_media_type if name_media_type else MediaType.UNKNOWN
            content = TorrentContent(
                torrent_name=torrent_name,
                files=[],
                folder_structure={},
                media_type=media_type,
                movie_file_count=0,
                has_season_folders=False,
                normalized_name=normalized_name
            )
            if name_media_type:
                vprint(f"Using name-based type (no files provided): {name_media_type.value}")

        # Run ALL non-LLM parsers to gather consensus
        all_parse_results = []
        all_tmdb_matches = []

        for parser in self.parsers:
            # Skip LLM parser - we only want non-LLM methods
            if parser.__class__.__name__ == 'LLMParser':
                continue

            parse_result = parser.parse(torrent_name, content)

            if parse_result:
                all_parse_results.append(parse_result)

                # Validate with TMDB if available
                if self.tmdb_validator:
                    is_valid, identification = self.tmdb_validator.validate_and_enrich(parse_result)

                    if is_valid and identification:
                        all_tmdb_matches.append(identification)

        # Calculate consensus-based confidence and select best result
        result = None
        if all_tmdb_matches:
            result = self._select_best_with_consensus(all_tmdb_matches, all_parse_results)
        elif all_parse_results:
            # No TMDB matches, use parser consensus only
            result = self._create_consensus_identification(all_parse_results)
        else:
            # Complete failure
            result = MediaIdentification(
                imdb_id=None,
                tmdb_id=None,
                title=normalized_name,
                year=None,
                media_type=content.media_type,
                season=None,
                episode=None,
                confidence=ConfidenceLevel.VERY_LOW,
                parser_used='None',
                tmdb_match=False,
                metadata={'error': 'All parsers failed'}
            )

        # Apply title-based confidence system
        # Use parser consensus for confidence scoring, but preserve TMDB title when matched
        if all_parse_results:
            final_title, title_confidence, confidence_level, title_metadata = build_title_and_confidence(all_parse_results)

            # Only override title if we don't have a TMDB match
            # TMDB titles are authoritative and should be preserved
            if not result.tmdb_match:
                result.title = final_title

            # Always use consensus-based confidence
            result.confidence = confidence_level

            # Store title confidence details in metadata
            if 'title_confidence' not in result.metadata:
                result.metadata['title_confidence'] = title_metadata
            else:
                result.metadata['title_confidence'].update(title_metadata)

            # AUTOMATIC LLM FALLBACK: If confidence is low, try LLM parser
            if confidence_level in [ConfidenceLevel.LOW, ConfidenceLevel.VERY_LOW]:
                vprint(f"Confidence is {confidence_level.name} ({title_confidence:.2f}), attempting LLM fallback...")

                # Find LLM parser in the pipeline
                llm_parser = None
                for parser in self.parsers:
                    if parser.__class__.__name__ == 'LLMParser':
                        llm_parser = parser
                        break

                if llm_parser:
                    try:
                        llm_result = llm_parser.parse(torrent_name, content)

                        if llm_result and llm_result.title:
                            vprint(f"LLM parser succeeded: {llm_result.title}")

                            # Use LLM result directly, but validate with TMDB if available
                            llm_identification = None
                            if self.tmdb_validator:
                                is_valid, llm_identification = self.tmdb_validator.validate_and_enrich(llm_result)

                                if is_valid and llm_identification:
                                    # Use TMDB-validated LLM result
                                    result = llm_identification
                                    result.parser_used = "LLM (fallback)"
                                    result.metadata['llm_fallback'] = True
                                    result.metadata['original_confidence'] = {
                                        'level': confidence_level.name,
                                        'score': title_confidence
                                    }
                                    vprint(f"Using TMDB-validated LLM result")
                                else:
                                    # Use LLM result without TMDB validation
                                    result = MediaIdentification(
                                        imdb_id=None,
                                        tmdb_id=None,
                                        title=llm_result.title,
                                        year=llm_result.year,
                                        media_type=llm_result.media_type,
                                        season=llm_result.season,
                                        episode=llm_result.episode,
                                        confidence=ConfidenceLevel.MEDIUM,  # Trust LLM moderately
                                        parser_used="LLM (fallback)",
                                        tmdb_match=False,
                                        metadata={
                                            'llm_fallback': True,
                                            'original_confidence': {
                                                'level': confidence_level.name,
                                                'score': title_confidence
                                            },
                                            'llm_raw_data': llm_result.raw_data
                                        }
                                    )
                                    vprint(f"Using LLM result without TMDB validation")
                            else:
                                # No TMDB validator, use LLM result directly
                                result = MediaIdentification(
                                    imdb_id=None,
                                    tmdb_id=None,
                                    title=llm_result.title,
                                    year=llm_result.year,
                                    media_type=llm_result.media_type,
                                    season=llm_result.season,
                                    episode=llm_result.episode,
                                    confidence=ConfidenceLevel.MEDIUM,  # Trust LLM moderately
                                    parser_used="LLM (fallback)",
                                    tmdb_match=False,
                                    metadata={
                                        'llm_fallback': True,
                                        'original_confidence': {
                                            'level': confidence_level.name,
                                            'score': title_confidence
                                        },
                                        'llm_raw_data': llm_result.raw_data
                                    }
                                )
                                vprint(f"Using LLM result (no TMDB validator)")
                        else:
                            vprint(f"LLM parser returned no result")
                    except Exception as e:
                        vprint(f"LLM fallback failed: {e}")
                else:
                    vprint(f"LLM parser not available in pipeline")

        # Add episode information to metadata if available
        if episode_list is not None and len(episode_list) > 0:
            result.metadata['episodes'] = episode_list
            result.metadata['episode_summary'] = episode_summary

        # Enrich with additional TMDB data if enricher is enabled
        if self.tmdb_enricher and result.title:
            try:
                result = self.tmdb_enricher.enrich(result)
            except Exception as e:
                vprint(f"Warning: Enrichment failed for {result.title}: {e}")

        return result

    def identify_from_sample(self, sample: DatasetSample) -> MediaIdentification:
        """
        Identify content from a DatasetSample.

        Args:
            sample: DatasetSample with torrent information

        Returns:
            MediaIdentification with the best possible identification
        """
        return self.identify(sample.name, sample.files)

    def identify_batch(
        self,
        torrents: List[Tuple[str, Optional[Union[List[str], List[Dict[str, Any]]]]]],
        max_workers: int = 5,
        show_progress: bool = True
    ) -> List[MediaIdentification]:
        """
        Process multiple torrents in parallel.

        Args:
            torrents: List of (torrent_name, files) tuples where files can be
                     list of paths (strings) or list of dicts with 'path' and 'length'
            max_workers: Maximum number of parallel workers
            show_progress: Whether to show progress

        Returns:
            List of MediaIdentification results
        """
        results = [None] * len(torrents)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_index = {
                executor.submit(self.identify, torrent[0], torrent[1]): i
                for i, torrent in enumerate(torrents)
            }

            # Collect results as they complete
            completed = 0
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    results[index] = future.result()
                    completed += 1

                    if show_progress and completed % 10 == 0:
                        vprint(f"Processed {completed}/{len(torrents)} torrents")

                except Exception as e:
                    vprint(f"Error processing torrent {index}: {e}")
                    torrent_name = torrents[index][0]
                    results[index] = MediaIdentification(
                        imdb_id=None,
                        tmdb_id=None,
                        title=torrent_name,
                        year=None,
                        media_type=MediaType.UNKNOWN,
                        season=None,
                        episode=None,
                        confidence=ConfidenceLevel.VERY_LOW,
                        parser_used='Error',
                        tmdb_match=False,
                        metadata={'error': str(e)}
                    )
                    completed += 1

        if show_progress:
            vprint(f"Completed processing {len(torrents)} torrents")

        return results

    def process_dataset_samples(
        self,
        samples: List[DatasetSample],
        max_workers: int = 5,
        show_progress: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Process samples from the torrent dataset.

        Args:
            samples: List of DatasetSample objects
            max_workers: Maximum number of parallel workers
            show_progress: Whether to show progress

        Returns:
            List of dictionaries with comparison data
        """
        # Prepare torrent data
        torrent_data = []
        for sample in samples:
            files = sample.get_file_paths()
            torrent_data.append((sample.name, files, sample))

        results = []

        if show_progress:
            vprint(f"Processing {len(torrent_data)} dataset samples...")

        # Process in smaller batches to manage memory
        batch_size = 100
        for i in range(0, len(torrent_data), batch_size):
            batch = torrent_data[i:i+batch_size]

            if show_progress:
                vprint(f"Processing batch {i//batch_size + 1}/{(len(torrent_data)-1)//batch_size + 1}")

            batch_results = self.identify_batch(
                [(name, files) for name, files, _ in batch],
                max_workers=max_workers,
                show_progress=False
            )

            # Combine results with original data
            for (name, files, sample), identification in zip(batch, batch_results):
                comparison = {
                    'sample_id': sample.sample_id,
                    'original_name': sample.name,
                    'original_imdb_id': sample.imdb_id,
                    'original_type': sample.type,
                    'detected_imdb_id': identification.imdb_id,
                    'detected_title': identification.title,
                    'detected_year': identification.year,
                    'detected_type': identification.media_type.value if hasattr(identification.media_type, 'value') else identification.media_type,
                    'season': identification.season,
                    'episode': identification.episode,
                    'confidence': identification.confidence_value,
                    'confidence_level': identification.confidence.name,
                    'tmdb_match': identification.tmdb_match,
                    'parser_used': identification.parser_used,
                    'metadata': identification.metadata
                }

                # Add comparison fields
                comparison['imdb_id_match'] = (
                    sample.imdb_id is not None and
                    identification.imdb_id is not None and
                    sample.imdb_id == identification.imdb_id
                )
                media_type_value = identification.media_type.value if hasattr(identification.media_type, 'value') else identification.media_type
                # Handle both old TV_SHOW and new TV_* types
                detected_type_clean = media_type_value.replace('_show', '').replace('_episode', '').replace('_season', '').replace('_multi_season', '')
                if detected_type_clean == 'tv':
                    detected_type_clean = 'tv'  # Keep tv as is
                comparison['type_match'] = sample.type == detected_type_clean

                # Add recovery status
                comparison['imdb_id_recovered'] = (
                    identification.imdb_id is not None and
                    identification.confidence_value >= 0.7
                )
                comparison['missing_imdb_filled'] = (
                    not sample.has_imdb_id() and
                    identification.imdb_id is not None and
                    identification.confidence_value >= 0.7
                )

                results.append(comparison)

        return results

    def recover_missing_imdb_ids(
        self,
        samples: List[DatasetSample],
        min_confidence: float = 0.7,
        max_workers: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Focus on recovering IMDB IDs for samples that don't have them.

        Args:
            samples: List of DatasetSample objects
            min_confidence: Minimum confidence level for recovered IDs
            max_workers: Maximum number of parallel workers

        Returns:
            List of successfully recovered IMDB IDs
        """
        # Filter samples without IMDB IDs
        missing_imdb_samples = [s for s in samples if not s.has_imdb_id()]
        vprint(f"Found {len(missing_imdb_samples)} samples without IMDB IDs")

        if not missing_imdb_samples:
            return []

        # Process samples
        results = self.process_dataset_samples(
            missing_imdb_samples,
            max_workers=max_workers
        )

        # Filter successful recoveries
        recovered = [
            result for result in results
            if result['missing_imdb_filled'] and result['confidence'] >= min_confidence
        ]

        vprint(f"Successfully recovered IMDB IDs for {len(recovered)} samples "
              f"({len(recovered)/len(missing_imdb_samples)*100:.1f}%)")

        return recovered

    def verify_content_types(
        self,
        samples: List[DatasetSample],
        min_confidence: float = 0.8,
        max_workers: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Verify and find discrepancies in content type classifications.

        Args:
            samples: List of DatasetSample objects
            min_confidence: Minimum confidence for type verification
            max_workers: Maximum number of parallel workers

        Returns:
            List of type discrepancies
        """
        # Process samples
        results = self.process_dataset_samples(
            samples,
            max_workers=max_workers
        )

        # Find type discrepancies
        discrepancies = []
        for result in results:
            if result['confidence'] >= min_confidence:
                detected_type = result['detected_type'].replace('_show', '').replace('_episode', '').replace('_season', '').replace('_multi_season', '')
                if detected_type == 'tv':
                    detected_type = 'tv'  # Keep tv as is
                if detected_type != result['original_type']:
                    discrepancies.append(result)

        vprint(f"Found {len(discrepancies)} type discrepancies with confidence >= {min_confidence}")
        return discrepancies

    def _select_best_with_consensus(
        self,
        tmdb_matches: List[MediaIdentification],
        parse_results: List[ParseResult]
    ) -> MediaIdentification:
        """
        Select the best TMDB match based on parser agreement.

        This method chooses which TMDB-validated result to use based on how many
        parsers agreed on the IMDB ID. It does NOT compute confidence - that is
        handled by the title consensus system in identify().

        Args:
            tmdb_matches: List of TMDB-validated identifications
            parse_results: List of all parser results

        Returns:
            Best MediaIdentification (confidence will be overwritten by identify())
        """
        if not tmdb_matches:
            return None

        # Count parser agreement for each unique IMDB ID
        imdb_agreement = {}
        for match in tmdb_matches:
            if match.imdb_id:
                if match.imdb_id not in imdb_agreement:
                    imdb_agreement[match.imdb_id] = {
                        'count': 0,
                        'identification': match,
                    }
                imdb_agreement[match.imdb_id]['count'] += 1

        # Select the IMDB ID with the most agreement
        best_match = None
        best_count = 0

        for imdb_id, data in imdb_agreement.items():
            if data['count'] > best_count:
                best_count = data['count']
                best_match = data['identification']

        if best_match:
            parser_names = [pr.parser_name for pr in parse_results]
            consensus_metadata = best_match.metadata.copy()
            consensus_metadata['consensus'] = {
                'parser_count': len(parse_results),
                'parsers_used': parser_names,
                'agreement_count': best_count,
                'agreement_ratio': best_count / len(parse_results),
            }

            # Return with placeholder confidence - will be overwritten by title consensus
            return MediaIdentification(
                imdb_id=best_match.imdb_id,
                tmdb_id=best_match.tmdb_id,
                title=best_match.title,
                year=best_match.year,
                media_type=best_match.media_type,
                season=best_match.season,
                episode=best_match.episode,
                confidence=ConfidenceLevel.MEDIUM,  # Placeholder - will be overwritten
                parser_used=f"Consensus({len(parser_names)})",
                tmdb_match=True,
                metadata=consensus_metadata
            )

        # Fallback to first match if no clear winner
        return tmdb_matches[0]

    def _create_consensus_identification(self, parse_results: List[ParseResult]) -> MediaIdentification:
        """
        Create identification from parser consensus without TMDB validation.

        This method determines the consensus values for year, media type, season,
        and episode based on parser agreement. Title and confidence are handled
        separately by the title consensus system in identify().

        Args:
            parse_results: List of parser results

        Returns:
            MediaIdentification based on parser consensus (title and confidence will be overwritten)
        """
        if not parse_results:
            return None

        # Find most common title (as placeholder - will be overwritten by title consensus)
        title_counts = {}
        for result in parse_results:
            if result.title:
                normalized_title = result.title.lower().strip()
                if normalized_title not in title_counts:
                    title_counts[normalized_title] = {'count': 0, 'original': result.title}
                title_counts[normalized_title]['count'] += 1

        # Select most agreed-upon title (placeholder only)
        best_title_data = max(title_counts.values(), key=lambda x: x['count'])
        consensus_title = best_title_data['original']

        # Find most common year
        years = []
        for r in parse_results:
            if r.year is not None:
                # Handle both single values and lists
                if isinstance(r.year, list):
                    years.extend(r.year)
                else:
                    years.append(r.year)
        consensus_year = max(set(years), key=years.count) if years else None

        # Find most common media type
        types = [r.media_type for r in parse_results]
        consensus_type = max(set(types), key=types.count) if types else MediaType.UNKNOWN

        # Find most common season/episode (for TV shows)
        # Handle both single values and lists
        seasons = []
        for r in parse_results:
            if r.season is not None:
                # Convert lists to tuples for hashability
                if isinstance(r.season, list):
                    seasons.append(tuple(r.season))
                else:
                    seasons.append(r.season)

        consensus_season = None
        if seasons:
            # Find most common season value
            most_common = max(set(seasons), key=seasons.count)
            # Convert back to list if it was originally a list
            consensus_season = list(most_common) if isinstance(most_common, tuple) else most_common

        episodes = []
        for r in parse_results:
            if r.episode is not None:
                # Convert lists to tuples for hashability
                if isinstance(r.episode, list):
                    episodes.append(tuple(r.episode))
                else:
                    episodes.append(r.episode)

        consensus_episode = None
        if episodes:
            # Find most common episode value
            most_common = max(set(episodes), key=episodes.count)
            # Convert back to list if it was originally a list
            consensus_episode = list(most_common) if isinstance(most_common, tuple) else most_common

        parser_names = [r.parser_name for r in parse_results]

        return MediaIdentification(
            imdb_id=None,
            tmdb_id=None,
            title=consensus_title,  # Placeholder - will be overwritten
            year=consensus_year,
            media_type=consensus_type,
            season=consensus_season,
            episode=consensus_episode,
            confidence=ConfidenceLevel.MEDIUM,  # Placeholder - will be overwritten
            parser_used=f"Consensus({len(parser_names)})",
            tmdb_match=False,
            metadata={
                'consensus': {
                    'parser_count': len(parse_results),
                    'parsers_used': parser_names,
                    'title_agreement': best_title_data['count'] / len(parse_results),
                },
                'parse_results': [
                    {
                        'parser': r.parser_name,
                        'title': r.title,
                        'year': r.year,
                    }
                    for r in parse_results
                ]
            }
        )

    def _create_fallback_identification(self, parse_result: ParseResult) -> MediaIdentification:
        """Create identification from parse result without TMDB validation"""
        confidence_map = {
            range(90, 101): ConfidenceLevel.HIGH,
            range(70, 90): ConfidenceLevel.MEDIUM,
            range(50, 70): ConfidenceLevel.LOW,
            range(0, 50): ConfidenceLevel.VERY_LOW,
        }

        confidence_level = ConfidenceLevel.VERY_LOW
        for range_obj, level in confidence_map.items():
            if int(parse_result.confidence * 100) in range_obj:
                confidence_level = level
                break

        return MediaIdentification(
            imdb_id=None,
            tmdb_id=None,
            title=parse_result.title or "Unknown",
            year=parse_result.year,
            media_type=parse_result.media_type,
            season=parse_result.season,
            episode=parse_result.episode,
            confidence=confidence_level,
            parser_used=parse_result.parser_name,
            tmdb_match=False,
            metadata=parse_result.raw_data
        )


class ParallelDetector(TorrentContentDetector):
    """
    Detector optimized for parallel batch processing.

    This subclass extends TorrentContentDetector with additional
    optimizations for processing large datasets efficiently.
    """

    def __init__(self, *args, **kwargs):
        # Extract max_workers from kwargs
        self.max_workers = kwargs.pop('max_workers', 10)
        super().__init__(*args, **kwargs)

    def identify_batch(self, torrents: List[Tuple[str, Optional[List[str]]]], **kwargs) -> List[MediaIdentification]:
        """Override to use instance's max_workers by default"""
        kwargs.setdefault('max_workers', self.max_workers)
        return super().identify_batch(torrents, **kwargs)