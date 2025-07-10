import subprocess
import sys
import re
from pathlib import Path

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install"] + package.split())

try:
    import torch
except ImportError:
    install("torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu")

try:
    import whisperx
except ImportError:
    install("whisperx")

import torch
import whisperx

# Load models once at startup
print("Loading WhisperX model...")
model = whisperx.load_model("base", device="cuda", compute_type="float16", local_files_only=False)
print("Loading alignment model...")
modelA, metadata = whisperx.load_align_model(language_code="en", device="cuda")

def find_audio_files(folder):
    """Find all audio files in the folder"""
    audio_files = []
    for ext in ['*.wav', '*.mp3', '*.m4a', '*.flac']:
        audio_files.extend(folder.glob(ext))
    return sorted(audio_files)

def create_bert_style_sentences(full_text):
    """Split text using the same regex as BERT script"""
    sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s', full_text)
    sentences = [s.strip() for s in sentences if s.strip()]
    return sentences

def create_transcript_with_timestamps(segments, transcript_file, timestamps_file):
    """Create transcript and timestamps ensuring each line matches BERT processing"""
    # First, combine all segment text
    full_text = " ".join(segment["text"].strip() for segment in segments)
    
    # Split using BERT regex to get sentences
    bert_sentences = create_bert_style_sentences(full_text)
    
    # Save transcript (just the sentences joined)
    with open(transcript_file, "w", encoding="utf-8") as f:
        f.write(" ".join(bert_sentences))
    
    # Create timestamps for each BERT sentence
    with open(timestamps_file, "w", encoding="utf-8") as f:
        sentence_index = 0
        segment_index = 0
        current_sentence = bert_sentences[sentence_index] if bert_sentences else ""
        sentence_start_time = segments[0]["start"] if segments else 0
        accumulated_text = ""
        
        for segment in segments:
            segment_text = segment["text"].strip()
            accumulated_text += " " + segment_text if accumulated_text else segment_text
            
            # Check if we've completed the current sentence
            while sentence_index < len(bert_sentences) and current_sentence in accumulated_text:
                # Find the end time for this sentence
                sentence_end_time = segment["end"]
                
                # Write the timestamp for this sentence
                f.write(f"[{sentence_start_time:.2f} --> {sentence_end_time:.2f}] {current_sentence}\n")
                
                # Move to next sentence
                sentence_index += 1
                if sentence_index < len(bert_sentences):
                    current_sentence = bert_sentences[sentence_index]
                    sentence_start_time = segment["end"]  # Next sentence starts where this one ends
                    # Remove the completed sentence from accumulated text
                    accumulated_text = accumulated_text.replace(bert_sentences[sentence_index - 1], "", 1).strip()
                else:
                    break

def create_transcript(audio_file, output_folder):
    """Create transcript from audio file using WhisperX"""
    # Create output filename based on audio filename
    base_name = audio_file.stem.lower()
    transcript_name = f"{base_name}_transcript.txt"
    timestamps_name = f"{base_name}_timestamps.txt"
    
    transcript_file = output_folder / transcript_name
    timestamps_file = output_folder / timestamps_name
    
    print(f"Working on: {audio_file.name}")
    
    # Check if files already exist
    if transcript_file.exists():
        answer = input(f"'{transcript_name}' exists. Replace it? (y/n): ")
        if answer.lower() != 'y':
            print("Skipping...")
            return False
    
    try:
        print("Transcribing...")
        result = model.transcribe(str(audio_file), language="en")
        
        print("Aligning timestamps...")
        aligned_result = whisperx.align(result["segments"], modelA, metadata, str(audio_file), "cuda")
        
        # Create transcript and timestamps with BERT-matching sentences
        create_transcript_with_timestamps(aligned_result["segments"], transcript_file, timestamps_file)
        
        print(f"✓ Saved: {transcript_name} and {timestamps_name}")
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def parse_selection(choice, max_num):
    """Parse user selection like '1', '1,3', '1-3', or 'all'"""
    choice = choice.strip().lower()
    
    if choice == 'all':
        return list(range(max_num))
    
    selected = []
    parts = choice.split(',')
    
    for part in parts:
        part = part.strip()
        if '-' in part:
            # Handle range like '1-3'
            try:
                start, end = part.split('-')
                start_idx = int(start) - 1
                end_idx = int(end) - 1
                if 0 <= start_idx <= end_idx < max_num:
                    selected.extend(range(start_idx, end_idx + 1))
            except ValueError:
                continue
        else:
            # Handle single number
            try:
                idx = int(part) - 1
                if 0 <= idx < max_num:
                    selected.append(idx)
            except ValueError:
                continue
    
    return sorted(list(set(selected)))  # Remove duplicates and sort

def main():
    here = Path(__file__).parent
    audio_folder = here / "../audio"
    output_folder = here / "../output"
 
    if not audio_folder.exists():
        print(f"Can't find audio folder: {audio_folder}")
        return
    
    output_folder.mkdir(exist_ok=True)
    audio_files = find_audio_files(audio_folder)
    if not audio_files:
        print("No audio files found")
        return
    
    # Display available files
    print(f"Found {len(audio_files)} audio file(s):")
    for i, audio in enumerate(audio_files, 1):
        print(f"  {i}. {audio.name}")
    
    # Get user selection
    print("\nSelect files to process:")
    print("  - Single file: 1")
    print("  - Multiple files: 1,3,4")
    print("  - Range: 1-3")
    print("  - All files: all")
    
    choice = input(f"\nSelect (1-{len(audio_files)} or combinations): ").strip()
    
    selected_indices = parse_selection(choice, len(audio_files))
    
    if not selected_indices:
        print("No valid selection made")
        return
    
    # Show selected files
    selected_files = [audio_files[i] for i in selected_indices]
    print(f"\nSelected {len(selected_files)} file(s):")
    for audio in selected_files:
        print(f"  - {audio.name}")
    
    # Confirm processing
    confirm = input(f"\nProcess these {len(selected_files)} file(s)? (y/n): ")
    if confirm.lower() != 'y':
        print("Cancelled")
        return
    
    # Process selected files
    success_count = 0
    for audio in selected_files:
        if create_transcript(audio, output_folder):
            success_count += 1
    
    print(f"\nDone! Created {success_count}/{len(selected_files)} transcripts")

if __name__ == "__main__":
    main()
