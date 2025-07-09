import os
import subprocess
import platform
from pathlib import Path

def getYtDlpPath(videoFolder):
    system = platform.system().lower()
    
    if system == "windows":
        ytDlpPath = videoFolder / "yt-dlp.exe"
    elif system == "linux":
        ytDlpPath = videoFolder / "yt-dlp_linux" 
    return ytDlpPath

def addCustomVideo():
    print("\n" + "=" * 50)
    print("ADD CUSTOM VIDEO")
    print("=" * 50)
    
    url = input("Enter YouTube URL: ").strip()
    if not url:
        print("No URL entered. Returning to main menu.")
        return None

    here = Path(__file__).parent
    videoFolder = here / "../video"
    ytDlpPath = getYtDlpPath(videoFolder)
    
    try:
        print("Getting video title...")
        cmd = [str(ytDlpPath), url, '--get-title']
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(videoFolder))
        
        if result.returncode == 0:
            title = result.stdout.strip()
            print(f"Video title: {title}")
            
            useTitle = input("Use this title as filename? (y/n): ").strip().lower()
            if useTitle == 'y':
                filename = cleanFilename(title)
            else:
                filename = input("Enter custom filename (without extension): ").strip()
                if not filename:
                    filename = cleanFilename(title)
            
            return {
                "title": title,
                "url": url,
                "filename": filename
            }
        else:
            print(f"Could not get video title. Error: {result.stderr.strip()}")
            title = input("Enter video title: ").strip()
            filename = input("Enter filename (without extension): ").strip()
            
            if not title:
                title = "Custom Video"
            if not filename:
                filename = "custom_video"
            
            return {
                "title": title,
                "url": url,
                "filename": filename
            }
            
    except Exception as e:
        print(f"Error getting video info: {e}")
        title = input("Enter video title: ").strip()
        filename = input("Enter filename (without extension): ").strip()
        
        if not title:
            title = "Custom Video"
        if not filename:
            filename = "custom_video"
        
        return {
            "title": title,
            "url": url,
            "filename": filename
        }

def cleanFilename(title):
    """Clean video title to make it suitable as filename"""
    clean = ""
    for char in title:
        if char.isalnum() or char in ' -_':
            clean += char
        elif char in '()[]{}':
            clean += '_'
    clean = ' '.join(clean.split())
    return clean.strip()

##TEST VIDEOS
def main():
    videos = [
        {
            "title": "There's more to those colliding blocks that compute pi [3Blue1Brown]",
            "url": "https://youtu.be/6dTyOl1fmDo?si=A5E87Cw4l9DJzgD1",
            "filename": "Compute Pi"
        },
        {
            "title": "The Dark Side of Science: The Robbers Cave Experiment 1954 [Plainly Difficult]",
            "url": "https://youtu.be/FLmHfwkMAaU?si=NMXmq7oOIv_MrHZ1",
            "filename": "Robbers Cave Experiment"
        },
        {
            "title": "Why Was Black Saturday So Deadly? [Plainly Difficult]",
            "url": "https://youtu.be/aCZixBrrGrs?si=1dIQhXquVlAVLfF_",
            "filename": "Why Was Black Saturday So Deadly"
        }
    ]
    
    here = Path(__file__).parent
    videoFolder = here / "../video"
    ytDlpPath = getYtDlpPath(videoFolder)
    
    if not ytDlpPath.exists():
        system = platform.system().lower()
        if system == "windows":
            expected_name = "yt-dlp.exe"
        elif system == "linux":
            expected_name = "yt-dlp_linux"
        else:
            expected_name = "yt-dlp"
        print(f"ERROR: {expected_name} not found at {ytDlpPath}")
        print(f"Please download yt-dlp for {system.title()} and place it in the video folder.")
        return
    
    videoFolder.mkdir(exist_ok=True)
    
    while True:
        print("\nAvailable videos for download:")
        print("=" * 50)
        for i, video in enumerate(videos, 1):
            print(f"{i}. {video['title']}")
        print("=" * 50)
        
        print("\nOptions:")
        print(f"a. Input video numbers (e.g. 1 or 1,2) or 'all'")
        print(f"b. Input '{len(videos) + 1}' to download new video")
        
        selection = input(f"\nInput: ").strip().lower()
        
        if selection == str(len(videos) + 1) or selection == 'add':
            customVideo = addCustomVideo()
            if customVideo:
                videos.append(customVideo)
                print(f"✓ Added: {customVideo['title']}")
            continue
        
        if selection == 'all':
            selectedVideos = videos
            break
        elif selection == '':
            print("Please enter a selection.")
            continue
        else:
            try:
                if ',' in selection:
                    indices = [int(x.strip()) for x in selection.split(',')]
                else:
                    indices = [int(selection)]
                
                selectedVideos = []
                for idx in indices:
                    if 1 <= idx <= len(videos):
                        selectedVideos.append(videos[idx - 1])
                    else:
                        print(f"Invalid video number: {idx}. Please use numbers 1-{len(videos)}")
                        selectedVideos = None
                        break
                
                if selectedVideos is not None:
                    break
                    
            except ValueError:
                print("Invalid input. Please enter numbers separated by commas, 'all', or a single number.")
                continue
    
    if not selectedVideos:
        print("No videos selected.")
        return
    
    print(f"\nDownloading {len(selectedVideos)} video(s)...")
    print("=" * 50)
    
    successCount = 0
    for video in selectedVideos:
        print(f"\nDownloading: {video['title']}")
        
        # Check if file already exists
        outputFileMp4 = videoFolder / f"{video['filename']}.mp4"
        outputFileMkv = videoFolder / f"{video['filename']}.mkv"
        
        if outputFileMp4.exists() or outputFileMkv.exists():
            existingFile = outputFileMp4 if outputFileMp4.exists() else outputFileMkv
            overwrite = input(f"'{existingFile.name}' already exists. Overwrite? (y/n): ").strip().lower()
            if overwrite != 'y':
                print("Skipping...")
                continue
        
        cmd = [
            str(ytDlpPath),
            video['url'],
            '-f', 'best[ext=mp4]/best[ext=mkv]/best',  #mp4 -> mkv -> best available
            '-o', str(videoFolder / f"{video['filename']}.%(ext)s"),  
            '--no-playlist' 
        ]
        
        try:
            print(f"Running: yt-dlp for {video['filename']}")
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(videoFolder))
            
            if result.returncode == 0:
                downloadedFile = None
                for ext in ['mp4', 'mkv']:
                    potentialFile = videoFolder / f"{video['filename']}.{ext}"
                    if potentialFile.exists():
                        downloadedFile = potentialFile
                        break
                
                if downloadedFile:
                    print(f"✓ Successfully downloaded: {downloadedFile.name}")
                    successCount += 1
                else:
                    print(f"✓ Download completed but file not found with expected name")
                    successCount += 1
            else:
                print(f"✗ Failed to download: {video['filename']}")
                print(f"Error: {result.stderr.strip()}")
                
        except Exception as e:
            print(f"✗ Error downloading {video['filename']}: {e}")
    
    print("\n" + "=" * 50)
    print(f"Download complete! Successfully downloaded {successCount}/{len(selectedVideos)} videos.")
    

if __name__ == "__main__":
    main()