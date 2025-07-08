import re
import subprocess
import sys
from pathlib import Path

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install"] + package.split())

try:
    import torch
    import numpy as np
    from sklearn.preprocessing import MinMaxScaler
    from sentence_transformers import SentenceTransformer, util
except ImportError as e:
    missing = str(e).split("'")[1]
    if missing == "torch":
        install("torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu")
    elif missing == "sentence_transformers":
        install("sentence-transformers")
    elif missing == "sklearn":
        install("scikit-learn")
    else:
        install(missing)
    import torch
    import numpy as np
    from sklearn.preprocessing import MinMaxScaler
    from sentence_transformers import SentenceTransformer, util

def selectModel():
    """Let user select which sentence transformer model to use"""
    print("\nSelect BERT model:")
    print("=" * 30)
    print("1. all-mpnet-base-v2")
    print("2. all-roberta-large-v1")
    print("3. New Model")
    print("4. 'all")
    print("=" * 30)
    
    while True:
        choice = input("Select model (1-3 or 'all'): ").strip().lower()
        
        if choice == '1':
            return ['all-mpnet-base-v2']
        elif choice == '2':
            return ['all-roberta-large-v1']
        elif choice == '3':
            customModel = input("Enter model name: ").strip()
            if customModel:
                return [customModel]
            else:
                print("Please enter a model name.")
        elif choice == '4' or choice == 'all':
            return ['all-mpnet-base-v2', 'all-roberta-large-v1']
        else:
            print("Please enter 1, 2, 3, or 'all'.")

def findTranscriptFiles(folder):
    """Find all transcript files in the folder"""
    transcriptFiles = []
    for pattern in ['*transcript.txt', '*_transcript.txt']:
        transcriptFiles.extend(folder.glob(pattern))
    return sorted(transcriptFiles)

def scoreTranscript(transcriptFile, outputFolder, modelName):
    """Score transcript sentences using BERT similarity"""
    baseName = transcriptFile.stem
    # Remove _transcript or transcript (case-insensitive) from end if present
    if baseName.lower().endswith('_transcript'):
        baseName = baseName[:-11]
    elif baseName.lower().endswith('transcript'):
        baseName = baseName[:-10]
    # Clean model name for filename
    modelNameClean = modelName.replace('-', '_').replace('.', '_')
    scoredName = f"{baseName}_{modelNameClean}_scores.txt"
    scoredFile = outputFolder / scoredName
    
    print(f"Working on: {transcriptFile.name}")
    print(f"Using model: {modelName}")

    if scoredFile.exists():
        answer = input(f"'{scoredName}' exists. Replace it? (y/n): ")
        if answer.lower() != 'y':
            print("Skipping...")
            return False
    
    try:
        with open(transcriptFile, "r", encoding="utf-8") as f:
            transcript = f.read()
        
        sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s', transcript)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            print("✗ Error: transcript empty")
            return False
        print(f"Processing {len(sentences)} sentences with BERT...")
        try:
            model = SentenceTransformer(modelName, device='cuda')
        except Exception as e:
            print(f"✗ Error loading model '{modelName}': {e}")
            print("Reverting to CPU or default model...")
            try:
                model = SentenceTransformer(modelName, device='cpu')
            except Exception as e2:
                print(f"✗ Failed to load model: {e2}")
                return False
        
        embeddings = model.encode(sentences, convert_to_tensor=True)
        avgEmbedding = torch.mean(embeddings, dim=0)
        cosScores = util.pytorch_cos_sim(embeddings, avgEmbedding.unsqueeze(0)).squeeze()
        scaledScores = MinMaxScaler().fit_transform(cosScores.cpu().numpy().reshape(-1, 1)).flatten()
        with open(scoredFile, "w", encoding="utf-8") as f:
            for sent, score in zip(sentences, scaledScores):
                f.write(f"{score:.4f} {sent}\n")
        
        print(f"✓ Saved: {scoredName}")
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def main():
    here = Path(__file__).parent
    outputFolder = here / "../output"
    
    if not outputFolder.exists():
        print(f"Can't find output folder: {outputFolder}")
        return
    
    transcriptFiles = findTranscriptFiles(outputFolder)
    if not transcriptFiles:
        print("No transcript files found")
        return
    
    selectedModels = selectModel()
    print(f"\nSelected model(s): {', '.join(selectedModels)}")

    print(f"\nFound {len(transcriptFiles)} transcript file(s):")
    for i, transcript in enumerate(transcriptFiles, 1):
        print(f"  {i}. {transcript.name}")
    
    print(f"  {len(transcriptFiles) + 1}. All transcripts")
    choice = input(f"\nSelect: (1-{len(transcriptFiles) + 1}): ").strip().lower()
    
    if choice == str(len(transcriptFiles) + 1) or choice == 'all':
        successCount = 0
        for model in selectedModels:
            for transcript in transcriptFiles:
                if scoreTranscript(transcript, outputFolder, model):
                    successCount += 1
        print(f"\nDone! Scored {successCount} transcript(s) with {', '.join(selectedModels)}")
    else:
        try:
            index = int(choice) - 1
            if 0 <= index < len(transcriptFiles):
                for model in selectedModels:
                    scoreTranscript(transcriptFiles[index], outputFolder, model)
            else:
                print("Invalid number")
        except ValueError:
            print("Please enter a number")

if __name__ == "__main__":
    main()
