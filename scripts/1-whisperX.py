import subprocess
import sys

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
from pathlib import Path

audioFile = "THS-ST/audio/15M_audio.wav"
outputTxt = "THS-ST/output/transcript.txt"
outputTimestamps = "THS-ST/output/timestamps.txt"

device = "cuda"
computeType = "float16"  # Faster, lower memory (A4000 supports this well)
model = whisperx.load_model("large-v2", device=device, compute_type=computeType)

print(f"Transcribing... ({audioFile})")
result = model.transcribe(audioFile, language="en")

modelA, metadata = whisperx.load_align_model(language_code="en", device=device)
alignedResult = whisperx.align(result["segments"], modelA, metadata, audioFile, device)

with open(outputTxt, "w", encoding="utf-8") as f:
    fullText = " ".join(segment["text"].strip() for segment in alignedResult["segments"])
    f.write(fullText)
with open(outputTimestamps, "w", encoding="utf-8") as f:
    for segment in alignedResult["segments"]:
        f.write(f"[{segment['start']} --> {segment['end']}] {segment['text'].strip()}\n")

print("transcript.txt and sentence_timestamps.txt created successfully.")
