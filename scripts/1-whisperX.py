import torch
import whisperx
from pathlib import Path

audio_file = "Audio/15M_audio.wav"
output_txt = "Output/transcript.txt"
output_timestamps = "Output/sentence_timestamps.txt"

device = "cuda" if torch.cuda.is_available() else "cpu"
model = whisperx.load_model("medium", device, compute_type="float16")

print("Transcribing...")
result = model.transcribe(audio_file, language="en")

model_a, metadata = whisperx.load_align_model(language_code="en", device=device)
aligned_result = whisperx.align(result["segments"], model_a, metadata, audio_file, device)

with open(output_txt, "w", encoding="utf-8") as f:
    for segment in aligned_result["segments"]:
        f.write(segment["text"].strip() + "\n")

with open(output_timestamps, "w", encoding="utf-8") as f:
    for segment in aligned_result["segments"]:
        f.write(f"[{segment['start']} --> {segment['end']}] {segment['text'].strip()}\n")

print("WhisperX transcription and alignment complete.")
