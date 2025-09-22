import re
import pandas as pd
from IPython.display import display

#files
timestamps_path = "output/timestamps.txt"
scores_path = "output/scored_transcript.txt"
output_csv = "output/scores/_bert_output.csv"

#load and clean timestamps
with open(timestamps_path, 'r', encoding='utf-8') as f:
    timestamp_lines = [line.strip() for line in f if line.strip()]  # Remove empty lines

print(f"{len(timestamp_lines)} timestamp lines loaded")

timestamp_data = []
timestamp_pattern = re.compile(r'\[(.*?) --> (.*?)\] (.+)')

for line in timestamp_lines:
    match = timestamp_pattern.match(line)
    if match:
        start, end, text = match.groups()
        timestamp_data.append((text.strip(), float(start), float(end)))

#load and clean bert scores
with open(scores_path, 'r', encoding='utf-8') as f:
    score_lines = [line.strip() for line in f if line.strip()]  # Remove empty lines

print(f"{len(score_lines)} scored lines loaded")

score_data = []
score_pattern = re.compile(r'^(\d+\.\d+) (.+)$')

for line in score_lines:
    match = score_pattern.match(line)
    if match:
        score, text = match.groups()
        score_data.append((text.strip(), float(score)))

#match + merge
combined = []
text_to_timestamp = {text: (start, end) for text, start, end in timestamp_data}

for text, score in score_data:
    if text in text_to_timestamp:
        start, end = text_to_timestamp[text]
        combined.append((score, start, end, text))

#EXPORT to .csv
df = pd.DataFrame(combined, columns=["score", "start", "end", "transcript"]) #values
df.to_csv(output_csv, index=False)

print(f"\Saved to {output_csv}")
display(df.head())
print(f"\Total rows in CSV: {len(df)}")
