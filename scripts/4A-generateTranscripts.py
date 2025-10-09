#!/usr/bin/env python3
"""
4A-generateTranscripts.py

Generates transcript JSON files from chapter data and timestamp files.
Extracts the complete transcript text for each chapter segment.
"""

import json
import os
import re
import csv
from pathlib import Path

def parse_timestamp_line(line):
    """Parse a timestamp line to extract start time, end time, and text"""
    # Pattern: [start --> end] text
    pattern = r'\[(\d+\.?\d*) --> (\d+\.?\d*)\] (.+)'
    match = re.match(pattern, line.strip())
    if match:
        start = float(match.group(1))
        end = float(match.group(2))
        text = match.group(3)
        return start, end, text
    return None, None, None

def load_timestamps(timestamp_file):
    """Load all timestamps and text from a timestamp file"""
    timestamps = []
    try:
        with open(timestamp_file, 'r', encoding='utf-8') as f:
            for line in f:
                start, end, text = parse_timestamp_line(line)
                if start is not None:
                    timestamps.append({
                        'start': start,
                        'end': end,
                        'text': text
                    })
    except FileNotFoundError:
        print(f"Warning: Timestamp file not found: {timestamp_file}")
        return []
    except Exception as e:
        print(f"Error reading timestamp file {timestamp_file}: {e}")
        return []
    
    return timestamps

def load_timestamps_from_csv(csv_file):
    """Load timestamps and text from a CSV scores file (ignoring score column)"""
    timestamps = []
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    start = float(row['start'])
                    end = float(row['end'])
                    text = row['transcript']
                    timestamps.append({
                        'start': start,
                        'end': end,
                        'text': text
                    })
                except (ValueError, KeyError) as e:
                    print(f"Warning: Error parsing CSV row: {e}")
                    continue
    except FileNotFoundError:
        print(f"Warning: CSV file not found: {csv_file}")
        return []
    except Exception as e:
        print(f"Error reading CSV file {csv_file}: {e}")
        return []
    
    return timestamps

def find_matching_timestamp_file(chapter_file, timestamp_dir):
    """Find the corresponding timestamp file for a chapter file"""
    # Mapping of chapter files to timestamp files
    mappings = {
        'compute_pi_chapters.json': 'compute-pi_timestamps.txt',
        'robbers_cave_chapters.json': 'robbers cave experiment_timestamps.txt',
        'stanford_prison_chapters.json': 'the dark side of science the horrific stanford prison experiment 1971 _documentary__timestamps.txt',
        'five_puzzles_chapters.json': 'five puzzles for thinking outside the box_timestamps.txt'
    }
    
    chapter_filename = os.path.basename(chapter_file)
    if chapter_filename in mappings:
        return os.path.join(timestamp_dir, mappings[chapter_filename])
    
    # Try to find a matching file by similar naming
    chapter_base = chapter_filename.replace('_chapters.json', '').replace('.json', '')
    for ts_file in os.listdir(timestamp_dir):
        if ts_file.endswith('_timestamps.txt'):
            ts_base = ts_file.replace('_timestamps.txt', '').replace(' ', '_').lower()
            if chapter_base.lower() in ts_base or ts_base in chapter_base.lower():
                return os.path.join(timestamp_dir, ts_file)
    
    return None

def find_matching_csv_file(chapter_file, scores_dir):
    """Find the corresponding CSV scores file for a chapter file"""
    chapter_filename = os.path.basename(chapter_file)
    
    # Direct name mappings - try exact matches first
    chapter_base = chapter_filename.replace('_chapters.json', '').replace('.json', '')
    
    # Try different variations
    possible_names = [
        f"{chapter_base}.csv",
        f"{chapter_base}_export.csv",
        chapter_filename.replace('.json', '.csv'),
        chapter_filename.replace('_chapters.json', '.csv')
    ]
    
    for csv_name in possible_names:
        csv_path = os.path.join(scores_dir, csv_name)
        if os.path.exists(csv_path):
            return csv_path
    
    # Try to find by similar naming (case-insensitive matching)
    if os.path.exists(scores_dir):
        for csv_file in os.listdir(scores_dir):
            if csv_file.endswith('.csv'):
                csv_base = csv_file.replace('.csv', '').replace('_export', '').lower()
                if chapter_base.lower() == csv_base or chapter_base.lower() in csv_base:
                    return os.path.join(scores_dir, csv_file)
    
    return None

def extract_transcript_for_segment(timestamps, start_time, end_time):
    """Extract all transcript text between start_time and end_time"""
    transcript_parts = []
    
    for ts in timestamps:
        # Include timestamp if it overlaps with our segment
        # Use <= and >= to ensure we capture timestamps that touch the boundaries
        if ts['start'] < end_time and ts['end'] >= start_time:
            transcript_parts.append(ts['text'])
    
    return ' '.join(transcript_parts)

def generate_transcripts_for_file(chapter_file, timestamp_source, output_dir, source_type="txt"):
    """Generate transcript JSON for a single chapter file"""
    try:
        # Load chapters
        with open(chapter_file, 'r', encoding='utf-8') as f:
            chapters = json.load(f)
        
        # Load timestamps based on source type
        if source_type == "txt":
            timestamps = load_timestamps(timestamp_source)
            source_desc = f"timestamp file: {os.path.basename(timestamp_source)}"
        else:  # csv
            timestamps = load_timestamps_from_csv(timestamp_source)
            source_desc = f"CSV scores file: {os.path.basename(timestamp_source)}"
        
        if not timestamps:
            print(f"No timestamps found for {chapter_file}")
            return
        
        print(f"  Using {source_desc}")
        
        # Process each chapter
        transcript_data = []
        for i, chapter in enumerate(chapters):
            start_time = chapter['start']
            
            # Determine end time (next chapter's start or end of timestamps)
            if i + 1 < len(chapters):
                end_time = chapters[i + 1]['start']
            else:
                # Last chapter - use the end of the last timestamp
                end_time = timestamps[-1]['end'] if timestamps else start_time + 300
            
            print(f"    Processing segment {i+1}: '{chapter['name']}' ({start_time}-{end_time})")
            
            # Extract transcript for this segment
            transcript = extract_transcript_for_segment(timestamps, start_time, end_time)
            
            # Skip empty transcripts (likely an issue with segment boundaries)
            if not transcript.strip():
                print(f"    Warning: Empty transcript for segment '{chapter['name']}' ({start_time}-{end_time})")
                print(f"    DEBUG: This segment will be skipped!")
                continue
            
            print(f"    Found transcript: {len(transcript)} characters")
            
            segment_data = {
                "name": chapter['name'],
                "start": start_time,
                "end": end_time,
                "transcript": transcript
            }
            
            transcript_data.append(segment_data)
        
        # Generate output filename
        chapter_filename = os.path.basename(chapter_file)
        output_filename = chapter_filename.replace('_chapters.json', '_transcripts.json')
        output_path = os.path.join(output_dir, output_filename)
        
        # Save the transcript data
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(transcript_data, f, indent=2, ensure_ascii=False)
        
        print(f"Generated: {output_path}")
        print(f"  - Processed {len(transcript_data)} segments")
        
    except Exception as e:
        print(f"Error processing {chapter_file}: {e}")

def main():
    # Define paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    chapters_dir = project_root / 'output' / 'chapters'
    timestamps_dir = project_root / 'old' / 'timestamps'
    scores_dir = project_root / 'output' / 'scores'
    output_dir = project_root / 'output' / 'raw_transcripts'
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(exist_ok=True)
    
    print("4A-generateTranscripts: Generating transcript JSON files...")
    print(f"Chapters directory: {chapters_dir}")
    print(f"Timestamps directory: {timestamps_dir}")
    print(f"Scores directory (fallback): {scores_dir}")
    print(f"Output directory: {output_dir}")
    print()
    
    # Process each chapter file
    processed_count = 0
    for chapter_file in chapters_dir.glob('*.json'):
        print(f"Processing: {chapter_file.name}")
        
        # Try to find corresponding timestamp file first
        timestamp_file = find_matching_timestamp_file(str(chapter_file), str(timestamps_dir))
        
        if timestamp_file and os.path.exists(timestamp_file):
            generate_transcripts_for_file(str(chapter_file), timestamp_file, str(output_dir), "txt")
            processed_count += 1
        else:
            # Fallback to CSV scores file
            csv_file = find_matching_csv_file(str(chapter_file), str(scores_dir))
            
            if csv_file and os.path.exists(csv_file):
                print(f"  Timestamp file not found, falling back to CSV scores file")
                generate_transcripts_for_file(str(chapter_file), csv_file, str(output_dir), "csv")
                processed_count += 1
            else:
                print(f"  Warning: No matching timestamp file or CSV scores file found for {chapter_file.name}")
        
        print()
    
    print(f"Completed! Processed {processed_count} files.")
    print(f"Output files saved to: {output_dir}")

if __name__ == "__main__":
    main()