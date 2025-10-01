import re
import pandas as pd
import os
from IPython.display import display

# List of file names to process
file_names = ["airport food", 
              "bitcoin explained", 
              "differential equations",
              "human mistakes",
              "leetcode patterns",
              "linux file system",
              "mental puzzles",
              "schwarz lantern",
              "sudoku mastery",
              "virtual memory"]

def process_file_set(file_name):
    """Process a single set of timestamp and score files"""
    print(f"\n{'='*60}")
    print(f"Processing: {file_name}")
    print(f"{'='*60}")
    
    # Construct file paths
    timestamps_path = f"../output/{file_name}_timestamps.txt"
    scores_path = f"../output/{file_name}_all_mpnet_base_v2_scores.txt"
    
    # Create output directory
    output_dir = "../output/scores/"
    os.makedirs(output_dir, exist_ok=True)
    
    # Output file path (CSV only)
    clean_name = file_name.replace(" ", "_")
    output_csv = os.path.join(output_dir, f"{clean_name}_bert_output.csv")
    
    # Check if input files exist
    if not os.path.exists(timestamps_path):
        print(f"❌ Error: Timestamps file not found: {timestamps_path}")
        return False
    if not os.path.exists(scores_path):
        print(f"❌ Error: Scores file not found: {scores_path}")
        return False
    
    try:
        # Load and clean timestamps
        with open(timestamps_path, 'r', encoding='utf-8') as f:
            timestamp_lines = [line.strip() for line in f if line.strip()]
        
        print(f"📄 {len(timestamp_lines)} timestamp lines loaded from {timestamps_path}")
        
        timestamp_data = []
        timestamp_pattern = re.compile(r'\[(.*?) --> (.*?)\] (.+)')
        
        for line in timestamp_lines:
            match = timestamp_pattern.match(line)
            if match:
                start, end, text = match.groups()
                timestamp_data.append((text.strip(), float(start), float(end)))
        
        # Load and clean bert scores
        with open(scores_path, 'r', encoding='utf-8') as f:
            score_lines = [line.strip() for line in f if line.strip()]
        
        print(f"📊 {len(score_lines)} scored lines loaded from {scores_path}")
        
        score_data = []
        score_pattern = re.compile(r'^(\d+\.\d+) (.+)$')
        
        for line in score_lines:
            match = score_pattern.match(line)
            if match:
                score, text = match.groups()
                score_data.append((text.strip(), float(score)))
        
        # Match and merge
        combined = []
        text_to_timestamp = {text: (start, end) for text, start, end in timestamp_data}
        
        for text, score in score_data:
            if text in text_to_timestamp:
                start, end = text_to_timestamp[text]
                combined.append((score, start, end, text))
        
        if not combined:
            print(f"⚠️  Warning: No matching data found between timestamps and scores for {file_name}")
            return False
        
        # Create DataFrame
        df = pd.DataFrame(combined, columns=["score", "start", "end", "transcript"])
        
        # Export to CSV only
        df.to_csv(output_csv, index=False)
        print(f"✓ Saved CSV to {output_csv}")
        
        print(f"🎉 Successfully processed {len(df)} records for '{file_name}'")
        display(df.head())
        return True
        
    except Exception as e:
        print(f"❌ Error processing {file_name}: {str(e)}")
        return False

# Main execution
print("🚀 Starting batch processing of multiple file sets...")
print(f"Files to process: {file_names}")

successful_files = 0
total_files = len(file_names)

for file_name in file_names:
    if process_file_set(file_name):
        successful_files += 1

print(f"\n{'='*60}")
print(f"📈 BATCH PROCESSING COMPLETE")
print(f"{'='*60}")
print(f"✅ Successfully processed: {successful_files}/{total_files} file sets")
if successful_files < total_files:
    print(f"❌ Failed to process: {total_files - successful_files} file sets")
print(f"📂 All outputs saved to: output/scores/")

# Show summary of all generated files
if successful_files > 0:
    print(f"\n📋 Generated files:")
    for file_name in file_names:
        clean_name = file_name.replace(" ", "_")
        print(f"  - {clean_name}_bert_output.csv")
