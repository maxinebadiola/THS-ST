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

def find_audio_files(folder):
    """Find all audio files in the folder"""
    audio_files = []
    for ext in ['*.wav', '*.mp3', '*.m4a', '*.flac']:
        audio_files.extend(folder.glob(ext))
    return sorted(audio_files)

def splitSegmentsIntoSentences(segments):
    """Split WhisperX segments into sentences that match BERT sentence splitting"""
    sentenceSegments = []
    
    for segment in segments:
        text = segment["text"].strip()
        startTime = segment["start"]
        endTime = segment["end"]
        
        #BERT regex
        sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if len(sentences) <= 1:
            sentenceSegments.append(segment)
        else:
            # Distribute timestamps proportionally based on character count
            totalChars = sum(len(s) for s in sentences)
            duration = endTime - startTime
            
            currentStart = startTime
            for i, sentence in enumerate(sentences):
                if i == len(sentences) - 1:
                    # Last sentence gets remaining time
                    sentenceEnd = endTime
                else:
                    # Proportional time allocation
                    sentenceDuration = (len(sentence) / totalChars) * duration
                    sentenceEnd = currentStart + sentenceDuration
                
                sentenceSegments.append({
                    "start": currentStart,
                    "end": sentenceEnd,
                    "text": sentence
                })
                
                currentStart = sentenceEnd
    
    return sentenceSegments

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
        print("Loading WhisperX model...")
        model = whisperx.load_model("large-v2", device="cuda", compute_type="float16")
        print("Transcribing...")
        result = model.transcribe(str(audio_file), language="en")
        
        print("Aligning timestamps...")
        modelA, metadata = whisperx.load_align_model(language_code="en", device="cuda")
        aligned_result = whisperx.align(result["segments"], modelA, metadata, str(audio_file), "cuda")
        
        # Split segments into sentences that match BERT processing
        sentence_segments = split_segments_into_sentences(aligned_result["segments"])
        
        #save transcript
        with open(transcript_file, "w", encoding="utf-8") as f:
            full_text = " ".join(segment["text"].strip() for segment in sentence_segments)
            f.write(full_text)
        
        #save timestamps
        with open(timestamps_file, "w", encoding="utf-8") as f:
            for segment in sentence_segments:
                f.write(f"[{segment['start']:.2f} --> {segment['end']:.2f}] {segment['text'].strip()}\n")
        
        print(f"✓ Saved: {transcript_name} and {timestamps_name}")
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

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
    #found
    print(f"Found {len(audio_files)} audio file(s):")
    for i, audio in enumerate(audio_files, 1):
        print(f"  {i}. {audio.name}")
    
    #USER SELECTION
    if len(audio_files) == 1:
        answer = input("\nCreate transcript from this audio? (y/n): ")
        if answer.lower() == 'y':
            create_transcript(audio_files[0], output_folder)
    else:
        print(f"  {len(audio_files) + 1}. All audio files")
        choice = input(f"\nSelect: (1-{len(audio_files) + 1}): ")
        
        if choice == str(len(audio_files) + 1) or choice.lower() == 'all':
            # Process all
            success_count = 0
            for audio in audio_files:
                if create_transcript(audio, output_folder):
                    success_count += 1
            print(f"\nDone! Created {success_count}/{len(audio_files)} transcripts")
        else:
            # Process specific file
            try:
                index = int(choice) - 1
                if 0 <= index < len(audio_files):
                    create_transcript(audio_files[index], output_folder)
                else:
                    print("Invalid number")
            except ValueError:
                print("Please enter a number")

if __name__ == "__main__":
    main()
