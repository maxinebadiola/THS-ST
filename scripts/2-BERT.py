import re
import torch
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from sentence_transformers import SentenceTransformer, util

input_txt = "THS-ST/output/transcript.txt"
output_scores = "THS-ST/output/scored_transcript.txt"

with open(input_txt, "r", encoding="utf-8") as f:
    transcript = f.read()

sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s', transcript)
sentences = [s.strip() for s in sentences if s.strip()]

model = SentenceTransformer('all-mpnet-base-v2', device='cuda') #GPU
embeddings = model.encode(sentences, convert_to_tensor=True)
avg_embedding = torch.mean(embeddings, dim=0)

cos_scores = util.pytorch_cos_sim(embeddings, avg_embedding.unsqueeze(0)).squeeze()
scaled_scores = MinMaxScaler().fit_transform(cos_scores.cpu().numpy().reshape(-1, 1)).flatten()

with open(output_scores, "w", encoding="utf-8") as f:
    for sent, score in zip(sentences, scaled_scores):
        f.write(f"{score:.4f} {sent}\n")

print("scored_transcript.txt created successfully.")
