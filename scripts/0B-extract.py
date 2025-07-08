import os
import subprocess
from pathlib import Path

def findVideos(folder):
    videoFiles = []
    for ext in ['*.mp4','*.mkv']:
        videoFiles.extend(folder.glob(ext))
    return sorted(videoFiles)

def cleanName(filename):
    clean = ""
    for char in filename:
        if char.isalnum() or char in ' -_':
            clean += char
    return clean.strip()

def getQualitySettings(videoFile):
    """Get quality settings for a specific video file"""
    estimated_size = estimateMaxQualitySize(videoFile)
    
    print(f"\nQuality options for '{videoFile.name}':")
    if estimated_size:
        print(f"1. Max quality (Est. {estimated_size:.1f} MB)")
    else:
        print("1. Max quality (size estimate unavailable)")
    print("2. Best quality under 100MB")
    
    while True:
        choice = input("Select quality option (1-2): ").strip()
        if choice == "1":
            return "max", None
        elif choice == "2":
            return "limited", 100
        else:
            print("Please enter 1 or 2")

def getVideoDuration(videoFile):
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
            '-of', 'csv=p=0', str(videoFile)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return None
        
        duration = float(result.stdout.strip())
        return duration if duration > 0 else None
        
    except Exception:
        return None

def estimateMaxQualitySize(videoFile):
    duration = getVideoDuration(videoFile)
    if duration is None:
        return None
    estimatedBytes = duration * 288000
    estimatedMB = estimatedBytes / (1024 * 1024)
    return estimatedMB

def calculateBitrate(videoFile, targetSizeMB):
    duration = getVideoDuration(videoFile)
    if duration is None:
        return None
    
    try:
        targetSizeBytes = targetSizeMB * 1024 * 1024
        maxBitrate = int((targetSizeBytes * 8) / duration / 1000)
        return max(64, maxBitrate)
        
    except Exception as e:
        print(f"Warning: Could not calculate optimal bitrate: {e}")
        return None

def extractAudio(videoFile, outputFolder, qualityMode="max", targetSizeMB=None):
    outputName = cleanName(videoFile.stem) + ".wav"
    outputFile = outputFolder / outputName
    
    print(f"Extracting audio from: {videoFile.name}")
    
    #already exists
    if outputFile.exists():
        answer = input(f"'{outputName}' exists. Replace file? (Y/N): ")
        if answer.lower() != 'y':
            print("Skipping...")
            return False
    
    # Base ffmpeg command
    cmd = ['ffmpeg', '-i', str(videoFile), '-vn']
    
    if qualityMode == "max":
        # Maximum quality settings
        cmd.extend([
            '-acodec', 'pcm_s24le',  # 24-bit PCM for max quality
            '-ar', '48000',  # 48kHz sample rate
            '-ac', '2',  # stereo
        ])
        print("Using maximum quality settings (24-bit, 48kHz)")
    else:
        bitrate = calculateBitrate(videoFile, targetSizeMB)
        if bitrate:
            # Use compressed format to meet size requirements
            cmd.extend([
                '-acodec', 'pcm_s16le',  # 16-bit PCM
                '-ar', '44100',  # 44.1kHz sample rate
                '-ac', '2',  # stereo
                '-ab', f'{bitrate}k',  # calculated bitrate
            ])
            print(f"Using optimized settings for {targetSizeMB}MB limit (16-bit, 44.1kHz, {bitrate}kbps)")
        else:
            # Fallback to standard settings
            cmd.extend([
                '-acodec', 'pcm_s16le',
                '-ar', '44100',
                '-ac', '2',
            ])
            print("Using standard quality settings (16-bit, 44.1kHz)")
    
    cmd.extend(['-y', str(outputFile)])  # overwrite
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            size = outputFile.stat().st_size / (1024 * 1024)
            print(f"✓ Saved: {outputName} ({size:.1f} MB)")
            
            # Check if file meets size requirement
            if qualityMode == "limited" and targetSizeMB and size > targetSizeMB:
                print(f"⚠ Warning: File size ({size:.1f} MB) exceeds target ({targetSizeMB} MB)")
                # Optionally try again with lower quality
                retry = input("Try again with lower quality? (Y/N): ")
                if retry.lower() == 'y':
                    # Remove the oversized file and try with lower bitrate
                    outputFile.unlink()
                    return extractAudioWithLowerQuality(videoFile, outputFolder, targetSizeMB, size)
            
            return True
        else:
            print(f"✗ ERROR: {result.stderr.strip()}")
            return False
    except FileNotFoundError:
        print("ERROR: ffmpeg not found.")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def extractAudioWithLowerQuality(videoFile, outputFolder, targetSizeMB, previousSize):
    """Retry extraction with lower quality settings"""
    outputName = cleanName(videoFile.stem) + ".wav"
    outputFile = outputFolder / outputName
    
    print(f"Retrying with lower quality to meet {targetSizeMB}MB limit...")
    
    # Calculate a more conservative bitrate
    scaleFactor = targetSizeMB / previousSize * 0.8  # 80% of calculated to be safe
    newBitrate = max(32, int(calculateBitrate(videoFile, targetSizeMB) * scaleFactor))
    
    cmd = [
        'ffmpeg', '-i', str(videoFile),
        '-vn',
        '-acodec', 'pcm_s16le',
        '-ar', '22050',  # Lower sample rate
        '-ac', '1',      # Mono instead of stereo
        '-ab', f'{newBitrate}k',
        '-y', str(outputFile)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            size = outputFile.stat().st_size / (1024 * 1024)
            print(f"✓ Saved: {outputName} ({size:.1f} MB) with reduced quality")
            return True
        else:
            print(f"✗ ERROR: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def main():
    #file paths
    here = Path(__file__).parent
    videoFolder = here / "../video"
    audioFolder = here / "../audio"

    if not videoFolder.exists():
        print(f"Can't find video folder: {videoFolder}")
        return
    
    audioFolder.mkdir(exist_ok=True)
    videos = findVideos(videoFolder)
    if not videos:
        print("No video files found")
        return
    
    print(f"Found {len(videos)} video file(s):")
    for i, video in enumerate(videos, 1):
        duration = getVideoDuration(video)
        file_size_mb = video.stat().st_size / (1024 * 1024)
        
        if duration:
            duration_str = f"{int(duration//60)}:{int(duration%60):02d}"
            print(f"  {i}. {video.name} ({duration_str} | {file_size_mb:.1f} MB)")
        else:
            print(f"  {i}. {video.name} (Duration unknown | {file_size_mb:.1f} MB)")
    
    #USER SELECTION
    if len(videos) == 1:
        answer = input(f"\nExtract audio from this video? (Y/N): ")
        if answer.lower() == 'y':
            qualityMode, targetSize = getQualitySettings(videos[0])
            extractAudio(videos[0], audioFolder, qualityMode, targetSize)
    else:
        print(f"  {len(videos) + 1}. All videos")
        choice = input(f"\nSelect video (1-{len(videos) + 1}): ")
        
        if choice == str(len(videos) + 1) or choice.lower() == 'all':
            print("\nYou selected all videos. You'll choose quality settings for each video.")
            successCount = 0
            for video in videos:
                qualityMode, targetSize = getQualitySettings(video)
                if extractAudio(video, audioFolder, qualityMode, targetSize):
                    successCount += 1
            print(f"\nFinished! Extracted {successCount}/{len(videos)} files")
        else:
            #extract one
            try:
                index = int(choice) - 1
                if 0 <= index < len(videos):
                    qualityMode, targetSize = getQualitySettings(videos[index])
                    extractAudio(videos[index], audioFolder, qualityMode, targetSize)
                else:
                    print("Invalid number")
            except ValueError:
                print("Please enter a valid number")

if __name__ == "__main__":
    main()