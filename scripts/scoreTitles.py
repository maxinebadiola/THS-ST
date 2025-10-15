"""
Title Selection Script for Video Segments
==========================================
Scoring Metrics:
1. Cosine Similarity (TF-IDF)
2. BERTScore (F1)
3. Verbosity Penalty

Final Score = ((BERTScore + CosineSimilarity) / 2) * Penalty
"""

import os
import json
import math
import warnings
import time
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from bert_score import score as bert_score
from colorama import Fore, Style, init

#supress irrelevant Hugging Face warnings. BERTScore doesn't use the 'pooler' layer, so redundant
warnings.filterwarnings('ignore', message='Some weights of.*were not initialized')
warnings.filterwarnings('ignore', message='.*pooler.*')
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=FutureWarning)

# Also suppress transformers library logging
import logging
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("bert_score").setLevel(logging.ERROR)

init(autoreset=True)
referenceLength = 6  #for verbosity penalty

# Directory paths
BASE_DIR = Path(__file__).parent.parent
BATCH_DIR = BASE_DIR / "output" / "llm_generated" / "batch"
TRANSCRIPT_DIR = BASE_DIR / "output" / "raw_transcripts"
REPORT_DIR = BASE_DIR / "output" / "reports"
SELECTED_TITLES_DIR = BASE_DIR / "output" / "selected_titles"

# Ensure output directories exist
REPORT_DIR.mkdir(parents=True, exist_ok=True)
SELECTED_TITLES_DIR.mkdir(parents=True, exist_ok=True)


#model color for terminal
MODEL_COLORS = {
    'llama3.1-8b': Fore.BLUE,
    'llama3.1-70b': Fore.MAGENTA,
    'tinyllama': Fore.CYAN,
    'gpt-4o-mini': '\033[95m',  # Light Magenta
    'gpt-4o': '\033[94m',  # Light Blue
    'mistral': '\033[96m',  # Light Cyan
    'qwen': '\033[35m',  # Purple
    'phi': '\033[34m',  # Blue
}


def get_model_color(model_name):
    """
    Get color for a specific model.
    
    Args:
        model_name (str): Name of the model
    
    Returns:
        str: ANSI color code for the model
    """
    # Return assigned color or default to BLUE if model not in mapping
    return MODEL_COLORS.get(model_name, Fore.BLUE)


def calculate_verbosity_penalty(title, reference_length=referenceLength):
    """
    Calculate verbosity penalty for a title.
    
    Args:
        title (str): The candidate title
        reference_length (int): Reference length for penalty calculation
    
    Returns:
        float: Penalty value (1.0 if length <= reference, else e^(1 - length/reference))
    """
    word_count = len(title.split())
    
    if word_count <= reference_length:
        return 1.0
    else:
        return math.exp(1 - word_count / reference_length)


def calculate_cosine_similarity(title, transcript):
    """
    Calculate cosine similarity between title and transcript using TF-IDF.
    
    Args:
        title (str): The candidate title
        transcript (str): The full transcript text
    
    Returns:
        float: Cosine similarity score
    """
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform([title, transcript])
    similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
    return similarity


def calculate_bert_score(title, transcript):
    """
    Calculate BERTScore F1 between title and transcript using MPNet.
    
    Args:
        title (str): The candidate title
        transcript (str): The full transcript text
    
    Returns:
        float: BERTScore F1 value
    """
    # Calculate BERTScore (P, R, F1) using MPNet model
    P, R, F1 = bert_score([title], [transcript], model_type='microsoft/mpnet-base', lang='en', verbose=False)
    return F1.item()


def find_available_videos():
    """
    Scan directories and find videos with both transcript and titles files.
    
    Returns:
        list: List of video names that have both required files
    """
    available_videos = []
    
    # Get all CSV files from batch directory
    if not BATCH_DIR.exists():
        print(f"{Fore.RED}Error: Batch directory not found: {BATCH_DIR}")
        return []
    
    csv_files = list(BATCH_DIR.glob("*_batch_titles.csv"))
    
    for csv_file in csv_files:
        # Extract video name from filename (remove _batch_titles.csv suffix)
        video_name = csv_file.stem.replace("_batch_titles", "")
        
        # Check if corresponding transcript exists
        transcript_file = TRANSCRIPT_DIR / f"{video_name}_transcripts.json"
        
        if transcript_file.exists():
            available_videos.append(video_name)
    
    return sorted(available_videos)


def load_transcript(video_name):
    """
    Load transcript for a video from JSON file.
    
    Args:
        video_name (str): Name of the video
    
    Returns:
        list: List of transcript segments with 'start', 'end', and 'transcript' fields
    """
    transcript_file = TRANSCRIPT_DIR / f"{video_name}_transcripts.json"
    
    with open(transcript_file, 'r', encoding='utf-8') as f:
        transcripts = json.load(f)
    
    return transcripts


def load_titles(video_name):
    """
    Load candidate titles for a video from CSV file.
    
    Args:
        video_name (str): Name of the video
    
    Returns:
        pandas.DataFrame: DataFrame with candidate titles
    """
    titles_file = BATCH_DIR / f"{video_name}_batch_titles.csv"
    
    df = pd.read_csv(titles_file)
    return df


def format_timestamp(seconds):
    """
    Convert seconds to MM:SS format.
    
    Args:
        seconds (int): Time in seconds
    
    Returns:
        str: Formatted timestamp
    """
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes:02d}:{secs:02d}"


def parse_selection(input_str, max_idx):
    """
    Parse user input for video selection.
    
    Args:
        input_str (str): Input string like "1-3,5" or "all"
        max_idx (int): Maximum valid index (length of videos list)
    
    Returns:
        list: List of 1-based indices
    
    Raises:
        ValueError: If input is invalid
    """
    if input_str.lower() == 'all':
        return list(range(1, max_idx + 1))
    
    parts = input_str.split(',')
    indices = []
    
    for part in parts:
        part = part.strip()
        if '-' in part:
            try:
                start, end = part.split('-')
                start = int(start.strip())
                end = int(end.strip())
                if start > end:
                    raise ValueError(f"Invalid range {start}-{end}")
                indices.extend(range(start, end + 1))
            except ValueError:
                raise ValueError(f"Invalid range format: {part}")
        else:
            try:
                idx = int(part.strip())
                indices.append(idx)
            except ValueError:
                raise ValueError(f"Invalid number: {part}")
    
    # Validate indices
    for idx in indices:
        if idx < 1 or idx > max_idx:
            raise ValueError(f"Index {idx} out of range (1-{max_idx})")
    
    return sorted(set(indices))


def evaluate_titles(video_name):
    """
    Main function to evaluate titles for a video.
    
    Args:
        video_name (str): Name of the video to process
    """
    # Start timing
    video_start_time = time.time()
    
    print(f"\n{Fore.CYAN}{'='*80}")
    print(f"{Fore.CYAN}Processing Video: {Fore.YELLOW}{video_name}")
    print(f"{Fore.CYAN}{'='*80}\n")
    
    # Load data
    print(f"{Fore.GREEN}Loading transcript...")
    transcripts = load_transcript(video_name)
    
    print(f"{Fore.GREEN}Loading candidate titles...")
    titles_df = load_titles(video_name)
    
    # Results storage
    all_results = []
    segment_results = {}
    model_scores = {}
    
    # Get unique segments
    segments = sorted(titles_df['segment'].unique())
    
    print(f"\n{Fore.CYAN}Found {len(segments)} segments to process\n")
    
    # Process each segment
    for seg_num in segments:
        # Start segment timing
        segment_start_time = time.time()
        
        print(f"\n{Fore.MAGENTA}{'─'*80}")
        print(f"{Fore.MAGENTA}Segment {seg_num:02d}/{len(segments):02d}")
        print(f"{Fore.MAGENTA}{'─'*80}")
        
        # Get titles for this segment
        segment_titles = titles_df[titles_df['segment'] == seg_num]
        
        # Get corresponding transcript
        # Segments are 1-indexed in the CSV but 0-indexed in the transcript list
        transcript_idx = seg_num - 1
        
        if transcript_idx >= len(transcripts):
            print(f"{Fore.RED}Warning: Segment {seg_num} not found in transcript")
            continue
        
        transcript_data = transcripts[transcript_idx]
        full_transcript = transcript_data['transcript']
        start_time = transcript_data['start']
        
        # Display segment info
        print(f"{Fore.CYAN}Start Time: {Fore.WHITE}{format_timestamp(start_time)} ({start_time}s)")
        print(f"{Fore.CYAN}Transcript: {Fore.WHITE}{len(full_transcript):,} characters")
        print(f"{Fore.CYAN}Evaluating {Fore.YELLOW}{len(segment_titles)} {Fore.CYAN}titles...\n")
        
        # Evaluate each title
        segment_scores = []
        seen_titles_in_segment = {}  # Track duplicates during scoring
        
        for idx, row in segment_titles.iterrows():
            title = row['generated_title']
            model = row['model']
            
            # Get model color
            model_color = get_model_color(model)
            
            # Check if this exact title was already scored
            if title in seen_titles_in_segment:
                # Duplicate detected during scoring - show message
                seen_titles_in_segment[title]['count'] += 1
                
                # Calculate scores for duplicate
                cosine_score = calculate_cosine_similarity(title, full_transcript)
                bert_score_val = calculate_bert_score(title, full_transcript)
                penalty = calculate_verbosity_penalty(title)
                avg_score = ((bert_score_val + cosine_score) / 2) * penalty
                
                # Color code the score
                if avg_score >= 0.27:
                    score_color = Fore.GREEN
                elif avg_score >= 0.2:
                    score_color = Fore.YELLOW
                else:
                    score_color = Fore.RED
                
                # Color code the penalty
                if penalty == 1.0:
                    penalty_color = Fore.GREEN
                elif penalty >= 0.6:
                    penalty_color = '\033[33m'  # Orange
                else:
                    penalty_color = Fore.RED
                
                print(f"  {model_color}[{model}]{Fore.RESET} Duplicate title detected, skipping scoring...")
                print(f"  {Fore.WHITE}→ Score: {score_color}{avg_score:.4f}{Fore.RESET} "
                      f"(BERT: {bert_score_val:.3f}, Cosine: {cosine_score:.3f}, Penalty: {penalty_color}{penalty:.3f}{Fore.RESET})\n")
                
                # Still add to results for tracking
                result = {
                    'segment': seg_num,
                    'start': start_time,
                    'model': model,
                    'title': title,
                    'cosine_score': cosine_score,
                    'bert_score': bert_score_val,
                    'penalty': penalty,
                    'avg_score': avg_score,
                    'title_number': row['title_number']
                }
                segment_scores.append(result)
                all_results.append(result)
                
                if model not in model_scores:
                    model_scores[model] = []
                model_scores[model].append(avg_score)
                
                continue
            
            # New unique title - score it normally
            seen_titles_in_segment[title] = {'count': 1}
            
            # Show which title is being scored
            print(f"  {model_color}[{model}]{Fore.RESET} Scoring: \"{title[:60]}{'...' if len(title) > 60 else ''}\"")
            
            # Calculate scores
            cosine_score = calculate_cosine_similarity(title, full_transcript)
            bert_score_val = calculate_bert_score(title, full_transcript)
            penalty = calculate_verbosity_penalty(title)
            
            # Calculate final score
            avg_score = ((bert_score_val + cosine_score) / 2) * penalty
            
            # Color code the score
            if avg_score >= 0.27:
                score_color = Fore.GREEN
            elif avg_score >= 0.2:
                score_color = Fore.YELLOW
            else:
                score_color = Fore.RED
            
            # Color code the penalty
            if penalty == 1.0:
                penalty_color = Fore.GREEN
            elif penalty >= 0.6:
                penalty_color = '\033[33m'  # Orange
            else:
                penalty_color = Fore.RED
            
            print(f"  {Fore.WHITE}→ Score: {score_color}{avg_score:.4f}{Fore.RESET} "
                  f"(BERT: {bert_score_val:.3f}, Cosine: {cosine_score:.3f}, Penalty: {penalty_color}{penalty:.3f}{Fore.RESET})\n")
            
            result = {
                'segment': seg_num,
                'start': start_time,
                'model': model,
                'title': title,
                'cosine_score': cosine_score,
                'bert_score': bert_score_val,
                'penalty': penalty,
                'avg_score': avg_score,
                'title_number': row['title_number']
            }
            
            segment_scores.append(result)
            all_results.append(result)
            
            # Track model scores
            if model not in model_scores:
                model_scores[model] = []
            model_scores[model].append(avg_score)
        
        # Store segment results
        segment_results[seg_num] = {
            'start': start_time,
            'transcript_length': len(full_transcript),
            'scores': sorted(segment_scores, key=lambda x: x['avg_score'], reverse=True)
        }
        
        # Display top 3 results for this segment
        print(f"{Fore.CYAN}{'─'*80}")
        print(f"{Fore.CYAN}Top 3 Results for Segment {seg_num:02d}:")
        print(f"{Fore.CYAN}{'─'*80}")
        
        # Get unique titles for Top 3 display
        seen_titles = {}
        unique_results = []
        
        for result in segment_results[seg_num]['scores']:
            title = result['title']
            if title not in seen_titles:
                # First occurrence of this title
                seen_titles[title] = {'count': 1, 'result': result}
                unique_results.append(result)
            else:
                # Duplicate title - just increment count
                seen_titles[title]['count'] += 1
        
        # Display top 3 unique titles
        for rank, result in enumerate(unique_results[:3], 1):
            if result['avg_score'] >= 0.27:
                score_color = Fore.GREEN
            elif result['avg_score'] >= 0.2:
                score_color = Fore.YELLOW
            else:
                score_color = Fore.RED
            
            # Get model color
            model_color = get_model_color(result['model'])
            
            # Get duplicate count for this title
            dup_count = seen_titles[result['title']]['count']
            dup_indicator = f" {Fore.YELLOW}({dup_count}){Fore.RESET}" if dup_count > 1 else ""
            
            print(f"{Fore.WHITE}#{rank} {score_color}{result['avg_score']:.4f}{Fore.RESET} "
                  f"{model_color}[{result['model']}]{Fore.RESET} \"{result['title']}\"{dup_indicator}")
        
        # Calculate and display segment elapsed time
        segment_elapsed = time.time() - segment_start_time
        minutes = int(segment_elapsed // 60)
        seconds = int(segment_elapsed % 60)
        print(f"{Fore.CYAN}Segment completed in: {Fore.WHITE}{minutes:02d}:{seconds:02d}{Fore.RESET}\n")
    
    # Display model average scores
    print(f"\n{Fore.CYAN}{'='*80}")
    print(f"{Fore.CYAN}Model Performance Summary for {video_name}")
    print(f"{Fore.CYAN}{'='*80}\n")
    
    for model in sorted(model_scores.keys()):
        avg = np.mean(model_scores[model])
        print(f"{Fore.YELLOW}{model:20s} {Fore.WHITE}Average Score: {Fore.GREEN}{avg:.4f}")
    
    # Generate outputs
    generate_text_report(video_name, segment_results, model_scores)
    generate_csv_scores(video_name, segment_results)
    generate_json_output(video_name, segment_results)
    
    # Calculate and display total video processing time
    video_elapsed = time.time() - video_start_time
    total_minutes = int(video_elapsed // 60)
    total_seconds = int(video_elapsed % 60)
    
    print(f"\n{Fore.GREEN}{'='*80}")
    print(f"{Fore.GREEN}Processing Complete!")
    print(f"{Fore.GREEN}Total time: {Fore.WHITE}{total_minutes:02d}:{total_seconds:02d}{Fore.RESET}")
    print(f"{Fore.GREEN}{'='*80}\n")


def generate_text_report(video_name, segment_results, model_scores):
    """
    Generate detailed text report for the video.
    
    Args:
        video_name (str): Name of the video
        segment_results (dict): Dictionary of segment results
        model_scores (dict): Dictionary of model scores
    """
    report_file = REPORT_DIR / f"{video_name}_title_evaluation.txt"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("="*100 + "\n")
        f.write(f"TITLE EVALUATION REPORT: {video_name}\n")
        f.write("="*100 + "\n\n")
        
        # Overall model performance
        f.write("OVERALL MODEL PERFORMANCE\n")
        f.write("-"*100 + "\n")
        for model in sorted(model_scores.keys()):
            avg = np.mean(model_scores[model])
            f.write(f"{model:20s} Average Score: {avg:.4f}\n")
        f.write("\n\n")
        
        # Segment-by-segment details
        for seg_num in sorted(segment_results.keys()):
            seg_data = segment_results[seg_num]
            
            f.write(f"--- SEGMENT {seg_num:02d} ---\n")
            f.write(f"Start Time: {seg_data['start']}s ({format_timestamp(seg_data['start'])})\n")
            f.write(f"Transcript Length: {seg_data['transcript_length']:,} characters\n")
            f.write(f"Total Titles Evaluated: {len(seg_data['scores'])}\n\n")
            
            # Table header
            f.write(f"{'Rank':<6} {'Avg Score':<12} {'Bert Score':<12} {'Cosine Score':<14} {'Penalty':<10} {'Model':<20} {'Title'}\n")
            f.write("-"*100 + "\n")
            
            # Group duplicate titles
            seen_titles = {}
            unique_results = []
            
            for result in seg_data['scores']:
                title = result['title']
                if title not in seen_titles:
                    # First occurrence of this title
                    seen_titles[title] = {'count': 1, 'result': result}
                    unique_results.append(result)
                else:
                    # Duplicate title - just increment count
                    seen_titles[title]['count'] += 1
            
            # Table rows - show only unique titles with counts
            for rank, result in enumerate(unique_results, 1):
                dup_count = seen_titles[result['title']]['count']
                title_display = result['title']
                if dup_count > 1:
                    title_display = f"{result['title']} ({dup_count})"
                
                f.write(f"{rank:<6} {result['avg_score']:<12.4f} {result['bert_score']:<12.4f} "
                       f"{result['cosine_score']:<14.4f} {result['penalty']:<10.4f} "
                       f"{result['model']:<20} {title_display}\n")
            
            # Segment model averages
            f.write("\n")
            f.write("Model Averages for this Segment:\n")
            segment_model_scores = {}
            for result in seg_data['scores']:
                model = result['model']
                if model not in segment_model_scores:
                    segment_model_scores[model] = []
                segment_model_scores[model].append(result['avg_score'])
            
            for model in sorted(segment_model_scores.keys()):
                avg = np.mean(segment_model_scores[model])
                f.write(f"  {model:20s}: {avg:.4f}\n")
            
            f.write("\n" + "="*100 + "\n\n")
    
    print(f"{Fore.GREEN}Text report saved to: {Fore.WHITE}{report_file}")


def generate_csv_scores(video_name, segment_results):
    """
    Generate CSV file with all title scores.
    
    Args:
        video_name (str): Name of the video
        segment_results (dict): Dictionary of segment results
    """
    csv_file = REPORT_DIR / f"{video_name}_scores.csv"
    
    # Collect all scores
    rows = []
    for seg_num in sorted(segment_results.keys()):
        seg_data = segment_results[seg_num]
        
        for result in seg_data['scores']:
            rows.append({
                'segment': result['segment'],
                'start_time': result['start'],
                'timestamp': format_timestamp(result['start']),
                'model': result['model'],
                'title': result['title'],
                'avg_score': result['avg_score'],
                'bert_score': result['bert_score'],
                'cosine_score': result['cosine_score'],
                'penalty': result['penalty']
            })
    
    # Create DataFrame and save to CSV
    df = pd.DataFrame(rows)
    df.to_csv(csv_file, index=False, encoding='utf-8')
    
    print(f"{Fore.GREEN}CSV scores saved to: {Fore.WHITE}{csv_file}")


def generate_json_output(video_name, segment_results):
    """
    Generate JSON output with the highest-scoring title for each segment.
    
    Args:
        video_name (str): Name of the video
        segment_results (dict): Dictionary of segment results
    """
    json_output = []
    
    for seg_num in sorted(segment_results.keys()):
        seg_data = segment_results[seg_num]
        
        # Get the highest-scoring title
        best_title = seg_data['scores'][0]
        
        json_output.append({
            'name': best_title['title'],
            'start': seg_data['start'],
            'timestamp': format_timestamp(seg_data['start'])
        })
    
    # Save JSON file
    json_file = SELECTED_TITLES_DIR / f"{video_name}_chapters.json"
    
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(json_output, f, indent=2, ensure_ascii=False)
    
    print(f"{Fore.GREEN}JSON output saved to: {Fore.WHITE}{json_file}")


def display_menu(videos):
    """
    Display menu of available videos for user selection.
    
    Args:
        videos (list): List of available video names
    
    Returns:
        list: List of selected video names or empty list to exit
    """
    print(f"\n{Fore.CYAN}{'='*80}")
    print(f"{Fore.CYAN}Available Videos for Title Selection")
    print(f"{Fore.CYAN}{'='*80}\n")
    
    for idx, video in enumerate(videos, 1):
        print(f"{Fore.YELLOW}{idx:2d}. {Fore.WHITE}{video}")
    
    print(f"\n{Fore.YELLOW}Examples: {Fore.WHITE}1-3,5  or  'all'  or  0 to exit")
    print()
    
    while True:
        try:
            choice = input(f"{Fore.GREEN}Select videos to process: {Fore.WHITE}").strip()
            
            if choice.lower() in ['0', 'exit', 'quit']:
                return []
            
            indices = parse_selection(choice, len(videos))
            selected_videos = [videos[i-1] for i in indices]
            return selected_videos
            
        except ValueError as e:
            print(f"{Fore.RED}Error: {e}. Please try again.")
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Operation cancelled by user.")
            return []


def main():
    """
    Main function to run the title selection script.
    """
    # Start overall timing
    overall_start_time = time.time()
    
    print(f"\n{Fore.CYAN}{'='*80}")
    print(f"{Fore.CYAN}Video Title Selection Script")
    print(f"{Fore.CYAN}{'='*80}\n")
    
    # Find available videos
    print(f"{Fore.GREEN}Scanning for available videos...")
    available_videos = find_available_videos()
    
    if not available_videos:
        print(f"{Fore.RED}No videos found with both transcript and titles files.")
        print(f"{Fore.YELLOW}Please ensure files exist in:")
        print(f"  - {TRANSCRIPT_DIR}")
        print(f"  - {BATCH_DIR}")
        return
    
    print(f"{Fore.GREEN}Found {len(available_videos)} video(s) ready for processing.\n")
    
    # Display menu and get user selection
    selected_videos = display_menu(available_videos)
    
    if not selected_videos:
        print(f"\n{Fore.YELLOW}Exiting script. Goodbye!")
        return
    
    # Process selected videos
    for video in selected_videos:
        evaluate_titles(video)
    
    # Calculate and display overall execution time
    overall_elapsed = time.time() - overall_start_time
    total_minutes = int(overall_elapsed // 60)
    total_seconds = int(overall_elapsed % 60)
    
    print(f"\n{Fore.CYAN}{'='*80}")
    print(f"{Fore.CYAN}All Processing Complete!")
    print(f"{Fore.CYAN}Total execution time: {Fore.WHITE}{total_minutes:02d}:{total_seconds:02d}{Fore.RESET}")
    print(f"{Fore.CYAN}Videos processed: {Fore.YELLOW}{len(selected_videos)}{Fore.RESET}")
    print(f"{Fore.CYAN}{'='*80}\n")


if __name__ == "__main__":
    main()
