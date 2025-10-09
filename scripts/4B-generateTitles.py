#!/usr/bin/env python3
# for RTX 4090 24GB VRAM Runpod

#FIRST go to repo file:
# cd /root/THS-ST 
# python scripts/generateTitles.py
# python scripts/generateTitles.py --menu
# #TO REMOVE GENERATED TITLES:
# rm -f output/llm_generated/batch/

import os
import json
import csv
import gc
import time
import argparse
# import threading  
# import sys
# import select
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta
import warnings
warnings.filterwarnings('ignore')

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from dotenv import load_dotenv
# import google.generativeai as genai  # COMMENTED OUT


class TitleGenerator:
    
    #TERMINAL COLOURS
    RED = '\033[91m'
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    ORANGE = '\033[33m'
    RESET = '\033[0m'
    
    def __init__(self, use_gemini: bool = False):
        """
        Initialize the title generator.
        
        Args:
            use_gemini: Whether to include Gemini API model
        """
        self.use_gemini = use_gemini
        
        # MANDATORY GPU CHECK - SHUTDOWN IF NO GPU
        if not torch.cuda.is_available():
            print(f"{self.RED} (CRITICAL ERROR): NO GPU DETECTED!{self.RESET}")
            print(f"{self.RED}This script requires GPU for performance. Shutting down...{self.RESET}")
            import sys
            sys.exit(1)
        
        # Force CUDA - GPU is mandatory
        self.device = "cuda"
        gpu_name = torch.cuda.get_device_name()
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"[INFO] GPU LOCKED: {gpu_name} ({gpu_memory:.1f}GB VRAM)")
        
        # Additional GPU verification
        try:
            torch.cuda.empty_cache()
            test_tensor = torch.tensor([1.0]).cuda()
            del test_tensor
            print(f"[PASS] GPU functionality verified")
        except Exception as e:
            print(f"{self.RED}[FAIL] GPU VERIFICATION FAILED: {e}{self.RESET}")
            print(f"{self.RED}Shutting down script...{self.RESET}")
            import sys
            sys.exit(1)
            
        self.models_config = self._get_models_config()
        # self.paused = False  # COMMENTED OUT
        # self.should_quit = False  # COMMENTED OUT
        
        # Philippine timezone (UTC+8)
        self.ph_tz = timezone(timedelta(hours=8))
        
        # Setup API key if using Gemini - COMMENTED OUT
        # if self.use_gemini:
        #     self._setup_gemini_api()
        
        print(f"TitleGenerator initialized with device: {self.device}")
        print(f"Models to use: {list(self.models_config.keys())}")
        # if self.use_gemini:  # COMMENTED OUT
        #     print("Gemini API enabled")
    
    def _get_ph_timestamp(self) -> str:
        """Get current timestamp in Philippine timezone."""
        return datetime.now(self.ph_tz).strftime("%d/%m/%y %H:%M:%S")
    
    def _get_char_count_color(self, char_count: int) -> str:
        """Get color code based on character count."""
        if char_count < 100:  # Too little
            return self.RED
        elif char_count < 1000:  # Good amount
            return self.GREEN
        elif char_count < 5000:  # Nearing big amount
            return self.ORANGE
        else:  # A lot
            return self.RED
    
    # def _check_pause_quit(self):  # COMMENTED OUT
    #     """Check for pause/quit commands."""
    #     while self.paused and not self.should_quit:
    #         time.sleep(0.1)
    #     if self.should_quit:
    #         print(f"\n{self.RED}[WARNING]{self.RESET} Process interrupted by user!")
    #         raise KeyboardInterrupt("User requested quit")
    
    def _get_models_config(self) -> Dict[str, str]:
        """Get configuration for local models."""
        config = {
            "qwen2-1.5b": "Qwen/Qwen2-1.5B-Instruct", 
            "tinyllama": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
            # "gpt2-medium": "gpt2-medium",  # DISABLED: Generates very long rambling titles
            # "distilgpt2": "distilgpt2",    # DISABLED: Generates very short generic titles
            # "bloom-560m": "bigscience/bloom-560m"  # DISABLED: Generates poor quality titles
        }
        
        # if self.use_gemini:  # COMMENTED OUT
        #     config["gemini-flash"] = "gemini-2.0-flash-exp"
            
        return config
    
    # def _setup_gemini_api(self):  # COMMENTED OUT
    #     """Setup Gemini API using environment variables."""
    #     try:
    #         load_dotenv()
    #         api_key = os.getenv('GEMINI_API_KEY')
    #         if not api_key:
    #             raise ValueError("GEMINI_API_KEY not found in environment variables")
    #         
    #         genai.configure(api_key=api_key)
    #         self.gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')
    #         print("Gemini API configured successfully")
    #     except Exception as e:
    #         print(f"{self.RED}[ERROR]{self.RESET} Failed to setup Gemini API: {e}")
    #         self.use_gemini = False
    
    def _load_model(self, model_name: str, model_path: str) -> tuple:
        """
        Load a single model with optimized settings for RTX 4090.
        
        Args:
            model_name: Short name for the model
            model_path: HuggingFace model path
            
        Returns:
            Tuple of (tokenizer, model)
        """
        print(f"\nLoading {model_name} ({model_path})...")
        
        try:
            # Load tokenizer
            tokenizer = AutoTokenizer.from_pretrained(
                model_path, 
                trust_remote_code=True,
                padding_side="left"
            )
            
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
            
            # NOTE: NOquantization, native bfloat16
            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=torch.bfloat16,  # Native precision for RTX 4090  
                device_map="auto",
                trust_remote_code=True,
                load_in_4bit=False,  # No quantization with 24GB VRAM
                attn_implementation="flash_attention_2" if "flash" in model_path.lower() else None
            )
            
            model.eval()
            print(f"{self.GREEN}[PASS]{self.RESET} {model_name} loaded successfully")
            return tokenizer, model
            
        except Exception as e:
            print(f"{self.RED}[FAIL]{self.RESET} Failed to load {model_name}: {e}")
            return None, None
    
    def _unload_model(self, tokenizer, model):
        """Properly unload model and free GPU memory."""
        if model is not None:
            del model
        if tokenizer is not None:
            del tokenizer
        
        #CLEAN memory 
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
    
    def _create_prompt(self, transcript: str) -> str:
        cleaned_transcript = transcript.strip()
        
        prompt = f"""Create an engaging chapter title for this transcript. Be descriptive and creative.

Transcript: {cleaned_transcript}

REQUIREMENTS:
- Complete sentence or phrase only
- NO cut-off or incomplete words
- Summarize the core topic precisely
- Use clear, engaging language
- End with proper completion
- Output ONLY the title, nothing else

Title:"""
        return prompt
    
    def _generate_title_with_retry(self, tokenizer, model, prompt: str, model_name: str, max_retries: int = 10) -> str:
        """Generate title with retry logic for failures."""
        for attempt in range(max_retries):
            # Add variation in temperature for retries to get different results
            retry_temp_boost = attempt * 0.1  # Increase temperature for each retry
            title = self._generate_with_local_model(tokenizer, model, prompt, model_name, 
                                                  show_warnings=(attempt == 0), 
                                                  retry_attempt=attempt, 
                                                  temperature_boost=retry_temp_boost)
            
            # Check if title generation failed - more strict detection
            title_words = title.strip().split()
            title_failed = (
                title.startswith("Generated Title") or 
                title.startswith("Error Title") or 
                len(title.strip()) < 5 or  # More strict minimum length
                title.strip().lower() in ["sand", "generated", "title", "content", "chapter"] or
                "human" in title.lower() or  # Catch artifacts like "Human"
                len(title_words) < 3 or  # Titles should have at least 3 words
                title.strip() == "" or   # Empty titles
                title.endswith("...") or title.endswith("..") or  # Truncated titles
                any(word.lower() in ["and", "the", "of", "to", "a", "an", "with"] for word in [title_words[-1]] if title_words)  # Incomplete endings
            )
            
            if title_failed:
                if attempt == 0:  # Only show detailed info on first attempt
                    title_preview = title[:50] + ('...' if len(title) > 50 else '')
                    print(f"  {self.YELLOW}[RETRY]{self.RESET} Title generation issue: '{title_preview}'")
                
                if attempt == max_retries - 1:  # Last attempt
                    # Create emergency fallback title based on content length
                    words = prompt.split()[:50]  # Get first 50 words for context
                    content_words = [w for w in words if len(w) > 3 and w.isalpha()][:3]
                    if content_words:
                        fallback_title = f"Discussion on {' '.join(content_words)}"
                    else:
                        fallback_title = f"Content Analysis Chapter"
                    if attempt == 0:
                        print(f"  {self.ORANGE}[FALLBACK]{self.RESET} Using emergency title: '{fallback_title}'")
                    return fallback_title
                    
                # Add extra wait time for long prompts - VERY generous
                if len(prompt) > 4000:
                    time.sleep(5)  # Very generous time for very long prompts
                elif len(prompt) > 2000:
                    time.sleep(3)  # Generous time for long prompts
                continue  # Retry
            else:
                return title  # Success
        
        return "FAILURE"
    
    def _monitor_input(self):
        """Monitor for user input to pause/quit the process."""
        print(f"\n{self.YELLOW}[CONTROLS]{self.RESET} Type 'p' + Enter to pause, 'q' + Enter to quit, 'r' + Enter to resume")
        print("=" * 70)
        
        while not self.should_quit:
            try:
                user_input = input().strip().lower()
                if user_input == 'p':
                    self.paused = True
                    print(f"{self.YELLOW}[PAUSE]{self.RESET} Process PAUSED. Type 'r' to resume or 'q' to quit.")
                elif user_input == 'r':
                    self.paused = False
                    print(f"{self.GREEN}[RESUME]{self.RESET} Process RESUMED.")
                elif user_input == 'q':
                    self.should_quit = True
                    print(f"{self.RED}[QUIT]{self.RESET} Quitting process...")
                    break
            except (EOFError, KeyboardInterrupt):
                break
            except Exception as e:
                print(f"{self.RED}[ERROR]{self.RESET} Input monitoring error: {e}")
    
    def _generate_with_local_model(self, tokenizer, model, prompt: str, model_name: str, show_warnings: bool = True, retry_attempt: int = 0, temperature_boost: float = 0.0) -> str:
        """
        Generate title using a local model.
        
        Args:
            tokenizer: Model tokenizer
            model: Loaded model
            prompt: Input prompt
            model_name: Model identifier
            show_warnings: Whether to show debug warnings
            retry_attempt: Current retry attempt number (for variation)
            temperature_boost: Additional temperature boost for retries
            
        Returns:
            Generated title string
        """
        try:
            # Tokenize input
            inputs = tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=2048,  # Increased to handle longer prompts
                padding=True
            ).to(self.device)
            
            # Check token count and show warning only once
            token_count = inputs['input_ids'].shape[1]
            if token_count > 900 and show_warnings:
                print(f"  {self.YELLOW}[INFO]{self.RESET} High token count ({token_count}) | Will require extra processing time...")
            
            # Generate with optimized parameters
            # Add extra time for high token count prompts - VERY generous timing
            if token_count > 900:
                time.sleep(3)  # Very generous processing time
            elif len(prompt) > 2000:
                time.sleep(2)  # Extra time for long prompts
            
            # TODO: Solution for lengthy titles - consider implementing title length validation and truncation
            # Removed token restrictions to allow more varied title generation
            max_new_tokens = 100  # Increased from 25 to allow more creative and complete titles
            
            # Adjust temperature for retry attempts to get more variation
            base_temperature = 0.4
            adjusted_temperature = min(0.9, base_temperature + temperature_boost)  # Cap at 0.9
            
            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    temperature=adjusted_temperature,  # Variable temperature for retry diversity
                    top_p=0.8,   # More focused sampling
                    do_sample=True,
                    pad_token_id=tokenizer.eos_token_id,
                    eos_token_id=tokenizer.eos_token_id,
                    use_cache=False,  # Fix cache issues
                    repetition_penalty=1.1 + (retry_attempt * 0.05),   # Increase repetition penalty for retries
                    no_repeat_ngram_size=3    # Prevent repetitive patterns
                    # Removed early_stopping and length_penalty to avoid generation warnings
                )
            
            # Decode and clean response
            response = tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Debug: Check if response is empty or too short (only show once)
            if len(response.strip()) < 10 and show_warnings:
                print(f"  {self.RED}[WARNING]{self.RESET} Very short response from {model_name}")
            
            # Extract just the generated part (after prompt)
            if "Title:" in response:
                title = response.split("Title:")[-1].strip()
            elif "Complete Chapter Title:" in response:
                title = response.split("Complete Chapter Title:")[-1].strip()
            elif "Chapter Title:" in response:
                title = response.split("Chapter Title:")[-1].strip()
            else:
                title = response[len(prompt):].strip()
            
            # If the title has multiple lines or explanatory text, take only the first line
            if '\n' in title:
                title = title.split('\n')[0].strip()
            
            # If there's explanatory text after the title, try to extract just the title part
            # Look for patterns like: "Title" followed by explanation
            if '"' in title:
                # Try to extract quoted title
                import re
                quoted_match = re.search(r'"([^"]+)"', title)
                if quoted_match:
                    title = quoted_match.group(1).strip()
            
            # If extraction failed, try alternative methods
            if not title or len(title.strip()) < 3:
                # Try extracting from the end of response
                lines = response.strip().split('\n')
                for line in reversed(lines):
                    if line.strip() and len(line.strip()) > 3:
                        title = line.strip()
                        break
                
                # If still empty, create a summary-based title
                if not title or len(title.strip()) < 3:
                    # Extract key words from the transcript for emergency title
                    content_preview = prompt.split("Content Summary:")[1].split("Create a")[0][:200] if "Content Summary:" in prompt else "Content"
                    title = f"Chapter Analysis: {content_preview.split()[0:3] if content_preview.split() else ['Content']} Overview"
            
            # Clean up the title
            title = self._clean_title(title)
            
            return title if title else f"Generated Title ({model_name})"
            
        except Exception as e:
            print(f"{self.RED}[ERROR]{self.RESET} Issue encountered generating with {model_name}: {e}")
            print(f"  {self.YELLOW}[INFO]{self.RESET} Prompt length: {len(prompt)} chars")
            return f"Error Title ({model_name})"
    
    def _generate_gemini_with_retry(self, prompt: str, max_retries: int = 10) -> str:
        """Generate title with Gemini API with retry logic for failures."""
        for attempt in range(max_retries):
            title = self._generate_with_gemini(prompt)
            
            # Check if title generation failed
            if (title.startswith("Generated Title") or 
                title.startswith("Error Title") or 
                len(title.strip()) < 3 or
                title.strip().lower() in ["sand", "generated", "title"]):
                
                if attempt == max_retries - 1:  # Last attempt
                    return "FAILURE"
                # Add extra wait time for long prompts - VERY generous for API
                if len(prompt) > 4000:
                    time.sleep(6)  # Very generous time for API with very long prompts
                elif len(prompt) > 2000:
                    time.sleep(4)  # Generous time for API with long prompts
                continue  # Retry
            else:
                return title  # Success
        
        return "FAILURE"
    
    def _generate_with_gemini(self, prompt: str) -> str:
        """
        Generate title using Gemini API.
        
        Args:
            prompt: Input prompt
            
        Returns:
            Generated title string
        """
        try:
            # TODO: Solution for lengthy titles - consider implementing title length validation and truncation
            response = self.gemini_model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.4,  # Lower for more focused output
                    max_output_tokens=100,  # Increased from 20 to allow more creative titles
                    top_p=0.8  # More focused sampling
                )
            )
            
            title = response.text.strip()
            title = self._clean_title(title)
            
            return title if title else "Generated Title (Gemini)"
            
        except Exception as e:
            print(f"  Error generating with Gemini: {e}")
            return "Error Title (Gemini)"
    
    def _sanitize_for_csv(self, text: str) -> str:
        """Sanitize text for safe CSV output."""
        if not text:
            return text
        # Remove problematic characters and normalize quotes
        text = text.replace('\n', ' ').replace('\r', ' ')
        text = text.replace('"""', '"').replace("'''", "'")
        # Normalize multiple quotes
        while '""' in text:
            text = text.replace('""', '"')
        while "''" in text:
            text = text.replace("''", "'")
        return text.strip()
    
    def _clean_title(self, title: str) -> str:
        """Clean and format the generated title."""
        # Remove common unwanted prefixes/suffixes
        unwanted = [
            "Complete Chapter Title:", "Chapter Title:", "Title:", "Chapter:", 
            "Generated Title:", "Here's", "The title",
            "A good title", "Chapter title:", "Transcript:",
            "Subtitle:", "Sub", "-", "*"
        ]
        
        title_lower = title.lower()
        for unwanted_phrase in unwanted:
            if title_lower.startswith(unwanted_phrase.lower()):
                title = title[len(unwanted_phrase):].strip()
                break
        
        # Remove quotes and extra whitespace, handle CSV-safe quotes
        title = title.strip()
        # Remove surrounding quotes but keep internal quotes
        if title.startswith('"') and title.endswith('"'):
            title = title[1:-1].strip()
        elif title.startswith("'") and title.endswith("'"):
            title = title[1:-1].strip()
        # Remove double quotes that might remain
        if title.startswith('"') and title.endswith('"'):
            title = title[1:-1].strip()
        # Replace any remaining problematic quotes with safe alternatives
        title = title.replace('"""', '"').replace("'''", "'")
        title = title.strip()
        
        # Take only the first line if multiple lines
        title = title.split('\n')[0].strip()
        
        # Check for incomplete titles (ending with incomplete words or phrases)
        # Only remove these if the title seems obviously incomplete (very short or ends abruptly)
        incomplete_endings = [
            "a", "an", "the", "to", "in", "of", "at", "on", "by", "for", "from", 
            "is", "are", "was", "were", "can", "will", "would", "could", "should", "may", "might"
        ]
        
        words = title.split()
        
        # Only remove incomplete ending words if the title is very short or clearly incomplete
        if len(words) > 1 and len(words) < 4:  # Only for very short titles
            while len(words) > 0 and words[-1].lower() in incomplete_endings:
                words = words[:-1]
        
        # Reconstruct title
        title = ' '.join(words)
        
        # Check for cut-off words (words that seem incomplete)
        if len(words) > 0:
            last_word = words[-1]
            # Remove if last word looks cut off (no vowels, too short, etc.)
            if (len(last_word) < 3 and last_word.lower() not in ['ai', 'io', 'ui', 'is', 'it', 'of', 'or', 'to', 'up']) or \
               (len(last_word) > 1 and not any(c in last_word.lower() for c in 'aeiou')):
                words = words[:-1]
                title = ' '.join(words)
        
        # Ensure minimum word count for quality
        if len(words) < 3:
            print(f"    [WARNING]  Title too short ({len(words)} words), flagging for regeneration")
            return ""  # Return empty to trigger retry
        
        # Remove trailing punctuation except for appropriate ending punctuation
        while title and title[-1] in ".,;:":
            title = title[:-1].strip()
        
        # TODO: Solution for lengthy titles - implement smart title truncation here if needed
        # Removed strict word limit to allow more creative title generation
        words = title.split()
        # Keep minimum word requirement but remove maximum limit
        if len(words) < 3 and len(words) > 0:
            # If too short, keep as is rather than reject
            pass
        
        # Capitalize properly
        if title:
            title = title[0].upper() + title[1:] if len(title) > 1 else title.upper()
        
        return title
    
    def _load_transcripts(self, input_dir: Path) -> Dict[str, List[Dict]]:
        """Load all transcript files from the input directory."""
        transcripts = {}
        
        for json_file in input_dir.glob("*_transcripts.json"):
            video_name = json_file.stem.replace("_transcripts", "")
            
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    transcripts[video_name] = data
                    
                    # Display with improved format
                    timestamp = self._get_ph_timestamp()
                    print(f"({self.GREEN}PASS{self.RESET} | {timestamp}) [{video_name.upper()}] Loaded {len(data)} segments")
                    
                    # Show character count for each segment with color coding
                    for i, segment in enumerate(data, 1):
                        char_count = len(segment.get('transcript', ''))
                        color = self._get_char_count_color(char_count)
                        print(f"    {color}[{i:02d}]{self.RESET} {char_count:,} characters")
                            
            except Exception as e:
                timestamp = self._get_ph_timestamp()
                print(f"({self.RED}ERROR{self.RESET} | {timestamp}) [{video_name.upper()}] Error loading: {e}")
        
        return transcripts
    
    def _setup_csv_output(self, output_file: Path) -> csv.DictWriter:
        """Setup CSV file for logging results."""
        fieldnames = ['model', 'video', 's#', 't#', 'start', 'generated_title']
        
        file_exists = output_file.exists()
        
        f = open(output_file, 'a', newline='', encoding='utf-8')
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        
        if not file_exists:
            writer.writeheader()
        
        return writer, f
    
    def _is_already_processed(self, csv_file: Path, model: str, video: str, segment: int, title_number: int = 1) -> bool:
        """Check if a model-video-segment-title combination has already been processed."""
        if not csv_file.exists():
            return False
        
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if (row['model'] == model and 
                        row['video'] == video and 
                        int(row['segment']) == segment and
                        int(row.get('title_number', 1)) == title_number):
                        return True
        except Exception as e:
            print(f"Error checking CSV: {e}")
        
        return False
    
    def generate_all_titles(self, input_dir: str, output_dir: str):
        """
        Main function to generate titles using all models.
        Processes one model at a time to manage VRAM efficiently.
        """
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Load all transcript data
        print("Loading transcript data...")
        all_transcripts = self._load_transcripts(input_path)
        
        if not all_transcripts:
            print("No transcript files found!")
            return
        
        # We'll create separate CSV files for each video
        
        # Process each model sequentially (one at a time for memory management)
        for model_name, model_path in self.models_config.items():
            print(f"\n{'='*60}")
            print(f"PROCESSING MODEL: {model_name}")
            print(f"{'='*60}")
            
            if model_name == "gemini-flash":
                # Handle Gemini API separately
                if not self.use_gemini:
                    continue
                
                self._process_gemini_model(all_transcripts, output_path)
            else:
                # Handle local models
                self._process_local_model(model_name, model_path, all_transcripts, output_path)
            
            # Small delay between models
            time.sleep(2)
        
        print(f"\nResults saved to individual CSV files in: {output_path}")

    def generate_selected_titles(self, input_dir: str, output_dir: str, selected_videos: List[str]):
        """
        Generate titles for selected videos only.
        Processes one model at a time to manage VRAM efficiently.
        """
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Load all transcript data first
        print("Loading transcript data...")
        all_transcripts = self._load_transcripts(input_path)
        
        if not all_transcripts:
            print("No transcript files found!")
            return
        
        # Filter to selected videos only
        filtered_transcripts = {}
        for video_name in selected_videos:
            if video_name in all_transcripts:
                filtered_transcripts[video_name] = all_transcripts[video_name]
                print(f"✓ Selected: {video_name}")
            else:
                print(f"⚠️  Warning: Video '{video_name}' not found in transcript files")
        
        if not filtered_transcripts:
            print("No valid videos selected!")
            return
        
        print(f"\nProcessing {len(filtered_transcripts)} selected video(s)...")
        
        # Process each model sequentially (one at a time for memory management)
        for model_name, model_path in self.models_config.items():
            print(f"\n{'='*60}")
            print(f"PROCESSING MODEL: {model_name}")
            print(f"{'='*60}")
            
            if model_name == "gemini-flash":
                # Handle Gemini API separately
                if not self.use_gemini:
                    continue
                
                self._process_gemini_model(filtered_transcripts, output_path)
            else:
                # Handle local models
                self._process_local_model(model_name, model_path, filtered_transcripts, output_path)
            
            # Small delay between models
            time.sleep(2)
        
        print(f"\nResults saved to individual CSV files in: {output_path}")
    
    def _process_local_model(self, model_name: str, model_path: str, all_transcripts: Dict, output_path: Path):
        """Process a single local model across all videos."""
        # Load model
        tokenizer, model = self._load_model(model_name, model_path)
        
        if tokenizer is None or model is None:
            print(f"Skipping {model_name} due to loading error")
            return
        
        try:
            # Process all videos with this model
            video_list = list(all_transcripts.items())
            for video_idx, (video_name, segments) in enumerate(video_list, 1):
                print(f"\n{'*'*50}")
                print(f"({video_idx}/{len(video_list)}) Processing [{video_name.upper()}] with [{model_name.upper()}]")
                print(f"{'*'*50}")
                
                # Setup CSV for this video
                csv_file = output_path / f"{video_name}_batch_titles.csv"
                csv_writer, csv_file_handle = self._setup_csv_output(csv_file)
                
                try:
                    for i, segment in enumerate(segments):
                        print(f"\n=====================================")
                        print(f"Processing Segment {i+1:02d}/{len(segments):02d} [{video_name.upper()}]")
                        print(f"=====================================")
                        
                        # Check for long prompts and show warning before all titles
                        prompt = self._create_prompt(segment['transcript'])
                        if len(prompt) > 2000:
                            print(f"{self.RED}[WARNING]{self.RESET} Very long prompt ({len(prompt)} chars) | Will require extra processing time...\n")
                        
                        # Initialize timeout tracking for this segment
                        segment_timeout_warning_shown = False
                        titles_to_generate = 10  # Default number of titles
                        
                        # Generate titles for this segment (10 or 5 depending on timeout)
                        for title_num in range(1, 11):
                            # Check for pause/quit before each title - COMMENTED OUT
                            # self._check_pause_quit()
                            
                            # Check if already processed (resumability)
                            if self._is_already_processed(csv_file, model_name, video_name, i + 1, title_num):
                                continue
                        
                            # Track generation time for this title
                            title_start_time = time.time()
                            
                            # Generate title with retry logic
                            title = self._generate_title_with_retry(tokenizer, model, prompt, model_name)
                            
                            title_generation_time = time.time() - title_start_time
                            
                            # Check if this title took longer than 5 minutes (300 seconds)
                            if title_generation_time > 300 and not segment_timeout_warning_shown and titles_to_generate == 10:
                                minutes = int(title_generation_time // 60)
                                seconds = int(title_generation_time % 60)
                                print(f"\n     {self.YELLOW}[NOTE]{self.RESET} Since title generation took {minutes:02d}:{seconds:02d} to generate, total amount of titles generated for this segment using [{model_name.upper()}] will be shortened to 5\n")
                                titles_to_generate = 5  # Reduce to 5 titles for remaining titles in this segment
                                segment_timeout_warning_shown = True
                            
                            # Log result (sanitize title for CSV)
                            csv_writer.writerow({
                                'model': model_name,
                                'video': video_name,
                                'segment': i + 1,
                                'title_number': title_num,
                                'start': segment['start'],
                                'generated_title': self._sanitize_for_csv(title)
                            })
                            
                            # Print formatted message with dynamic total
                            timestamp = self._get_ph_timestamp()
                            print(f"({timestamp}) [{model_name.upper()}] Segment {i+1} | Title {title_num:02d}/{titles_to_generate:02d} = \"{title}\"")
                            
                            # Check for pause/quit - COMMENTED OUT
                            # self._check_pause_quit()
                            
                            # If we've reduced titles and reached the limit, break early
                            if titles_to_generate == 5 and title_num == 5:
                                break
                            
                            # Small delay to prevent overheating
                            time.sleep(0.5)
                
                finally:
                    csv_file_handle.close()
        
        finally:
            # Always unload model to free memory
            self._unload_model(tokenizer, model)
            print(f"{self.GREEN}[PASS]{self.RESET} {model_name} unloaded and memory freed")
    
    def _process_gemini_model(self, all_transcripts: Dict, output_path: Path):
        """Process Gemini API model across all videos."""
        model_name = "gemini-flash"
        
        video_list = list(all_transcripts.items())
        for video_idx, (video_name, segments) in enumerate(video_list, 1):
            print(f"\n{'*'*50}")
            print(f"({video_idx}/{len(video_list)}) Processing [{video_name.upper()}] with [{model_name.upper()}]")
            print(f"{'*'*50}")
            
            # Setup CSV for this video
            csv_file = output_path / f"{video_name}_batch_titles.csv"
            csv_writer, csv_file_handle = self._setup_csv_output(csv_file)
            
            try:
                for i, segment in enumerate(segments):
                    print(f"\n=====================================")
                    print(f"Processing Segment {i+1:02d}/{len(segments):02d} [{video_name.upper()}]")
                    print(f"=====================================")
                    
                    # Check for long prompts and show warning before all titles
                    prompt = self._create_prompt(segment['transcript'])
                    if len(prompt) > 2000:
                        print(f"{self.RED}[WARNING]{self.RESET} Very long prompt ({len(prompt)} chars) | Using extended API timeout...\n")
                    
                    # Initialize timeout tracking for this segment
                    segment_timeout_warning_shown = False
                    titles_to_generate = 10  # Default number of titles
                    
                    # Generate titles for this segment (10 or 5 depending on timeout)
                    for title_num in range(1, 11):
                        # Check if already processed (resumability)
                        if self._is_already_processed(csv_file, model_name, video_name, i + 1, title_num):
                            continue
                    
                        # Track generation time for this title
                        title_start_time = time.time()
                        
                        # Generate title with retry logic
                        title = self._generate_gemini_with_retry(prompt)
                        
                        title_generation_time = time.time() - title_start_time
                        
                        # Check if this title took longer than 5 minutes (300 seconds)
                        if title_generation_time > 300 and not segment_timeout_warning_shown and titles_to_generate == 10:
                            minutes = int(title_generation_time // 60)
                            seconds = int(title_generation_time % 60)
                            print(f"\n     {self.YELLOW}[NOTE]{self.RESET} Since title generation took {minutes:02d}:{seconds:02d} to generate, total amount of titles generated for this segment using [{model_name.upper()}] will be shortened to 5\n")
                            titles_to_generate = 5  # Reduce to 5 titles for remaining titles in this segment
                            segment_timeout_warning_shown = True
                        
                        # Log result (sanitize title for CSV)
                        csv_writer.writerow({
                            'model': model_name,
                            'video': video_name,
                            'segment': i + 1,
                            'title_number': title_num,
                            'start': segment['start'],
                            'generated_title': self._sanitize_for_csv(title)
                        })
                        
                        # Print formatted message with dynamic total
                        timestamp = self._get_ph_timestamp()
                        print(f"({timestamp}) [{model_name.upper()}] Segment {i+1} / Title {title_num:02d}/{titles_to_generate:02d} = \"{title}\"")
                        
                        # If we've reduced titles and reached the limit, break early
                        if titles_to_generate == 5 and title_num == 5:
                            break
                        
                        # Check for pause/quit - COMMENTED OUT
                        # self._check_pause_quit()
                        
                        # Rate limiting for API
                        time.sleep(1)
            
            finally:
                csv_file_handle.close()


def show_menu(input_dir: str) -> list:
    """Show interactive menu for video selection."""
    # Get available videos
    input_path = Path(input_dir)
    transcript_files = list(input_path.glob("*_transcripts.json"))
    
    if not transcript_files:
        print(f"No transcript files found in {input_dir}")
        return []
    
    # Extract video names
    videos = []
    for file in transcript_files:
        video_name = file.stem.replace("_transcripts", "")
        videos.append(video_name)
    
    videos.sort()  # Sort alphabetically
    
    while True:
        print("\n" + "="*60)
        print("           VIDEO TITLE GENERATION MENU")
        print("="*60)
        print("Available videos:")
        
        for i, video in enumerate(videos, 1):
            print(f"  {i:2d}. {video}")
        
        print("\nSelection options:")
        print("  - Single video: Enter number (e.g., '3')")
        print("  - Multiple videos: Enter numbers separated by commas (e.g., '1,3,5')")
        print("  - Range: Enter range with dash (e.g., '2-5')")
        print("  - All videos: Enter 'all' or 'a'")
        print("  - Cancel: Enter 'q' or 'quit'")
        
        selection = input("\nEnter your selection: ").strip().lower()
        
        if selection in ['q', 'quit']:
            return []
        
        if selection in ['all', 'a']:
            return videos
        
        try:
            selected_videos = []
            
            # Handle ranges (e.g., "2-5")
            if '-' in selection:
                parts = selection.split('-')
                if len(parts) == 2:
                    start, end = int(parts[0]), int(parts[1])
                    if 1 <= start <= len(videos) and 1 <= end <= len(videos) and start <= end:
                        selected_videos = videos[start-1:end]
                    else:
                        raise ValueError("Invalid range")
                else:
                    raise ValueError("Invalid range format")
            
            # Handle comma-separated numbers (e.g., "1,3,5")
            elif ',' in selection:
                numbers = [int(x.strip()) for x in selection.split(',')]
                for num in numbers:
                    if 1 <= num <= len(videos):
                        selected_videos.append(videos[num-1])
                    else:
                        raise ValueError(f"Invalid video number: {num}")
            
            # Handle single number
            else:
                num = int(selection)
                if 1 <= num <= len(videos):
                    selected_videos = [videos[num-1]]
                else:
                    raise ValueError(f"Invalid video number: {num}")
            
            if selected_videos:
                print(f"\nSelected videos: {', '.join(selected_videos)}")
                confirm = input("Proceed with these selections? (y/n): ").strip().lower()
                if confirm in ['y', 'yes']:
                    return selected_videos
        
        except ValueError as e:
            print(f"\nError: {e}")
            print("Please try again.")
        
        print()  # Add spacing before showing menu again


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate video chapter titles using multiple LLMs")
    parser.add_argument(
        "--gemini", 
        action="store_true", 
        help="Include Gemini 2.0 Flash via API (requires GOOGLE_API_KEY in .env)"
    )
    parser.add_argument(
        "--input-dir", 
        default="output/raw_transcripts",
        help="Directory containing transcript JSON files"
    )
    parser.add_argument(
        "--output-dir", 
        default="output/llm_generated/batch",
        help="Directory for output CSV logs"
    )
    parser.add_argument(
        "--menu",
        action="store_true",
        help="Show interactive menu for video selection"
    )
    
    args = parser.parse_args()

    print(f"Input directory: {args.input_dir}")
    print(f"Output directory: {args.output_dir}")
    print(f"Using Gemini API: {args.gemini}")
    
    # Handle menu mode
    if args.menu:
        selected_videos = show_menu(args.input_dir)
        if not selected_videos:
            print("No videos selected. Exiting.")
            return
    else:
        selected_videos = None  # Process all videos
    
    # Initialize generator
    generator = TitleGenerator(use_gemini=args.gemini)
    
    # Start input monitoring thread - COMMENTED OUT
    # input_thread = threading.Thread(target=generator._monitor_input, daemon=True)
    # input_thread.start()
    # 
    # print(f"{generator.YELLOW}[INFO]{generator.RESET} Input monitoring started. You can now use pause/quit controls.")
    
    try:
        # Generate titles
        if selected_videos:
            generator.generate_selected_titles(args.input_dir, args.output_dir, selected_videos)
        else:
            generator.generate_all_titles(args.input_dir, args.output_dir)
        print("\n[PASS] Title generation complete!")
    except KeyboardInterrupt:
        print("\n[WARNING] Process interrupted by user!")
        print("[INFO] Final results saved to CSV files.")
    except Exception as e:
        print(f"\n[ERROR] Error during generation: {e}")
    finally:
        # generator.should_quit = True  # COMMENTED OUT
        # print("[INFO] Shutting down input monitoring...")  # COMMENTED OUT
        # Give the input thread time to exit
        # if 'input_thread' in locals():
        #     input_thread.join(timeout=2.0)  # More generous timeout
        pass


if __name__ == "__main__":
    main()