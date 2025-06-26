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

audioFile = "audio/31M_audio.wav"
outputTxt = "output/transcript.txt"
outputTimestamps = "output/timestamps.txt"

model = whisperx.load_model("large-v2", device="cuda", compute_type="float16")

print(f"Transcribing... ({audioFile})")
result = model.transcribe(audioFile, language="en")

modelA, metadata = whisperx.load_align_model(language_code="en", device="cuda")
alignedResult = whisperx.align(result["segments"], modelA, metadata, audioFile, "cuda")

with open(outputTxt, "w", encoding="utf-8") as f:
    fullText = " ".join(segment["text"].strip() for segment in alignedResult["segments"])
    f.write(fullText)
with open(outputTimestamps, "w", encoding="utf-8") as f:
    for segment in alignedResult["segments"]:
        f.write(f"[{segment['start']} --> {segment['end']}] {segment['text'].strip()}\n")

print("transcript.txt and timestamps.txt created successfully.")
