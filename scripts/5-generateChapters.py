#!/usr/bin/env python3
# Video Title Scoring Script - THS-ST Project


#INSTALL DEPENDENCIES: pip install bert-score scikit-learn pandas numpy
#FIRST go to repo file:
# cd /root/THS-ST 
# python scripts/5-generateChapters.py --menu
# python scripts/5-generateChapters.py --input-csv output/llm_generated/batch/five_puzzles_batch_titles.csv
# python scripts/5-generateChapters.py --transcripts-dir output/raw_transcripts/

import os
import json
import csv
import argparse
import gc
import time
import warnings
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np
from collections import defaultdict

warnings.filterwarnings('ignore')

# Import scoring libraries
try:
    from bert_score import score as bert_score
    BERT_AVAILABLE = True
except ImportError:
    BERT_AVAILABLE = False
    print("WARNING: BERT-Score not available. Install with: pip install bert-score")

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    COSINE_AVAILABLE = True
except ImportError:
    COSINE_AVAILABLE = False
    print("WARNING: Scikit-learn not available. Install with: pip install scikit-learn")


class VideoTitleScorer:
    
    #TERMINAL COLOURS
    RED = '\033[91m'
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    ORANGE = '\033[33m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    
    def __init__(self):
        """
        Initialize the video title scorer.
        """
        # Philippine timezone (UTC+8)
        self.ph_tz = timezone(timedelta(hours=8))
        
        # Verify required libraries
        missing_libs = []
        if not BERT_AVAILABLE:
            missing_libs.append("bert-score (pip install bert-score)")
        if not COSINE_AVAILABLE:
            missing_libs.append("scikit-learn (pip install scikit-learn)")
            
        if missing_libs:
            print(f"{self.RED}[CRITICAL ERROR]: Missing required libraries!{self.RESET}")
            for lib in missing_libs:
                print(f"  - {lib}")
            print(f"{self.RED}Please install missing libraries and try again.{self.RESET}")
            import sys
            sys.exit(1)
        
        print(f"[INFO] VideoTitleScorer initialized successfully")
        print(f"[PASS] Required libraries verified: BERT-Score, Scikit-learn")
    
    def _get_ph_timestamp(self) -> str:
        """Get current timestamp in Philippine timezone."""
        return datetime.now(self.ph_tz).strftime("%d/%m/%y %H:%M:%S")
    
    def _get_char_count_color(self, char_count: int) -> str:
        """Get color code based on character count."""
        if char_count < 100:  # Too little
            return self.RED
        elif char_count < 1000:  # Good amount
            return self.GREEN
        elif char_count < 5000:  # Nearing big amount
            return self.ORANGE
        else:  # A lot
            return self.RED
    
    def load_title_data(self, csv_file: str) -> pd.DataFrame:
        """
        Load title data from CSV file.
        
        Args:
            csv_file: Path to the CSV file containing title data
            
        Returns:
            DataFrame with title data
        """
        print(f"\n{self.CYAN}=== LOADING TITLE DATA ==={self.RESET}")
        
        csv_path = Path(csv_file)
        if not csv_path.exists():
            print(f"{self.RED}[ERROR]{self.RESET} CSV file not found: {csv_file}")
            raise FileNotFoundError(f"CSV file not found: {csv_file}")
        
        try:
            # Load CSV with proper handling
            df = pd.read_csv(csv_file)
            
            # Verify required columns
            required_cols = ['video', 'start', 'generated_title']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                print(f"{self.RED}[ERROR]{self.RESET} Missing required columns: {missing_cols}")
                print(f"Available columns: {list(df.columns)}")
                raise ValueError(f"Missing required columns: {missing_cols}")
            
            # Handle different column naming schemes
            if 's#' in df.columns:
                df['segment'] = df['s#']
            elif 'segment' not in df.columns:
                print(f"{self.YELLOW}[WARNING]{self.RESET} No segment column found, using row order")
                df['segment'] = df.groupby(['video']).cumcount() + 1
            
            if 't#' in df.columns:
                df['title_number'] = df['t#']
            elif 'title_number' not in df.columns:
                df['title_number'] = df.groupby(['video', 'segment']).cumcount() + 1
            
            timestamp = self._get_ph_timestamp()
            print(f"({self.GREEN}PASS{self.RESET} | {timestamp}) Loaded {len(df)} title entries from CSV")
            
            # Display summary by video
            video_counts = df.groupby('video').size()
            for video_name, count in video_counts.items():
                unique_segments = df[df['video'] == video_name]['segment'].nunique()
                print(f"    {self.GREEN}[{video_name.upper()}]{self.RESET} {count} titles across {unique_segments} segments")
            
            return df
            
        except Exception as e:
            print(f"{self.RED}[ERROR]{self.RESET} Failed to load CSV: {e}")
            raise
    
    def load_transcript_data(self, transcripts_dir: str) -> Dict[str, List[Dict]]:
        """
        Load transcript data from JSON files.
        
        Args:
            transcripts_dir: Directory containing transcript JSON files
            
        Returns:
            Dictionary mapping video names to segment lists
        """
        print(f"\n{self.CYAN}=== LOADING TRANSCRIPT DATA ==={self.RESET}")
        
        transcripts_path = Path(transcripts_dir)
        if not transcripts_path.exists():
            print(f"{self.RED}[ERROR]{self.RESET} Transcripts directory not found: {transcripts_dir}")
            raise FileNotFoundError(f"Transcripts directory not found: {transcripts_dir}")
        
        transcripts = {}
        transcript_files = list(transcripts_path.glob("*_transcripts.json"))
        
        if not transcript_files:
            print(f"{self.RED}[ERROR]{self.RESET} No transcript files found in: {transcripts_dir}")
            raise FileNotFoundError(f"No transcript files found in: {transcripts_dir}")
        
        for json_file in transcript_files:
            video_name = json_file.stem.replace("_transcripts", "")
            
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    transcripts[video_name] = data
                    
                    # Display with improved format
                    timestamp = self._get_ph_timestamp()
                    print(f"({self.GREEN}PASS{self.RESET} | {timestamp}) [{video_name.upper()}] Loaded {len(data)} segments")
                    
                    # Show character count for each segment with color coding
                    for i, segment in enumerate(data, 1):
                        char_count = len(segment.get('transcript', ''))
                        color = self._get_char_count_color(char_count)
                        start_time = segment.get('start', 'N/A')
                        print(f"    {color}[{i:02d}]{self.RESET} Start: {start_time}, {char_count:,} characters")
                            
            except Exception as e:
                timestamp = self._get_ph_timestamp()
                print(f"({self.RED}ERROR{self.RESET} | {timestamp}) [{video_name.upper()}] Error loading: {e}")
        
        return transcripts
    
    def find_matching_segment(self, transcripts: List[Dict], start_time: float) -> Optional[Dict]:
        """
        Find the transcript segment that matches the given start time.
        
        Args:
            transcripts: List of transcript segments for a video
            start_time: Start time to match
            
        Returns:
            Matching segment dictionary or None
        """
        for segment in transcripts:
            segment_start = segment.get('start', 0)
            if abs(segment_start - start_time) < 1:  # Allow 1 second tolerance
                return segment
        return None
    
    def calculate_bert_score(self, candidates: List[str], references: List[str]) -> Tuple[List[float], List[float], List[float]]:
        """
        Calculate BERT scores using mpnet model for candidate titles against reference transcripts.
        
        Args:
            candidates: List of candidate titles
            references: List of reference transcripts
            
        Returns:
            Tuple of (precision, recall, f1) score lists
        """
        if not candidates or not references:
            return [], [], []
        
        try:
            # Calculate BERT score using mpnet model for better performance
            P, R, F1 = bert_score(candidates, references, lang="en", model_type="microsoft/mpnet-base", verbose=False)
            
            # Convert tensors to lists if necessary
            if hasattr(P, 'tolist'):
                P = P.tolist()
            if hasattr(R, 'tolist'):
                R = R.tolist()
            if hasattr(F1, 'tolist'):
                F1 = F1.tolist()
            
            return P, R, F1
            
        except Exception as e:
            print(f"{self.RED}[ERROR]{self.RESET} BERT Score calculation failed: {e}")
            # Return zeros as fallback
            return [0.0] * len(candidates), [0.0] * len(candidates), [0.0] * len(candidates)
    
    def calculate_cosine_similarity(self, candidates: List[str], references: List[str]) -> List[float]:
        """
        Calculate cosine similarity scores for candidate titles against reference transcripts.
        
        Args:
            candidates: List of candidate titles
            references: List of reference transcripts
            
        Returns:
            List of cosine similarity scores
        """
        if not candidates or not references:
            return []
        
        try:
            # Create TF-IDF vectorizer
            vectorizer = TfidfVectorizer(stop_words='english', max_features=5000)
            
            # Combine all texts for fitting
            all_texts = candidates + references
            vectorizer.fit(all_texts)
            
            # Transform candidates and references
            candidate_vectors = vectorizer.transform(candidates)
            reference_vectors = vectorizer.transform(references)
            
            # Calculate cosine similarity for each pair
            similarities = []
            for i in range(len(candidates)):
                sim = cosine_similarity(candidate_vectors[i], reference_vectors[i])[0][0]
                similarities.append(sim)
            
            return similarities
            
        except Exception as e:
            print(f"{self.RED}[ERROR]{self.RESET} Cosine similarity calculation failed: {e}")
            # Return zeros as fallback
            return [0.0] * len(candidates)
    
    def score_video_titles(self, title_df: pd.DataFrame, transcripts: Dict[str, List[Dict]]) -> Dict:
        """
        Score all video titles against their corresponding transcript segments.
        
        Args:
            title_df: DataFrame containing title data
            transcripts: Dictionary of video transcripts
            
        Returns:
            Dictionary containing all scoring results
        """
        print(f"\n{self.CYAN}=== SCORING VIDEO TITLES ==={self.RESET}")
        
        results = {
            'video_results': {},
            'model_performance': defaultdict(list),
            'overall_stats': {}
        }
        
        # Process each video
        unique_videos = title_df['video'].unique()
        
        for video_idx, video_name in enumerate(unique_videos, 1):
            print(f"\n{self.PURPLE}{'*'*60}{self.RESET}")
            print(f"{self.PURPLE}({video_idx}/{len(unique_videos)}) PROCESSING [{video_name.upper()}]{self.RESET}")
            print(f"{self.PURPLE}{'*'*60}{self.RESET}")
            
            if video_name not in transcripts:
                print(f"{self.RED}[ERROR]{self.RESET} No transcript found for video: {video_name}")
                continue
            
            video_transcripts = transcripts[video_name]
            video_df = title_df[title_df['video'] == video_name].copy()
            
            video_results = {
                'segments': {},
                'best_titles': {},
                'segment_count': 0
            }
            
            # Process each segment
            unique_segments = sorted(video_df['segment'].unique())
            
            for seg_idx, segment_num in enumerate(unique_segments, 1):
                print(f"\n{self.YELLOW}--- Segment {segment_num:02d}/{len(unique_segments):02d} ---{self.RESET}")
                
                # Get all titles for this segment
                segment_df = video_df[video_df['segment'] == segment_num].copy()
                
                if segment_df.empty:
                    continue
                
                # Find matching transcript segment
                start_time = segment_df['start'].iloc[0]  # All should have same start time
                matching_segment = self.find_matching_segment(video_transcripts, start_time)
                
                if not matching_segment:
                    print(f"{self.RED}[ERROR]{self.RESET} No matching transcript segment found for start time: {start_time}")
                    continue
                
                transcript_text = matching_segment.get('transcript', '')
                char_count = len(transcript_text)
                color = self._get_char_count_color(char_count)
                
                print(f"  {color}Transcript:{self.RESET} {char_count:,} characters, Start: {start_time}")
                
                # Prepare data for scoring
                candidates = segment_df['generated_title'].tolist()
                references = [transcript_text] * len(candidates)
                
                print(f"  {self.CYAN}Scoring:{self.RESET} {len(candidates)} titles against transcript...")
                
                # Calculate BERT scores
                timestamp = self._get_ph_timestamp()
                print(f"  ({timestamp}) Calculating BERT scores...")
                bert_p, bert_r, bert_f1 = self.calculate_bert_score(candidates, references)
                
                # Calculate Cosine similarities  
                timestamp = self._get_ph_timestamp()
                print(f"  ({timestamp}) Calculating Cosine similarities...")
                cosine_scores = self.calculate_cosine_similarity(candidates, references)
                
                # Calculate average scores and rank titles
                title_scores = []
                for i, (title, model) in enumerate(zip(candidates, segment_df['model'])):
                    bert_score = bert_f1[i] if i < len(bert_f1) else 0.0
                    cosine_score = cosine_scores[i] if i < len(cosine_scores) else 0.0
                    avg_score = (bert_score + cosine_score) / 2
                    
                    title_scores.append({
                        'title': title,
                        'model': model,
                        'bert_score': bert_score,
                        'cosine_score': cosine_score,
                        'average_score': avg_score,
                        'title_number': segment_df.iloc[i].get('title_number', i+1)
                    })
                    
                    # Track model performance
                    results['model_performance'][model].append(avg_score)
                
                # Sort by average score (descending)
                title_scores.sort(key=lambda x: x['average_score'], reverse=True)
                
                # Store segment results
                video_results['segments'][segment_num] = {
                    'start_time': start_time,
                    'transcript_chars': char_count,
                    'title_scores': title_scores,
                    'top_3': title_scores[:3],
                    'best_title': title_scores[0] if title_scores else None
                }
                
                # Display results as markdown table
                self._display_segment_table(segment_num, start_time, title_scores[:5])  # Show top 5 in table
                
                # Track best title for this segment
                if title_scores:
                    best = title_scores[0]
                    video_results['best_titles'][segment_num] = {
                        'name': best['title'],
                        'start': start_time,
                        'timestamp': self._format_timestamp(start_time),
                        'score': best['average_score'],
                        'model': best['model']
                    }
            
            video_results['segment_count'] = len(unique_segments)
            results['video_results'][video_name] = video_results
        
        return results
    
    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds into MM:SS or HH:MM:SS format."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"
    
    def _display_segment_table(self, segment_num: int, start_time: float, title_scores: List[Dict]) -> None:
        """Display segment results as a formatted markdown-style table with full title length."""
        timestamp = self._format_timestamp(start_time)
        
        print(f"\n  {self.CYAN}📊 SEGMENT {segment_num:02d} RESULTS ({timestamp}){self.RESET}")
        print(f"  {'-'*120}")
        print(f"  {'Rank':<4} | {'Score':<6} | {'BERT':<6} | {'Cosine':<6} | {'Model':<12} | {'Title'}")
        print(f"  {'-'*120}")
        
        for rank, score_data in enumerate(title_scores, 1):
            # Color code based on score
            if score_data['average_score'] >= 0.8:
                color = self.GREEN
            elif score_data['average_score'] >= 0.6:
                color = self.YELLOW  
            else:
                color = self.RED
            
            # DO NOT CUT TITLE LENGTH - show full title
            full_title = score_data['title']
            
            print(f"  {color}{rank:<4}{self.RESET} | {score_data['average_score']:<6.3f} | "
                  f"{score_data['bert_score']:<6.3f} | {score_data['cosine_score']:<6.3f} | "
                  f"{score_data['model']:<12} | {full_title}")
        
        print(f"  {'-'*120}\n")
    
    def generate_reports(self, results: Dict, output_dir: str) -> None:
        """
        Generate comprehensive text and JSON reports.
        
        Args:
            results: Scoring results dictionary
            output_dir: Directory to save reports
        """
        print(f"\n{self.CYAN}=== GENERATING REPORTS ==={self.RESET}")
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Create score_overview subdirectory
        score_overview_path = Path("output/llm_generated/score_overview")
        score_overview_path.mkdir(parents=True, exist_ok=True)
        
        # Create main llm_generated directory for final output
        llm_generated_path = Path("output/llm_generated")
        llm_generated_path.mkdir(parents=True, exist_ok=True)
        
        # Generate detailed text report in score_overview directory
        self._generate_detailed_text_report(results, score_overview_path)
        
        # Generate simple JSON chapter file in llm_generated directory
        self._generate_json_chapters(results, llm_generated_path)
        
        timestamp = self._get_ph_timestamp()
        print(f"({self.GREEN}PASS{self.RESET} | {timestamp}) Reports generated successfully")
    
    def _generate_detailed_text_report(self, results: Dict, output_path: Path) -> None:
        """Generate detailed text report."""
        report_file = output_path / "video_title_scoring_summary.txt"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("VIDEO TITLE SCORING OVERVIEW REPORT\n")
            f.write("="*80 + "\n")
            f.write(f"Generated: {self._get_ph_timestamp()}\n")
            f.write(f"Total Videos Processed: {len(results['video_results'])}\n\n")
            
            # Per-video breakdown
            for video_name, video_data in results['video_results'].items():
                f.write("="*60 + "\n")
                f.write(f"VIDEO: {video_name.upper()}\n")
                f.write("="*60 + "\n")
                f.write(f"Total Segments: {video_data['segment_count']}\n\n")
                
                # Process each segment
                for segment_num in sorted(video_data['segments'].keys()):
                    segment_data = video_data['segments'][segment_num]
                    
                    f.write(f"--- SEGMENT {segment_num:02d} ---\n")
                    f.write(f"Start Time: {segment_data['start_time']}s ({self._format_timestamp(segment_data['start_time'])})\n")
                    f.write(f"Transcript Length: {segment_data['transcript_chars']:,} characters\n")
                    f.write(f"Total Titles Evaluated: {len(segment_data['title_scores'])}\n\n")
                    
                    # Top 3 titles
                    f.write("TOP 3 TITLES:\n")
                    for rank, title_data in enumerate(segment_data['top_3'], 1):
                        f.write(f"  [{rank}] Score: {title_data['average_score']:.4f} "
                               f"(BERT: {title_data['bert_score']:.4f}, Cosine: {title_data['cosine_score']:.4f})\n")
                        f.write(f"      Model: [{title_data['model']}]\n")
                        f.write(f"      Title: \"{title_data['title']}\"\n\n")
                    
                    # All titles table
                    f.write("ALL TITLES:\n")
                    f.write("Rank | Avg Score | BERT Score | Cosine Score | Model | Title\n")
                    f.write("-" * 120 + "\n")
                    
                    for rank, title_data in enumerate(segment_data['title_scores'], 1):
                        # DO NOT CUT TITLE LENGTH - show full title in report
                        f.write(f"{rank:4d} | {title_data['average_score']:9.4f} | "
                               f"{title_data['bert_score']:10.4f} | "
                               f"{title_data['cosine_score']:12.4f} | "
                               f"{title_data['model']:12s} | \"{title_data['title']}\"\n")
                    
                    f.write("\n" + "-"*60 + "\n\n")
                
                # Video summary - best titles per segment
                f.write("FINAL VIDEO SUMMARY - BEST TITLES:\n")
                f.write("-" * 50 + "\n")
                for segment_num in sorted(video_data['best_titles'].keys()):
                    best = video_data['best_titles'][segment_num]
                    f.write(f"Segment {segment_num:02d} ({best['timestamp']}): \"{best['name']}\"\n")
                    f.write(f"  Score: {best['score']:.4f} | Model: [{best['model']}]\n\n")
                
                f.write("\n")
            
            # Overall model performance
            f.write("="*60 + "\n")
            f.write("OVERALL MODEL PERFORMANCE\n")
            f.write("="*60 + "\n")
            
            model_stats = {}
            for model, scores in results['model_performance'].items():
                if scores:  # Only if model has scores
                    model_stats[model] = {
                        'avg_score': np.mean(scores),
                        'std_score': np.std(scores),
                        'min_score': np.min(scores),
                        'max_score': np.max(scores),
                        'total_titles': len(scores)
                    }
            
            # Sort by average score
            sorted_models = sorted(model_stats.items(), key=lambda x: x[1]['avg_score'], reverse=True)
            
            f.write("Model Performance Summary:\n")
            f.write("Model        | Avg Score | Std Dev | Min Score | Max Score | Total Titles\n")
            f.write("-" * 75 + "\n")
            
            for model, stats in sorted_models:
                f.write(f"{model:12s} | {stats['avg_score']:9.4f} | {stats['std_score']:7.4f} | "
                       f"{stats['min_score']:9.4f} | {stats['max_score']:9.4f} | {stats['total_titles']:12d}\n")
        
        print(f"  {self.GREEN}✓{self.RESET} Detailed scoring report saved: {report_file}")
    
    def _generate_json_chapters(self, results: Dict, output_path: Path) -> None:
        """Generate simple JSON chapter file with best titles."""
        json_file = output_path / "video_title_generated_chapter.json"
        
        chapters = []
        
        for video_name, video_data in results['video_results'].items():
            for segment_num in sorted(video_data['best_titles'].keys()):
                best_title = video_data['best_titles'][segment_num]
                
                # Simple format with only title, start, timestamp
                chapters.append({
                    'title': best_title['name'],
                    'start': float(best_title['start']),
                    'timestamp': best_title['timestamp']
                })
        
        # Sort by start time
        chapters.sort(key=lambda x: x['start'])
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(chapters, f, indent=2, ensure_ascii=False)
        
        print(f"  {self.GREEN}✓{self.RESET} Best titles JSON saved: {json_file}")
        print(f"    Total chapters: {len(chapters)}")
    
    def process_titles(self, csv_file: str, transcripts_dir: str, output_dir: str = "output") -> None:
        """
        Main processing function to score video titles.
        
        Args:
            csv_file: Path to CSV file with title data
            transcripts_dir: Directory containing transcript JSON files
            output_dir: Output directory for reports
        """
        print(f"{self.BLUE}{'='*70}{self.RESET}")
        print(f"{self.BLUE}VIDEO TITLE SCORING SYSTEM - STARTING PROCESSING{self.RESET}")
        print(f"{self.BLUE}{'='*70}{self.RESET}")
        
        start_time = time.time()
        
        try:
            # Load data
            title_df = self.load_title_data(csv_file)
            transcripts = self.load_transcript_data(transcripts_dir)
            
            # Score titles
            results = self.score_video_titles(title_df, transcripts)
            
            # Generate reports
            self.generate_reports(results, output_dir)
            
            # Final summary
            total_time = time.time() - start_time
            minutes = int(total_time // 60)
            seconds = int(total_time % 60)
            
            print(f"\n{self.GREEN}{'='*70}{self.RESET}")
            print(f"{self.GREEN}PROCESSING COMPLETE!{self.RESET}")
            print(f"{self.GREEN}{'='*70}{self.RESET}")
            print(f"Total Processing Time: {minutes:02d}:{seconds:02d}")
            print(f"Videos Processed: {len(results['video_results'])}")
            print(f"Total Segments: {sum(v['segment_count'] for v in results['video_results'].values())}")
            print(f"Reports Generated:")
            print(f"  - output/llm_generated/video_title_generated_chapter.json")
            print(f"  - output/llm_generated/score_overview/video_title_scoring_summary.txt")
            
        except Exception as e:
            print(f"\n{self.RED}[ERROR]{self.RESET} Processing failed: {e}")
            raise


def show_menu() -> str:
    """Show interactive menu for CSV file selection."""
    # Get available CSV files from batch directory
    batch_dir = Path("output/llm_generated/batch")
    
    if not batch_dir.exists():
        print(f"Batch directory not found: {batch_dir}")
        return ""
    
    csv_files = list(batch_dir.glob("*_batch_titles.csv"))
    
    if not csv_files:
        print(f"No CSV files found in {batch_dir}")
        return ""
    
    # Extract video names from filenames
    videos = []
    for file in csv_files:
        video_name = file.stem.replace("_batch_titles", "")
        videos.append((video_name, str(file)))
    
    videos.sort()  # Sort alphabetically by video name
    
    while True:
        print("\n" + "="*60)
        print("           VIDEO TITLE SCORING MENU")
        print("="*60)
        print("Available CSV files with generated titles:")
        
        for i, (video_name, file_path) in enumerate(videos, 1):
            print(f"  {i:2d}. {video_name}")
        
        print("\nSelection options:")
        print("  - Select CSV file: Enter number (e.g., '2')")
        print("  - Cancel: Enter 'q' or 'quit'")
        
        selection = input("\nEnter your selection: ").strip().lower()
        
        if selection in ['q', 'quit']:
            return ""
        
        try:
            num = int(selection)
            if 1 <= num <= len(videos):
                selected_video, selected_path = videos[num-1]
                print(f"\nSelected: {selected_video}")
                confirm = input("Proceed with this selection? (y/n): ").strip().lower()
                if confirm in ['y', 'yes']:
                    return selected_path
            else:
                print(f"Error: Invalid number: {num}")
                continue
        except ValueError:
            print("Error: Please enter a valid number")
            continue
        
        print()  # Add spacing before showing menu again


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Score LLM-generated video titles against transcript segments")
    parser.add_argument(
        "--input-csv",
        default="",
        help="Path to CSV file containing generated titles"
    )
    parser.add_argument(
        "--transcripts-dir", 
        default="output/raw_transcripts",
        help="Directory containing transcript JSON files"
    )
    parser.add_argument(
        "--output-dir", 
        default="output",
        help="Directory for output reports"
    )
    parser.add_argument(
        "--menu",
        action="store_true",
        help="Show interactive menu for CSV file selection"
    )
    
    args = parser.parse_args()

    # Handle menu mode or automatic selection
    if args.menu:
        selected_csv = show_menu()
        if not selected_csv:
            print("No CSV file selected. Exiting.")
            return
        args.input_csv = selected_csv
    elif not args.input_csv:
        # Try to find CSV files automatically
        batch_dir = Path("output/llm_generated/batch")
        if batch_dir.exists():
            csv_files = list(batch_dir.glob("*_batch_titles.csv"))
            if csv_files:
                if len(csv_files) == 1:
                    args.input_csv = str(csv_files[0])
                    print(f"Auto-selected only available CSV file: {csv_files[0].name}")
                else:
                    print("Multiple CSV files found. Use --menu to select:")
                    for i, csv_file in enumerate(csv_files, 1):
                        print(f"  {i}. {csv_file.name}")
                    return
            else:
                print(f"No CSV files found in {batch_dir}")
                return
        else:
            print(f"Batch directory not found: {batch_dir}")
            return
    
    print(f"Input CSV: {args.input_csv}")
    print(f"Transcripts Directory: {args.transcripts_dir}")
    print(f"Output Directory: {args.output_dir}")
    
    # Verify input file exists
    if not Path(args.input_csv).exists():
        print(f"Error: CSV file not found: {args.input_csv}")
        return
    
    # Initialize scorer and process
    scorer = VideoTitleScorer()
    scorer.process_titles(args.input_csv, args.transcripts_dir, args.output_dir)


if __name__ == "__main__":
    main()
