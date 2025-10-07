import json
import os
import time
import requests
from typing import List, Dict
import glob
#TO RUN:
#cd scripts
#python 5-generateTitlesAPI.py

def load_raw_segments(input_file: str) -> List[Dict]:
    """Load the raw segment data from JSON file."""
    with open(input_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def convert_seconds_to_timestamp(seconds: int) -> str:
    """Convert seconds to MM:SS or HH:MM:SS format."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"

def generate_title_with_gemini_http(transcript: str, api_key: str, max_retries: int = 3) -> str:
    """Generate a descriptive title for a transcript segment using Gemini HTTP API with retry logic."""
    
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    
    headers = {
        'Content-Type': 'application/json',
        'X-goog-api-key': api_key
    }
    
    prompt = f"""Generate ONE concise title for this video segment based on its content.

RULES:
- Exactly 3-6 words
- ONE line only (no bullet points, no line breaks)
- Focus on the most unique/specific event, concept, or topic in this segment
- Use specific names, actions, technical terms, or concrete details mentioned
- Make it descriptive and specific to what's actually happening or being discussed in the segment

Transcript:
"{transcript}"

Title:"""

    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }
    
    for attempt in range(max_retries):
        try:
            print(f"  Attempt {attempt + 1}/{max_retries}...")
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            # Extract the generated text from the response
            if 'candidates' in result and len(result['candidates']) > 0:
                candidate = result['candidates'][0]
                if 'content' in candidate and 'parts' in candidate['content']:
                    parts = candidate['content']['parts']
                    if len(parts) > 0 and 'text' in parts[0]:
                        title = parts[0]['text'].strip()
                        
                        # Clean up the title (remove quotes if present)
                        if title.startswith('"') and title.endswith('"'):
                            title = title[1:-1]
                        
                        print(f"  [PASS] Success on attempt {attempt + 1}")
                        return title
            
            # Fallback if response structure is unexpected
            print(f"  [WARN] Unexpected response structure on attempt {attempt + 1}: {result}")
            
        except requests.exceptions.RequestException as e:
            print(f"  [FAIL] HTTP Error on attempt {attempt + 1}: {e}")
        except Exception as e:
            print(f"  [FAIL] Error on attempt {attempt + 1}: {e}")
        
        # Wait before retrying (exponential backoff)
        if attempt < max_retries - 1:
            wait_time = (attempt + 1) * 2  # 2, 4, 6 seconds
            print(f"  [WAIT] Waiting {wait_time} seconds before retry...")
            time.sleep(wait_time)
    
    print(f"  [DEAD] Failed after {max_retries} attempts")
    return "Segment Title"

def process_segments(segments: List[Dict], api_key: str) -> List[Dict]:
    """Process all segments and generate titles with retry logic."""
    result = []
    failed_segments = []
    
    # First pass: try to generate all titles
    for i, segment in enumerate(segments):
        print(f"\n[PROC] Processing segment {i+1}/{len(segments)}...")
        
        # Extract transcript and start time
        transcript = segment['transcript']
        start_seconds = segment['start']
        
        # Convert start time to timestamp format
        timestamp = convert_seconds_to_timestamp(start_seconds)
        
        # Generate title using Gemini HTTP API
        title = generate_title_with_gemini_http(transcript, api_key)
        
        # Add to result
        segment_result = {
            "name": title,
            "time": timestamp,
            "index": i,
            "transcript": transcript
        }
        result.append(segment_result)
        
        # Track failed segments
        if title == "Segment Title":
            failed_segments.append(i)
            print(f"[FAIL] Failed: '{title}' at {timestamp}")
        else:
            print(f"[PASS] Generated: '{title}' at {timestamp}")
        
        # Add a small delay to avoid rate limiting
        time.sleep(2)
    
    # Second pass: retry failed segments
    if failed_segments:
        print(f"\n[RETRY] Retrying {len(failed_segments)} failed segments...")
        
        for attempt in range(2):  # Additional retry rounds
            if not failed_segments:
                break
                
            print(f"\n--- Retry Round {attempt + 1} ---")
            still_failed = []
            
            for i in failed_segments:
                print(f"\n[PROC] Retrying segment {i+1}...")
                transcript = result[i]['transcript']
                
                # Try generating title again
                title = generate_title_with_gemini_http(transcript, api_key, max_retries=2)
                
                if title != "Segment Title":
                    result[i]['name'] = title
                    print(f"[PASS] Retry success: '{title}' at {result[i]['time']}")
                else:
                    still_failed.append(i)
                    print(f"[FAIL] Still failed: segment {i+1}")
                
                time.sleep(3)  # Longer delay for retries
            
            failed_segments = still_failed
    
    # Clean up result (remove helper fields)
    final_result = []
    for item in result:
        final_result.append({
            "name": item['name'],
            "time": item['time']
        })
    
    return final_result

def discover_input_files(input_dir: str) -> List[str]:
    """Discover all JSON files in the input directory."""
    pattern = os.path.join(input_dir, "*.json")
    files = glob.glob(pattern)
    return [os.path.basename(f) for f in files]

def select_files_to_process(available_files: List[str]) -> List[str]:
    """Allow user to select which files to process."""
    if not available_files:
        print("No JSON files found in the input directory.")
        return []
    
    print("\nAvailable files to process:")
    print("=" * 50)
    for i, file in enumerate(available_files, 1):
        print(f"{i}. {file}")
    
    print("\nSelect files to process:")
    print("- Enter numbers separated by commas (e.g., 1,3,4)")
    print("- Enter 'all' to process all files")
    print("- Enter 'q' to quit")
    
    while True:
        selection = input("\nYour selection: ").strip().lower()
        
        if selection == 'q':
            return []
        
        if selection == 'all':
            return available_files
        
        try:
            # Parse comma-separated numbers
            indices = [int(x.strip()) for x in selection.split(',')]
            selected_files = []
            
            for idx in indices:
                if 1 <= idx <= len(available_files):
                    selected_files.append(available_files[idx - 1])
                else:
                    print(f"Invalid selection: {idx}. Please select numbers between 1 and {len(available_files)}")
                    break
            else:
                # All indices were valid
                return selected_files
                
        except ValueError:
            print("Invalid input. Please enter numbers separated by commas, 'all', or 'q'")

def generate_output_filename(input_filename: str) -> str:
    """Generate output filename based on input filename."""
    # Remove _segments_raw.json suffix and add _llm.json
    base_name = input_filename.replace('_segments_raw.json', '').replace('.json', '')
    return f"{base_name}_llm.json"

def save_results(results: List[Dict], output_file: str):
    """Save the results to JSON file."""
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

def main():
    # Configuration
    input_dir = r"..\output\raw_transcripts"
    output_dir = r"..\output\llm_generated"
    
    # INSERT: API Key
    api_key = "AIzaSyAqaItKe0TloNFIgUh4oW-5SoNDvOj3n4g"
    
    print("Using direct HTTP API calls to Gemini...")
    
    # Discover available files
    print("Discovering available files...")
    available_files = discover_input_files(input_dir)
    
    if not available_files:
        print(f"No JSON files found in {input_dir}")
        return
    
    # Let user select files to process
    selected_files = select_files_to_process(available_files)
    
    if not selected_files:
        print("No files selected. Exiting...")
        return
    
    print(f"\nProcessing {len(selected_files)} file(s)...")
    
    # Process each selected file
    for i, filename in enumerate(selected_files, 1):
        print(f"\n{'='*60}")
        print(f"Processing file {i}/{len(selected_files)}: {filename}")
        print(f"{'='*60}")
        
        # Construct full paths
        input_file = os.path.join(input_dir, filename)
        output_filename = generate_output_filename(filename)
        output_file = os.path.join(output_dir, output_filename)
        
        # Check if input file exists
        if not os.path.exists(input_file):
            print(f"Error: Input file not found: {input_file}")
            continue
        
        try:
            # Load segments
            print("Loading raw segments...")
            segments = load_raw_segments(input_file)
            print(f"Loaded {len(segments)} segments")
            
            # Process segments
            print("Generating titles with Gemini...")
            results = process_segments(segments, api_key)
            
            # Save results
            print(f"Saving results to {output_file}...")
            save_results(results, output_file)
            
            print(f"[PASS] Title generation complete for {filename}!")
            print(f"Generated {len(results)} titles")
            
            # Display results
            print(f"\nGenerated Titles for {filename}:")
            print("=" * 50)
            for item in results:
                print(f"{item['time']}: {item['name']}")
                
        except Exception as e:
            print(f"[FAIL] Error processing {filename}: {str(e)}")
            continue
    
    print(f"\n[DONE] All processing complete! Processed {len(selected_files)} file(s).")

if __name__ == "__main__":
    main()
