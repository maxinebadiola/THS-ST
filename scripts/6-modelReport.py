#!/usr/bin/env python3
"""
Model Performance Report Generator
===================================

This script analyzes the performance of different language models across all video title scoring results.
It generates a comprehensive report showing metrics like average scores, penalty frequencies, and
top-scoring title counts for each model.

Usage:
    python scripts/6-modelReport.py

Output:
    output/reports/model_performance_report.txt
"""

import os
import pandas as pd
import numpy as np
import glob
from pathlib import Path
from collections import defaultdict
import re


def parse_malformed_csv(path: Path):
    """Heuristic parser for malformed *_scores_3.csv files.

    Returns a pandas.DataFrame with columns: model, title, avg_score, penalty
    when it can recover rows. Conservative and best-effort.
    """
    text = path.read_text(encoding='utf-8', errors='replace')

    # Remove comment/header lines starting with '#'
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith('#')]
    if not lines:
        return pd.DataFrame()

    combined = ' '.join(lines)

    # Pattern: start of a record looks like: <int>,<int>,<HH:MM>,
    record_re = re.compile(r'(\d+,\d+,\d{1,2}:\d{2},.*?)(?=\s+\d+,\d+,\d{1,2}:\d{2},|\Z)', re.S)

    rows = []
    for m in record_re.finditer(combined):
        rec = m.group(1).strip()
        # Split off the first three fields (id, num, time)
        parts = rec.split(',', 3)
        if len(parts) < 4:
            continue
        rest = parts[3]
        # The model is the first token of rest, title (possibly with commas)
        # follows. Use partition to safely split only on the first comma.
        model, sep, title_rest = rest.partition(',')
        if not sep:
            continue

        # Find first float in title_rest to detect where title ends and
        # numeric fields begin.
        float_match = re.search(r'[-+]?\d*\.\d+|\d+', title_rest)
        if float_match:
            fpos = float_match.start()
            title = title_rest[:fpos].strip().strip('"')
            nums_text = title_rest[fpos:]
        else:
            title = title_rest.strip().strip('"')
            nums_text = ''

        nums = re.findall(r'[-+]?\d*\.\d+|\d+', nums_text)
        if not nums:
            # If we couldn't find numeric fields, skip this record
            continue

        # Convert to floats when possible
        try:
            numsf = [float(x) for x in nums]
        except Exception:
            continue

        avg_score = numsf[0] if len(numsf) >= 1 else None
        penalty = numsf[1] if len(numsf) >= 2 else None

        rows.append({'model': model.strip(), 'title': title, 'avg_score': avg_score, 'penalty': penalty})

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)

def main():
    # Define paths
    reports_dir = Path("output/reports")
    output_file = reports_dir / "model_performance_report.txt"

    # Ensure reports directory exists
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Find all score CSV files (initial glob for *_scores_*.csv)
    all_score_files = glob.glob(str(reports_dir / "*_scores_*.csv"))

    # Filter to only those CSVs whose filename ends with '_3.csv'
    score_files = [p for p in all_score_files if p.endswith('_3.csv')]

    if not all_score_files:
        print("No score CSV files found in output/reports/")
        return

    if not score_files:
        print(f"Found {len(all_score_files)} score files but none end with '_3.csv'.")
        return

    print(f"Found {len(score_files)} score files to process (filtered to *_3.csv)...")

    # Collect all data
    all_data = []
    top_counts = defaultdict(int)
    best_counts = defaultdict(int)
    top5_counts = defaultdict(int)
    penalty_counts = defaultdict(lambda: {'total': 0, 'penalties': 0})
    scores_list = defaultdict(list)

    for file_path in score_files:
        # Extract video name from filename
        filename = Path(file_path).name
        video_name = filename.split('_scores_')[0]

        # Read CSV
        try:
            df = pd.read_csv(file_path, sep=',', quotechar='"', escapechar='\\', on_bad_lines='skip')
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            continue

        if df.empty:
            continue

        # If pandas couldn't parse proper columns, try a salvage parser.

    # Normalize and validate columns. Some score CSVs are malformed or use
        # capitalized/whitespace-padded headers. Try to map common headers to
        # the lower-case names used by this script. If required columns are
        # missing, skip the file (log a message) instead of crashing.
        df.columns = [str(c).strip() for c in df.columns]
        col_map = {c.lower(): c for c in df.columns}
        required = ['model', 'avg_score', 'penalty']
        if not all(r in col_map for r in required):
            # Try a conservative salvage parser for malformed files
            try:
                salvaged = parse_malformed_csv(Path(file_path))
            except Exception as e:
                salvaged = None

            if salvaged is None or salvaged.empty:
                print(f"Skipping {file_path}: missing required columns. Columns found: {df.columns.tolist()}")
                continue

            # use salvaged dataframe
            df = salvaged
            # ensure columns normalized
            df.columns = [str(c).strip() for c in df.columns]
            col_map = {c.lower(): c for c in df.columns}

        # Build a rename map to normalize column names to the lower-case
        # identifiers the rest of the script expects.
        rename_map = {col_map[r]: r for r in required if r in col_map}
        for opt in ['title', 'segment', 'video']:
            if opt in col_map:
                rename_map[col_map[opt]] = opt

        if rename_map:
            df = df.rename(columns=rename_map)

        # Add video column
        df['video'] = video_name

        # Ensure expected columns exist with safe defaults so grouping/metrics
        # don't fail when salvaged data is partial.
        for _col in ['segment', 'title', 'model', 'avg_score', 'penalty']:
            if _col not in df.columns:
                if _col == 'segment':
                    df['segment'] = 0
                elif _col == 'title':
                    df['title'] = ''
                elif _col == 'model':
                    df['model'] = 'unknown'
                else:
                    df[_col] = np.nan

        # Coerce numeric columns
        df['avg_score'] = pd.to_numeric(df['avg_score'], errors='coerce')
        df['penalty'] = pd.to_numeric(df['penalty'], errors='coerce')

        # Process each row
        for _, row in df.iterrows():
            model = row['model']
            avg_score = row['avg_score']
            penalty = row['penalty']

            # Accumulate scores
            scores_list[model].append(avg_score)

            # Count penalties
            penalty_counts[model]['total'] += 1
            if penalty < 1.0:
                penalty_counts[model]['penalties'] += 1

        # Find top scoring titles per segment (including ties)
        segment_groups = df.groupby(['video', 'segment'])
        for (video, segment), group in segment_groups:
            if group.empty:
                continue

            # Find the maximum score in this segment
            max_score = group['avg_score'].max()

            # Find all models that achieved this max score (handle ties)
            top_models = group[group['avg_score'] == max_score]['model'].unique()

            # Count each top model
            for model in top_models:
                top_counts[model] += 1

        # Find best and top 5 titles per segment (excluding duplicates)
        for (video, segment), group in segment_groups:
            if group.empty:
                continue

            # Group by title to get unique titles with their max scores
            title_max_scores = group.groupby('title')['avg_score'].max().reset_index()

            # Sort by score descending
            title_max_scores = title_max_scores.sort_values('avg_score', ascending=False)

            # Get top titles (up to 5)
            top_titles = title_max_scores.head(5)

            # Best title
            if not top_titles.empty:
                best_title = top_titles.iloc[0]['title']
                # Find which model(s) generated this title
                best_models = group[group['title'] == best_title]['model'].unique()
                for model in best_models:
                    best_counts[model] += 1

            # Top 5 titles
            for _, row in top_titles.iterrows():
                title = row['title']
                top5_models = group[group['title'] == title]['model'].unique()
                for model in top5_models:
                    top5_counts[model] += 1

        all_data.append(df)

    if not all_data:
        print("No valid data found in CSV files.")
        return

    # Combine all data
    combined_df = pd.concat(all_data, ignore_index=True)

    # Calculate metrics
    models = sorted(set(scores_list.keys()) | set(top_counts.keys()) | set(best_counts.keys()) | set(top5_counts.keys()) | set(penalty_counts.keys()))

    # Generate report
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("MODEL PERFORMANCE REPORT\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"Total videos processed: {len(set(combined_df['video']))}\n")
        f.write(f"Total segments analyzed: {len(combined_df.groupby(['video', 'segment']))}\n")
        f.write(f"Total titles evaluated: {len(combined_df)}\n")
        f.write(f"Models evaluated: {len(models)}\n\n")

        f.write("-" * 80 + "\n")
        f.write("PER-MODEL PERFORMANCE METRICS\n")
        f.write("-" * 80 + "\n\n")

        # Header
        f.write(f"{'Model':<20} {'Avg Score':<12} {'Median':<10} {'Titles':<8} {'Penalty %':<10} {'Top Seg':<10} {'Best Seg':<10} {'Top5 Seg':<10}\n")
        f.write("-" * 90 + "\n")

        total_segments = len(combined_df.groupby(['video', 'segment']))

        for model in models:
            scores = scores_list[model]
            avg_score = np.mean(scores) if scores else 0.0
            median_score = np.median(scores) if scores else 0.0
            total_titles = penalty_counts[model]['total']
            penalty_pct = (penalty_counts[model]['penalties'] / total_titles * 100) if total_titles > 0 else 0.0
            top_segments = top_counts[model]
            best_segments = best_counts[model]
            top5_segments = top5_counts[model]

            f.write(f"{model:<20} {avg_score:<12.4f} {median_score:<10.4f} {total_titles:<8} {penalty_pct:<10.1f} {top_segments:<10} {best_segments:<10} {top5_segments:<10}\n")

        f.write("\n" + "=" * 80 + "\n")
        f.write("DETAILED ANALYSIS\n")
        f.write("=" * 80 + "\n\n")

        # Model ranking by average score
        f.write("MODELS RANKED BY AVERAGE SCORE\n")
        f.write("-" * 40 + "\n")
        model_scores = [(model, np.mean(scores_list[model])) for model in models if scores_list[model]]
        model_scores.sort(key=lambda x: x[1], reverse=True)

        for rank, (model, score) in enumerate(model_scores, 1):
            f.write(f"{rank:2d}. {model:<18} {score:.4f}\n")

        f.write("\n")

        # Model ranking by median score
        f.write("MODELS RANKED BY MEDIAN SCORE\n")
        f.write("-" * 40 + "\n")
        model_medians = [(model, np.median(scores_list[model])) for model in models if scores_list[model]]
        model_medians.sort(key=lambda x: x[1], reverse=True)

        for rank, (model, median) in enumerate(model_medians, 1):
            f.write(f"{rank:2d}. {model:<18} {median:.4f}\n")

        f.write("\n")

        # Model ranking by best segment frequency
        f.write("MODELS RANKED BY BEST TITLE FREQUENCY\n")
        f.write("-" * 40 + "\n")
        model_bests = [(model, best_counts[model]) for model in models]
        model_bests.sort(key=lambda x: x[1], reverse=True)

        for rank, (model, count) in enumerate(model_bests, 1):
            pct = (count / total_segments * 100) if total_segments > 0 else 0.0
            f.write(f"{rank:2d}. {model:<18} {count:3d} ({pct:.1f}%)\n")

        f.write("\n")

        # Model ranking by top 5 frequency
        f.write("MODELS RANKED BY TOP 5 FREQUENCY\n")
        f.write("-" * 40 + "\n")
        model_top5s = [(model, top5_counts[model]) for model in models]
        model_top5s.sort(key=lambda x: x[1], reverse=True)

        for rank, (model, count) in enumerate(model_top5s, 1):
            pct = (count / total_segments * 100) if total_segments > 0 else 0.0
            f.write(f"{rank:2d}. {model:<18} {count:3d} ({pct:.1f}%)\n")

        f.write("\n")

        # Penalty analysis
        f.write("PENALTY ANALYSIS\n")
        f.write("-" * 20 + "\n")
        total_penalties = sum(p['penalties'] for p in penalty_counts.values())
        total_titles_all = sum(p['total'] for p in penalty_counts.values())
        overall_penalty_pct = (total_penalties / total_titles_all * 100) if total_titles_all > 0 else 0.0

        f.write(f"Overall penalty rate: {overall_penalty_pct:.1f}%\n")
        f.write(f"Titles with penalties: {total_penalties}\n")
        f.write(f"Total titles: {total_titles_all}\n\n")

        # Models with lowest penalty rates
        f.write("MODELS WITH LOWEST PENALTY RATES\n")
        f.write("-" * 35 + "\n")
        penalty_rates = [(model, penalty_counts[model]['penalties'] / penalty_counts[model]['total'] * 100)
                        for model in models if penalty_counts[model]['total'] > 0]
        penalty_rates.sort(key=lambda x: x[1])

        for model, rate in penalty_rates[:5]:  # Top 5 lowest
            f.write(f"{model:<18} {rate:.1f}%\n")

    print(f"Report generated: {output_file}")

if __name__ == "__main__":
    main()
