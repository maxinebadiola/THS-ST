#!/usr/bin/env python3
# for RTX 4090 24GB VRAM Runpod


#INSTALL DEPENDENCIES: via setupTitleGeneration.sh
# cd /root/THS-ST-1 && ./scripts/setupTitleGeneration.sh

#FIRST go to repo file:
# cd /root/THS-ST 

#run ALL models on ALL videos with chapter timestamps + segmented transcript
# python scripts/4B-generateTitles.py

#choose specific: models and videos to run
# cd /root/THS-ST-1 && python scripts/4B-generateTitles.py --menu

#choose specific segment to generate titles for
# python scripts/4B-generateTitles.py --segment-menu
# #TO REMOVE GENERATED TITLES:
# rm -f output/llm_generated/batch/

import os
import json
import csv
import gc
import time
import argparse
import shutil
import subprocess
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
from huggingface_hub import login
# import google.generativeai as genai  # Gemini API


class TitleGenerator:
    
    #TERMINAL COLOURS
    RED = '\033[91m'
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    ORANGE = '\033[33m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    
    def __init__(self, use_gemini: bool = False, selected_models: Optional[List[str]] = None):
        """
        Initialize the title generator.
        
        Args:
            use_gemini: Whether to include Gemini API model
            selected_models: Optional list of specific models to use (None = use all)
        """
        self.use_gemini = use_gemini
        
        # Setup Hugging Face authentication
        self._setup_huggingface_auth()
        
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
            test_tensor = torch.tensor([1.0], dtype=torch.float32, device="cuda")
            del test_tensor
            print(f"[PASS] GPU functionality verified")
        except Exception as e:
            print(f"{self.RED}[FAIL] GPU VERIFICATION FAILED: {e}{self.RESET}")
            print(f"{self.RED}Shutting down script...{self.RESET}")
            import sys
            sys.exit(1)
            
        # Set PyTorch memory allocation config to reduce fragmentation
        os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'
            
        # Get all available models
        all_models = self._get_models_config()
        
        # Filter models if specific ones are selected
        if selected_models:
            self.models_config = {k: v for k, v in all_models.items() if k in selected_models}
        else:
            self.models_config = all_models
        
        # self.paused = False  # COMMENTED OUT
        # self.should_quit = False  # COMMENTED OUT
        
        # Philippine timezone (UTC+8)
        self.ph_tz = timezone(timedelta(hours=8))
        
        # Setup API key if using Gemini
        if self.use_gemini:
            self._setup_gemini_api()
        
        print(f"TitleGenerator initialized with device: {self.device}")
        print(f"Models to use: {list(self.models_config.keys())}")
        if self.use_gemini:
            print("Gemini API enabled")
    
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
    
    def _setup_huggingface_auth(self):
        """Setup Hugging Face authentication from environment or prompt user."""
        try:
            load_dotenv()
            hf_token = os.getenv('HF_TOKEN') or os.getenv('HUGGINGFACE_TOKEN')
            
            if hf_token:
                login(token=hf_token, add_to_git_credential=False)
                print(f"{self.GREEN}[PASS]{self.RESET} Hugging Face authentication successful")
            else:
                print(f"{self.YELLOW}[INFO]{self.RESET} No HF_TOKEN found in .env file")
                print(f"{self.YELLOW}[INFO]{self.RESET} NOTE: Llama, Gemma require huggingspace authorization")
                print(f"{self.YELLOW}[INFO]{self.RESET} Add HF_TOKEN to .env file to access gated models")
        except Exception as e:
            print(f"{self.YELLOW}[WARNING]{self.RESET} Hugging Face auth setup: {e}")
            print(f"{self.YELLOW}[INFO]{self.RESET} Continuing without authentication - some models may not be accessible")
    
    def _get_models_config(self) -> Dict[str, str]:
        """Get configuration for local models."""
        config = {
            # TOP-TIER MODELS FOR RTX 4090 24GB (run individually)
            # Note: Llama and Gemma require HF authentication
            "llama3.1-8b": "meta-llama/Llama-3.1-8B-Instruct",  #Meta 8B
            "mistral-7b-v0.3": "mistralai/Mistral-7B-Instruct-v0.3",  #Mistral 7B
            
            #phi is difficult to run due to transformers compatibility issues
            # "phi4-mini": "microsoft/Phi-4-mini-instruct",  #Phi4 4B
            # "phi3.5-mini": "microsoft/Phi-3.5-mini-instruct",  #Phi3.5 3.8B 
            
            "gemma2-9b": "google/gemma-2-9b-it",  #Gemma 9B
            "qwen2-7b": "Qwen/Qwen2-7B-Instruct", 
            # "qwen2.5-14b": "Qwen/Qwen2.5-14B-Instruct",  #Qwen2.5 14B (NOTE: SLOW, requires significant disk space)
            #SMALLER MODELS (faster, lower memory usage)
            "tinyllama": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",  
        }
        
        
        # if self.use_gemini:
        #     config["gemini-flash"] = "gemini-2.0-flash-exp"
            
        return config
    
    def _setup_gemini_api(self):
        """Setup Gemini API using environment variables."""
        # COMMENTED OUT - Gemini API disabled
        # try:
        #     load_dotenv()
        #     api_key = os.getenv('GEMINI_API_KEY')
        #     if not api_key:
        #         raise ValueError("GEMINI_API_KEY not found in environment variables")
        #     
        #     genai.configure(api_key=api_key)
        #     self.gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')
        #     print(f"{self.GREEN}[PASS]{self.RESET} Gemini API configured successfully")
        # except Exception as e:
        #     print(f"{self.RED}[ERROR]{self.RESET} Failed to setup Gemini API: {e}")
        #     self.use_gemini = False
        pass
    
    def _load_model(self, model_name: str, model_path: str) -> tuple:
        """
        Load a single model with optimized settings for ~24GB+ VRAM
        
        Args:
            model_name: Short name for the model
            model_path: HuggingFace model path
            
        Returns:
            Tuple of (tokenizer, model)
        """
        print(f"\nLoading {model_name} ({model_path})...")
        
        try:
            # Suppress specific transformers warnings for cleaner output
            import warnings
            warnings.filterwarnings('ignore', message='.*flash-attention.*')
            warnings.filterwarnings('ignore', message='.*flash-attenton.*')
            warnings.filterwarnings('ignore', message='.*window_size.*')
            
            # Load tokenizer
            tokenizer = AutoTokenizer.from_pretrained(
                model_path, 
                trust_remote_code=True,
                padding_side="left"
            )
            
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
            
            # NOTE: No quantization, native bfloat16
            # Use dtype for better memory efficiency and compatibility
            dtype = torch.bfloat16
            
            # Prepare model loading kwargs
            model_kwargs = {
                "torch_dtype": dtype, 
                "device_map": "auto",
                "trust_remote_code": True,
            }
            
            # Handle attention implementation based on model type
            if "phi" in model_path.lower():
                # Phi models require 'eager' attention implementation
                model_kwargs["attn_implementation"] = "eager"
                print(f"{self.BLUE}[INFO]{self.RESET} Using eager attention for Phi model")
            elif "flash" in model_path.lower():
                # Only try flash attention for models that explicitly support it
                try:
                    import flash_attn
                    model_kwargs["attn_implementation"] = "flash_attention_2"
                except ImportError:
                    pass  # Silently skip if flash_attn not installed
            
            # Load model with suppressed warnings
            with warnings.catch_warnings():
                warnings.filterwarnings('ignore', category=UserWarning)
                try:
                    model = AutoModelForCausalLM.from_pretrained(
                        model_path,
                        **model_kwargs
                    )
                except Exception as import_err:
                    # Handle compatibility issues (e.g., LossKwargs for Phi4)
                    if "LossKwargs" in str(import_err) or "cannot import" in str(import_err):
                        print(f"{self.YELLOW}[INFO]{self.RESET} Compatibility issue detected, trying alternative loading method...")
                        # Try without trust_remote_code for problematic models
                        model_kwargs_alt = model_kwargs.copy()
                        model_kwargs_alt["trust_remote_code"] = False
                        try:
                            model = AutoModelForCausalLM.from_pretrained(
                                model_path,
                                **model_kwargs_alt
                            )
                        except:
                            raise import_err  # Re-raise original error if alternative fails
                    else:
                        raise  # Re-raise if it's a different error
            
            model.eval()
            print(f"{self.GREEN}[PASS]{self.RESET} {model_name} loaded successfully")
            
            # Immediately cleanup download cache after model is loaded into memory
            try:
                # Clear the download cache to free up disk space
                hub_cache = os.path.expanduser("~/.cache/huggingface/hub")
                if os.path.exists(hub_cache):
                    # Only delete .lock files and incomplete downloads
                    for item in os.listdir(hub_cache):
                        item_path = os.path.join(hub_cache, item)
                        if item.endswith('.lock') or 'incomplete' in item:
                            try:
                                if os.path.isfile(item_path):
                                    os.remove(item_path)
                                elif os.path.isdir(item_path):
                                    shutil.rmtree(item_path, ignore_errors=True)
                            except:
                                pass
            except:
                pass
            
            return tokenizer, model
            
        except Exception as e:
            print(f"{self.RED}[FAIL]{self.RESET} Failed to load {model_name}: {e}")
            return None, None
    
    def _unload_model(self, tokenizer, model, model_path: str = None):
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
        
        # Delete the specific model from HuggingFace cache to free disk space
        if model_path:
            self._delete_model_cache(model_path)
    
    def _check_disk_space(self):
        """Check available disk space and warn if low."""
        try:
            import subprocess
            # Check /workspace in RunPod (persistent storage)
            result = subprocess.run(['df', '-h', '/workspace'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    # Parse the output
                    parts = lines[1].split()
                    if len(parts) >= 5:
                        available = parts[3]
                        usage_percent = parts[4].rstrip('%')
                        
                        print(f"{self.BLUE}[DISK /workspace]{self.RESET} Available: {available} | Used: {usage_percent}%")
                        
                        # Warn if usage is high
                        try:
                            usage_int = int(usage_percent)
                            if usage_int > 95:
                                print(f"{self.RED}[CRITICAL]{self.RESET} Disk usage is CRITICAL ({usage_percent}%)!")
                                print(f"{self.RED}[WARNING]{self.RESET} Large models may fail to load!")
                                print(f"{self.YELLOW}[INFO]{self.RESET} Running aggressive cleanup...")
                                self._clear_huggingface_cache()
                            elif usage_int > 90:
                                print(f"{self.YELLOW}[WARNING]{self.RESET} Disk usage is very high ({usage_percent}%)!")
                                print(f"{self.YELLOW}[INFO]{self.RESET} Running aggressive cleanup...")
                                self._clear_huggingface_cache()
                            elif usage_int > 80:
                                print(f"{self.YELLOW}[NOTICE]{self.RESET} Disk usage is high ({usage_percent}%)")
                        except:
                            pass
            else:
                # Fallback to checking root if /workspace doesn't exist
                result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1:
                        parts = lines[1].split()
                        if len(parts) >= 5:
                            available = parts[3]
                            usage_percent = parts[4].rstrip('%')
                            print(f"{self.BLUE}[DISK /]{self.RESET} Available: {available} | Used: {usage_percent}%")
        except Exception as e:
            print(f"{self.YELLOW}[INFO]{self.RESET} Could not check disk space: {e}")
    
    def _delete_model_cache(self, model_path: str):
        """Delete specific model from HuggingFace cache to free disk space."""
        try:
            # Convert model path to cache directory name
            # e.g., "meta-llama/Llama-3.1-8B-Instruct" -> "models--meta-llama--Llama-3.1-8B-Instruct"
            cache_dir_name = "models--" + model_path.replace("/", "--")
            
            # HuggingFace cache locations
            cache_locations = [
                os.path.expanduser("~/.cache/huggingface/hub"),
                "/workspace/.cache/huggingface/hub"
            ]
            
            deleted = False
            for base_cache in cache_locations:
                model_cache_path = os.path.join(base_cache, cache_dir_name)
                
                if os.path.exists(model_cache_path):
                    try:
                        # Get size before deletion
                        cache_size = 0
                        try:
                            cache_size = sum(
                                os.path.getsize(os.path.join(dirpath, filename))
                                for dirpath, dirnames, filenames in os.walk(model_cache_path)
                                for filename in filenames
                            ) / (1024**3)  # Convert to GB
                        except Exception as size_err:
                            print(f"{self.YELLOW}[WARNING]{self.RESET} Could not calculate cache size: {size_err}")
                        
                        # Try multiple deletion methods
                        delete_success = False
                        
                        # Method 1: shutil.rmtree
                        try:
                            shutil.rmtree(model_cache_path, ignore_errors=False)
                            delete_success = True
                        except PermissionError:
                            # Method 2: Use subprocess rm -rf
                            try:
                                result = subprocess.run(
                                    ["rm", "-rf", model_cache_path],
                                    capture_output=True,
                                    text=True,
                                    timeout=60
                                )
                                if result.returncode == 0:
                                    delete_success = True
                                else:
                                    print(f"{self.YELLOW}[WARNING]{self.RESET} rm command failed: {result.stderr}")
                            except Exception as rm_err:
                                print(f"{self.YELLOW}[WARNING]{self.RESET} Could not delete with rm: {rm_err}")
                        except Exception as rmtree_err:
                            print(f"{self.YELLOW}[WARNING]{self.RESET} Could not delete with shutil: {rmtree_err}")
                        
                        if delete_success:
                            if cache_size > 0.01:
                                print(f"{self.GREEN}[CLEANUP]{self.RESET} Deleted {model_path} cache: {cache_size:.2f}GB freed")
                            else:
                                print(f"{self.GREEN}[CLEANUP]{self.RESET} Deleted {model_path} cache")
                            deleted = True
                        else:
                            print(f"{self.YELLOW}[WARNING]{self.RESET} Could not delete {model_path} cache from {base_cache}")
                    except Exception as e:
                        print(f"{self.YELLOW}[WARNING]{self.RESET} Could not delete {model_path} cache: {e}")
            
            if not deleted:
                print(f"{self.BLUE}[INFO]{self.RESET} No cache found for {model_path}")
                
        except Exception as e:
            print(f"{self.YELLOW}[WARNING]{self.RESET} Model cache cleanup failed: {e}")

    
    def _clear_huggingface_cache(self):
        """Clear Hugging Face cache to free disk space."""
        try:
            # Multiple cache locations to check (including RunPod's /workspace)
            cache_locations = [
                os.path.expanduser("~/.cache/huggingface"),
                os.path.expanduser("~/.cache/torch"),
                "/workspace/.cache/huggingface",  # RunPod persistent storage
                "/workspace/.cache/torch",        # RunPod persistent storage
                "/tmp/torch_extensions",
                "/tmp/huggingface",
                os.path.join(os.getcwd(), ".cache"),
            ]
            
            total_freed = 0.0
            print(f"\n{self.YELLOW}[CLEANUP]{self.RESET} Clearing caches to free disk space...")
            
            for cache_dir in cache_locations:
                if os.path.exists(cache_dir):
                    try:
                        # Get size before cleanup
                        print(f"  {self.BLUE}[INFO]{self.RESET} Scanning {cache_dir}...")
                        cache_size = 0
                        try:
                            cache_size = sum(
                                os.path.getsize(os.path.join(dirpath, filename))
                                for dirpath, dirnames, filenames in os.walk(cache_dir)
                                for filename in filenames
                            ) / (1024**3)  # Convert to GB
                        except Exception as size_err:
                            print(f"  {self.YELLOW}!{self.RESET} Could not calculate size for {cache_dir}: {size_err}")
                        
                        # Try multiple methods to clear the cache
                        deleted = False
                        
                        # Method 1: Use shutil.rmtree without ignore_errors to see actual errors
                        try:
                            shutil.rmtree(cache_dir, ignore_errors=False)
                            os.makedirs(cache_dir, exist_ok=True)
                            deleted = True
                        except PermissionError as perm_err:
                            print(f"  {self.YELLOW}!{self.RESET} Permission denied for {cache_dir}, trying with sudo...")
                            # Method 2: Try with subprocess and rm -rf (more aggressive)
                            try:
                                result = subprocess.run(
                                    ["rm", "-rf", cache_dir],
                                    capture_output=True,
                                    text=True,
                                    timeout=60
                                )
                                if result.returncode == 0:
                                    os.makedirs(cache_dir, exist_ok=True)
                                    deleted = True
                                else:
                                    print(f"  {self.YELLOW}!{self.RESET} rm command failed: {result.stderr}")
                            except Exception as rm_err:
                                print(f"  {self.YELLOW}!{self.RESET} rm command error: {rm_err}")
                        except Exception as rmtree_err:
                            print(f"  {self.YELLOW}!{self.RESET} shutil.rmtree failed: {rmtree_err}")
                        
                        if deleted:
                            total_freed += cache_size
                            if cache_size > 0.01:  # Only report if significant
                                print(f"  {self.GREEN}✓{self.RESET} Cleared {os.path.basename(cache_dir)}: {cache_size:.2f}GB")
                            else:
                                print(f"  {self.GREEN}✓{self.RESET} Cleared {os.path.basename(cache_dir)}")
                        else:
                            print(f"  {self.RED}✗{self.RESET} Failed to clear {os.path.basename(cache_dir)}")
                    except Exception as e:
                        print(f"  {self.YELLOW}!{self.RESET} Could not clear {cache_dir}: {e}")
                else:
                    print(f"  {self.BLUE}[SKIP]{self.RESET} {cache_dir} does not exist")
            
            # Also clear pip cache
            try:
                print(f"  {self.BLUE}[INFO]{self.RESET} Clearing pip cache...")
                result = subprocess.run(["pip", "cache", "purge"], capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    print(f"  {self.GREEN}✓{self.RESET} Cleared pip cache")
                else:
                    print(f"  {self.YELLOW}!{self.RESET} Pip cache purge failed: {result.stderr}")
            except Exception as pip_err:
                print(f"  {self.YELLOW}!{self.RESET} Could not clear pip cache: {pip_err}")
            
            print(f"{self.GREEN}[PASS]{self.RESET} Total freed: {total_freed:.2f}GB")
                
        except Exception as e:
            print(f"{self.YELLOW}[WARNING]{self.RESET} Cache cleanup failed: {e}")
            print(f"{self.YELLOW}[INFO]{self.RESET} Continuing anyway...")
    
    def _create_prompt(self, transcript: str) -> str:
        cleaned_transcript = transcript.strip()
        
        prompt = f"""Create a brief, engaging chapter title for this transcript. Be descriptive, creative, and concise.

Transcript: {cleaned_transcript}

REQUIREMENTS:
- NO cut-off or incomplete words
- Summarize the core topic precisely
- Use clear, engaging language
- Keep it brief and concise (1-8 words)
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
        # COMMENTED OUT - Gemini API disabled
        # for attempt in range(max_retries):
        #     title = self._generate_with_gemini(prompt)
        #     
        #     # Check if title generation failed
        #     if (title.startswith("Generated Title") or 
        #         title.startswith("Error Title") or 
        #         len(title.strip()) < 3 or
        #         title.strip().lower() in ["sand", "generated", "title"]):
        #         
        #         if attempt == max_retries - 1:  # Last attempt
        #             return "FAILURE"
        #         # Add extra wait time for long prompts - VERY generous for API
        #         if len(prompt) > 4000:
        #             time.sleep(6)  # Very generous time for API with very long prompts
        #         elif len(prompt) > 2000:
        #             time.sleep(4)  # Generous time for API with long prompts
        #         continue  # Retry
        #     else:
        #         return title  # Success
        # 
        # return "FAILURE"
        return "FAILURE"  # Gemini disabled
    
    def _generate_with_gemini(self, prompt: str) -> str:
        """
        Generate title using Gemini API.
        
        Args:
            prompt: Input prompt
            
        Returns:
            Generated title string
        """
        # COMMENTED OUT - Gemini API disabled
        # try:
        #     # TODO: Solution for lengthy titles - consider implementing title length validation and truncation
        #     response = self.gemini_model.generate_content(
        #         prompt,
        #         generation_config=genai.types.GenerationConfig(
        #             temperature=0.4,  # Lower for more focused output
        #             max_output_tokens=100,  # Increased from 20 to allow more creative titles
        #             top_p=0.8  # More focused sampling
        #         )
        #     )
        #     
        #     title = response.text.strip()
        #     title = self._clean_title(title)
        #     
        #     return title if title else "Generated Title (Gemini)"
        #     
        # except Exception as e:
        #     print(f"  Error generating with Gemini: {e}")
        #     return "Error Title (Gemini)"
        return "Error Title (Gemini)"  # Gemini disabled
    
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
        """Setup CSV file for logging results - creates header if needed."""
        fieldnames = ['model', 'video', 'segment', 'title_number', 'start', 'generated_title']
        
        file_exists = output_file.exists()
        
        if not file_exists:
            # Create file with header
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
                writer.writeheader()
        
        return fieldnames
    
    def _append_to_csv(self, output_file: Path, fieldnames: List[str], row_data: Dict):
        """Append a single row to CSV file immediately."""
        with open(output_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writerow(row_data)

    def _create_all_csv_files(self, output_path: Path, video_names: List[str]):
        """Create empty CSV files with headers for all videos upfront."""
        fieldnames = ['model', 'video', 'segment', 'title_number', 'start', 'generated_title']
        
        print(f"\n{self.BLUE}[SETUP]{self.RESET} Creating CSV files for {len(video_names)} video(s)...")
        for video_name in video_names:
            csv_file = output_path / f"{video_name}_batch_titles.csv"
            
            # Only create if it doesn't exist
            if not csv_file.exists():
                with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
                    writer.writeheader()
                print(f"  {self.GREEN}✓{self.RESET} Created: {video_name}_batch_titles.csv")
            else:
                print(f"  {self.YELLOW}◦{self.RESET} Exists: {video_name}_batch_titles.csv")
        print(f"{self.BLUE}[SETUP]{self.RESET} CSV files ready\n")

    
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
        
        # Create all CSV files upfront with headers
        self._create_all_csv_files(output_path, list(all_transcripts.keys()))
        
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

    def generate_single_segment_titles(self, input_dir: str, output_dir: str, video_name: str, segment_index: int):
        """
        Generate titles for a single segment of a specific video.
        Useful for testing and debugging specific segments.
        """
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Load the specific transcript file
        transcript_file = input_path / f"{video_name}_transcripts.json"
        if not transcript_file.exists():
            print(f"Error: Transcript file not found: {transcript_file}")
            return
        
        try:
            with open(transcript_file, 'r', encoding='utf-8') as f:
                segments = json.load(f)
        except Exception as e:
            print(f"Error loading transcript file: {e}")
            return
        
        if segment_index >= len(segments):
            print(f"Error: Segment {segment_index + 1} not found (only {len(segments)} segments available)")
            return
        
        segment = segments[segment_index]
        char_count = len(segment.get('transcript', ''))
        start_time = segment.get('start', 'N/A')
        
        print(f"\n{'='*60}")
        print(f"SINGLE SEGMENT TITLE GENERATION")
        print(f"{'='*60}")
        print(f"Video: {video_name}")
        print(f"Segment: {segment_index + 1} (Start: {start_time})")
        print(f"Character count: {char_count:,}")
        print(f"{'='*60}")
        
        # Create CSV file upfront with header
        csv_file = output_path / f"{video_name}_segment_{segment_index + 1}_titles.csv"
        if not csv_file.exists():
            fieldnames = ['model', 'video', 'segment', 'title_number', 'start', 'generated_title']
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
                writer.writeheader()
            print(f"\n{self.BLUE}[SETUP]{self.RESET} Created CSV file: {csv_file.name}")
        else:
            print(f"\n{self.YELLOW}[SETUP]{self.RESET} Using existing CSV file: {csv_file.name}")
        
        # Create a mini transcript structure for processing
        single_segment_data = {video_name: [segment]}
        
        # Process each model sequentially
        for model_name, model_path in self.models_config.items():
            print(f"\n{'='*60}")
            print(f"PROCESSING MODEL: {model_name}")
            print(f"{'='*60}")
            
            if model_name == "gemini-flash":
                # Handle Gemini API separately
                if not self.use_gemini:
                    continue
                
                self._process_gemini_single_segment(single_segment_data, output_path, segment_index)
            else:
                # Handle local models
                self._process_local_single_segment(model_name, model_path, single_segment_data, output_path, segment_index)
            
            # Small delay between models
            time.sleep(2)
        
        print(f"\nResults saved to CSV file in: {output_path}")

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
                print(f"[WARNING]: Video '{video_name}' not found in transcript files")
        
        if not filtered_transcripts:
            print("No valid videos selected!")
            return
        
        print(f"\nProcessing {len(filtered_transcripts)} selected video(s)...")
        
        # Create all CSV files upfront with headers
        self._create_all_csv_files(output_path, list(filtered_transcripts.keys()))
        
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
        # Check disk space before starting
        self._check_disk_space()
        
        # Clear cache BEFORE loading model to maximize available disk space
        # More aggressive cleanup for large models (Qwen 14B, etc.)
        if "14b" in model_name.lower() or "qwen" in model_name.lower():
            print(f"{self.YELLOW}[INFO]{self.RESET} Large model detected - performing aggressive cache cleanup...")
            self._clear_huggingface_cache()
            # Additional cleanup for large models
            import subprocess
            try:
                # Clean tmp directory properly (no shell=True to avoid glob issues)
                subprocess.run(["find", "/tmp", "-type", "f", "-delete"], timeout=10, stderr=subprocess.DEVNULL)
                subprocess.run(["find", "/tmp", "-type", "d", "-empty", "-delete"], timeout=10, stderr=subprocess.DEVNULL)
            except:
                pass
        else:
            self._clear_huggingface_cache()
        
        # Check disk space again after cleanup
        self._check_disk_space()
        
        # Load model
        tokenizer, model = self._load_model(model_name, model_path)
        
        if tokenizer is None or model is None:
            print(f"Skipping {model_name} due to loading error")
            return
        
        try:
            # Process all videos with this model
            video_list = list(all_transcripts.items())
            for video_idx, (video_name, segments) in enumerate(video_list, 1):
                video_start_time = time.time()
                video_start_timestamp = self._get_ph_timestamp()
                
                print(f"\n{'*'*50}")
                print(f"({video_idx}/{len(video_list)}) Processing [{video_name.upper()}] with [{model_name.upper()}]")
                print(f"{'*'*50}")
                
                # Setup CSV for this video
                csv_file = output_path / f"{video_name}_batch_titles.csv"
                fieldnames = self._setup_csv_output(csv_file)
                
                try:
                    for i, segment in enumerate(segments):
                        segment_start_time = time.time()
                        segment_start_timestamp = self._get_ph_timestamp()
                        
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
                            self._append_to_csv(csv_file, fieldnames, {
                                'model': model_name,
                                'video': video_name,
                                'segment': i + 1,
                                'title_number': title_num,
                                'start': segment['start'],
                                'generated_title': self._sanitize_for_csv(title)
                            })
                            
                            # Clear GPU cache after each title generation
                            torch.cuda.empty_cache()
                            
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
                        
                        # Clear GPU cache after processing all titles for this segment
                        torch.cuda.empty_cache()
                        
                        # Print segment completion timing
                        segment_end_time = time.time()
                        segment_end_timestamp = self._get_ph_timestamp()
                        segment_elapsed = segment_end_time - segment_start_time
                        segment_minutes = int(segment_elapsed // 60)
                        segment_seconds = int(segment_elapsed % 60)
                        
                        print(f"\n{self.BLUE}[SEGMENT COMPLETE]{self.RESET}")
                        print(f"{self.BLUE}├─ Video: {video_name}{self.RESET}")
                        print(f"{self.BLUE}├─ Segment: {i+1}/{len(segments)}{self.RESET}")
                        print(f"{self.BLUE}├─ Start Time: {segment_start_timestamp}{self.RESET}")
                        print(f"{self.BLUE}├─ End Time: {segment_end_timestamp}{self.RESET}")
                        print(f"{self.BLUE}└─ Elapsed: {segment_minutes:02d}:{segment_seconds:02d}{self.RESET}\n")
                
                except Exception as segment_error:
                    print(f"{self.RED}[ERROR]{self.RESET} Error processing segments: {segment_error}")
                
            # Print video completion timing (moved outside try-except block)
            video_end_time = time.time()
            video_end_timestamp = self._get_ph_timestamp()
            video_elapsed = video_end_time - video_start_time
            video_minutes = int(video_elapsed // 60)
            video_seconds = int(video_elapsed % 60)
            
            print(f"\n{self.BLUE}{'='*60}{self.RESET}")
            print(f"{self.BLUE}[VIDEO COMPLETE]{self.RESET}")
            print(f"{self.BLUE}├─ Video: {video_name}{self.RESET}")
            print(f"{self.BLUE}├─ Model: {model_name}{self.RESET}")
            print(f"{self.BLUE}├─ Total Segments: {len(segments)}{self.RESET}")
            print(f"{self.BLUE}├─ Start Time: {video_start_timestamp}{self.RESET}")
            print(f"{self.BLUE}├─ End Time: {video_end_timestamp}{self.RESET}")
            print(f"{self.BLUE}└─ Total Elapsed: {video_minutes:02d}:{video_seconds:02d}{self.RESET}")
            print(f"{self.BLUE}{'='*60}{self.RESET}\n")
        
        finally:
            # Always unload model to free memory and delete its cache
            self._unload_model(tokenizer, model, model_path)
            print(f"{self.GREEN}[PASS]{self.RESET} {model_name} unloaded and memory freed")
    
    def _process_local_single_segment(self, model_name: str, model_path: str, single_segment_data: Dict, output_path: Path, segment_index: int):
        """Process a single segment with a local model."""
        # Check disk space before starting
        self._check_disk_space()
        
        # Clear cache BEFORE loading model to maximize available disk space
        # More aggressive cleanup for large models (Qwen 14B, etc.)
        if "14b" in model_name.lower() or "qwen" in model_name.lower():
            print(f"{self.YELLOW}[INFO]{self.RESET} Large model detected - performing aggressive cache cleanup...")
            self._clear_huggingface_cache()
            # Additional cleanup for large models
            import subprocess
            try:
                # Clean tmp directory properly (no shell=True to avoid glob issues)
                subprocess.run(["find", "/tmp", "-type", "f", "-delete"], timeout=10, stderr=subprocess.DEVNULL)
                subprocess.run(["find", "/tmp", "-type", "d", "-empty", "-delete"], timeout=10, stderr=subprocess.DEVNULL)
            except:
                pass
        else:
            self._clear_huggingface_cache()
        
        # Check disk space again after cleanup
        self._check_disk_space()
        
        # Load model
        tokenizer, model = self._load_model(model_name, model_path)
        
        if tokenizer is None or model is None:
            print(f"Skipping {model_name} due to loading error")
            return
        
        try:
            video_name, segments = next(iter(single_segment_data.items()))
            segment = segments[0]  # Only one segment
            
            print(f"\nProcessing single segment with [{model_name.upper()}]")
            
            # Track segment start time
            segment_start_time = time.time()
            segment_start_timestamp = self._get_ph_timestamp()
            
            # Setup CSV for this video
            csv_file = output_path / f"{video_name}_segment_{segment_index + 1}_titles.csv"
            fieldnames = self._setup_csv_output(csv_file)
            
            try:
                # Check for long prompts and show warning
                prompt = self._create_prompt(segment['transcript'])
                if len(prompt) > 2000:
                    print(f"{self.RED}[WARNING]{self.RESET} Very long prompt ({len(prompt)} chars) | Will require extra processing time...\n")
                
                # Generate 10 titles for this segment
                for title_num in range(1, 11):
                    # Track generation time for this title
                    title_start_time = time.time()
                    
                    # Generate title with retry logic
                    title = self._generate_title_with_retry(tokenizer, model, prompt, model_name)
                    
                    title_generation_time = time.time() - title_start_time
                    
                    # Log result (sanitize title for CSV)
                    self._append_to_csv(csv_file, fieldnames, {
                        'model': model_name,
                        'video': video_name,
                        'segment': segment_index + 1,
                        'title_number': title_num,
                        'start': segment['start'],
                        'generated_title': self._sanitize_for_csv(title)
                    })
                    
                    # Print formatted message
                    timestamp = self._get_ph_timestamp()
                    minutes = int(title_generation_time // 60)
                    seconds = int(title_generation_time % 60)
                    time_str = f"({minutes:02d}:{seconds:02d})" if minutes > 0 else f"({seconds}s)"
                    
                    print(f"({timestamp}) [{model_name.upper()}] Title {title_num:02d}/10 {time_str} = \"{title}\"")
                    
                    # Small delay to prevent overheating
                    time.sleep(0.5)
            
            except Exception as segment_error:
                print(f"{self.RED}[ERROR]{self.RESET} Error processing segment: {segment_error}")
        
        finally:
            # Always unload model to free memory and delete its cache
            self._unload_model(tokenizer, model, model_path)
            print(f"{self.GREEN}[PASS]{self.RESET} {model_name} unloaded and memory freed")
        
        # Print segment completion timing (moved outside try-except-finally block)
        segment_end_time = time.time()
        segment_end_timestamp = self._get_ph_timestamp()
        segment_elapsed = segment_end_time - segment_start_time
        segment_minutes = int(segment_elapsed // 60)
        segment_seconds = int(segment_elapsed % 60)
        
        print(f"\n{self.BLUE}[SEGMENT COMPLETE]{self.RESET}")
        print(f"{self.BLUE}├─ Video: {video_name}{self.RESET}")
        print(f"{self.BLUE}├─ Segment: {segment_index + 1}{self.RESET}")
        print(f"{self.BLUE}├─ Model: {model_name}{self.RESET}")
        print(f"{self.BLUE}├─ Titles Generated: 10{self.RESET}")
        print(f"{self.BLUE}├─ Start Time: {segment_start_timestamp}{self.RESET}")
        print(f"{self.BLUE}├─ End Time: {segment_end_timestamp}{self.RESET}")
        print(f"{self.BLUE}└─ Elapsed: {segment_minutes:02d}:{segment_seconds:02d}{self.RESET}\n")
    
    def _process_gemini_single_segment(self, single_segment_data: Dict, output_path: Path, segment_index: int):
        """Process a single segment with Gemini API."""
        model_name = "gemini-flash"
        
        video_name, segments = next(iter(single_segment_data.items()))
        segment = segments[0]  # Only one segment
        
        print(f"\nProcessing single segment with [{model_name.upper()}]")
        
        # Track segment start time
        segment_start_time = time.time()
        segment_start_timestamp = self._get_ph_timestamp()
        
        # Setup CSV for this video
        csv_file = output_path / f"{video_name}_segment_{segment_index + 1}_titles.csv"
        fieldnames = self._setup_csv_output(csv_file)
        
        try:
            # Check for long prompts and show warning
            prompt = self._create_prompt(segment['transcript'])
            if len(prompt) > 2000:
                print(f"{self.RED}[WARNING]{self.RESET} Very long prompt ({len(prompt)} chars) | Using extended API timeout...\n")
            
            # Generate 10 titles for this segment
            for title_num in range(1, 11):
                # Track generation time for this title
                title_start_time = time.time()
                
                # Generate title with retry logic
                title = self._generate_gemini_with_retry(prompt)
                
                title_generation_time = time.time() - title_start_time
                
                # Log result (sanitize title for CSV)
                self._append_to_csv(csv_file, fieldnames, {
                    'model': model_name,
                    'video': video_name,
                    'segment': segment_index + 1,
                    'title_number': title_num,
                    'start': segment['start'],
                    'generated_title': self._sanitize_for_csv(title)
                })
                
                # Print formatted message
                timestamp = self._get_ph_timestamp()
                minutes = int(title_generation_time // 60)
                seconds = int(title_generation_time % 60)
                time_str = f"({minutes:02d}:{seconds:02d})" if minutes > 0 else f"({seconds}s)"
                
                print(f"({timestamp}) [{model_name.upper()}] Title {title_num:02d}/10 {time_str} = \"{title}\"")
                
                # Rate limiting for API
                time.sleep(1)
        
        except Exception as segment_error:
            print(f"{self.RED}[ERROR]{self.RESET} Error processing segment: {segment_error}")
        
        # Print segment completion timing (moved outside try-except block)
        segment_end_time = time.time()
        segment_end_timestamp = self._get_ph_timestamp()
        segment_elapsed = segment_end_time - segment_start_time
        segment_minutes = int(segment_elapsed // 60)
        segment_seconds = int(segment_elapsed % 60)
        
        print(f"\n{self.BLUE}[SEGMENT COMPLETE]{self.RESET}")
        print(f"{self.BLUE}├─ Video: {video_name}{self.RESET}")
        print(f"{self.BLUE}├─ Segment: {segment_index + 1}{self.RESET}")
        print(f"{self.BLUE}├─ Model: {model_name}{self.RESET}")
        print(f"{self.BLUE}├─ Titles Generated: 10{self.RESET}")
        print(f"{self.BLUE}├─ Start Time: {segment_start_timestamp}{self.RESET}")
        print(f"{self.BLUE}├─ End Time: {segment_end_timestamp}{self.RESET}")
        print(f"{self.BLUE}└─ Elapsed: {segment_minutes:02d}:{segment_seconds:02d}{self.RESET}\n")
    
    def _process_gemini_model(self, all_transcripts: Dict, output_path: Path):
        """Process Gemini API model across all videos."""
        model_name = "gemini-flash"
        
        video_list = list(all_transcripts.items())
        for video_idx, (video_name, segments) in enumerate(video_list, 1):
            video_start_time = time.time()
            video_start_timestamp = self._get_ph_timestamp()
            
            print(f"\n{'*'*50}")
            print(f"({video_idx}/{len(video_list)}) Processing [{video_name.upper()}] with [{model_name.upper()}]")
            print(f"{'*'*50}")
            
            # Setup CSV for this video
            csv_file = output_path / f"{video_name}_batch_titles.csv"
            fieldnames = self._setup_csv_output(csv_file)
            
            try:
                for i, segment in enumerate(segments):
                    segment_start_time = time.time()
                    segment_start_timestamp = self._get_ph_timestamp()
                    
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
                        self._append_to_csv(csv_file, fieldnames, {
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
                    
                    # Print segment completion timing
                    segment_end_time = time.time()
                    segment_end_timestamp = self._get_ph_timestamp()
                    segment_elapsed = segment_end_time - segment_start_time
                    segment_minutes = int(segment_elapsed // 60)
                    segment_seconds = int(segment_elapsed % 60)
                    
                    print(f"\n{self.BLUE}[SEGMENT COMPLETE]{self.RESET}")
                    print(f"{self.BLUE}├─ Video: {video_name}{self.RESET}")
                    print(f"{self.BLUE}├─ Segment: {i+1}/{len(segments)}{self.RESET}")
                    print(f"{self.BLUE}├─ Start Time: {segment_start_timestamp}{self.RESET}")
                    print(f"{self.BLUE}├─ End Time: {segment_end_timestamp}{self.RESET}")
                    print(f"{self.BLUE}└─ Elapsed: {segment_minutes:02d}:{segment_seconds:02d}{self.RESET}\n")
            
            except Exception as segment_error:
                print(f"{self.RED}[ERROR]{self.RESET} Error processing segments: {segment_error}")
                
            # Print video completion timing
            video_end_time = time.time()
            video_end_timestamp = self._get_ph_timestamp()
            video_elapsed = video_end_time - video_start_time
            video_minutes = int(video_elapsed // 60)
            video_seconds = int(video_elapsed % 60)
            
            print(f"\n{self.BLUE}{'='*60}{self.RESET}")
            print(f"{self.BLUE}[VIDEO COMPLETE]{self.RESET}")
            print(f"{self.BLUE}├─ Video: {video_name}{self.RESET}")
            print(f"{self.BLUE}├─ Model: {model_name}{self.RESET}")
            print(f"{self.BLUE}├─ Total Segments: {len(segments)}{self.RESET}")
            print(f"{self.BLUE}├─ Start Time: {video_start_timestamp}{self.RESET}")
            print(f"{self.BLUE}├─ End Time: {video_end_timestamp}{self.RESET}")
            print(f"{self.BLUE}└─ Total Elapsed: {video_minutes:02d}:{video_seconds:02d}{self.RESET}")
            print(f"{self.BLUE}{'='*60}{self.RESET}\n")


def show_segment_menu(input_dir: str) -> tuple:
    """Show interactive menu for specific video segment selection."""
    # Get available videos
    input_path = Path(input_dir)
    transcript_files = list(input_path.glob("*_transcripts.json"))
    
    if not transcript_files:
        print(f"No transcript files found in {input_dir}")
        return None, None
    
    # Extract video names
    videos = []
    for file in transcript_files:
        video_name = file.stem.replace("_transcripts", "")
        videos.append(video_name)
    
    videos.sort()  # Sort alphabetically
    
    # Step 1: Select video
    while True:
        print("\n" + "="*60)
        print("        SPECIFIC SEGMENT TITLE GENERATION MENU")
        print("="*60)
        print("Available videos:")
        
        for i, video in enumerate(videos, 1):
            print(f"  {i:2d}. {video}")
        
        print("\nSelection options:")
        print("  - Select video: Enter number (e.g., '3')")
        print("  - Cancel: Enter 'q' or 'quit'")
        
        selection = input("\nEnter video selection: ").strip().lower()
        
        if selection in ['q', 'quit']:
            return None, None
        
        try:
            num = int(selection)
            if 1 <= num <= len(videos):
                selected_video = videos[num-1]
                break
            else:
                print(f"Error: Invalid video number: {num}")
                continue
        except ValueError:
            print("Error: Please enter a valid number")
            continue
    
    # Step 2: Load segments for selected video
    video_file = input_path / f"{selected_video}_transcripts.json"
    try:
        with open(video_file, 'r', encoding='utf-8') as f:
            segments = json.load(f)
    except Exception as e:
        print(f"Error loading segments for {selected_video}: {e}")
        return None, None
    
    # Step 3: Select segment
    while True:
        print(f"\n" + "="*60)
        print(f"SEGMENTS FOR: {selected_video.upper()}")
        print("="*60)
        
        for i, segment in enumerate(segments, 1):
            char_count = len(segment.get('transcript', ''))
            start_time = segment.get('start', 'N/A')
            
            # Color code based on character count
            if char_count < 100:
                color = '\033[91m'  # RED
            elif char_count < 1000:
                color = '\033[92m'  # GREEN
            elif char_count < 5000:
                color = '\033[33m'  # ORANGE
            else:
                color = '\033[91m'  # RED
            reset = '\033[0m'
            
            # Show preview of transcript (first 80 chars)
            transcript_preview = segment.get('transcript', '')[:80].replace('\n', ' ')
            if len(segment.get('transcript', '')) > 80:
                transcript_preview += "..."
            
            print(f"  {i:2d}. {color}[{char_count:,} chars]{reset} Start: {start_time}")
            print(f"      Preview: {transcript_preview}")
        
        print("\nSelection options:")
        print("  - Select segment: Enter number (e.g., '4')")
        print("  - Back to video selection: Enter 'b' or 'back'")
        print("  - Cancel: Enter 'q' or 'quit'")
        
        selection = input("\nEnter segment selection: ").strip().lower()
        
        if selection in ['q', 'quit']:
            return None, None
        
        if selection in ['b', 'back']:
            return show_segment_menu(input_dir)  # Restart from video selection
        
        try:
            num = int(selection)
            if 1 <= num <= len(segments):
                selected_segment = num - 1  # Convert to 0-based index
                
                # Confirmation
                segment_info = segments[selected_segment]
                char_count = len(segment_info.get('transcript', ''))
                start_time = segment_info.get('start', 'N/A')
                
                print(f"\nSelected:")
                print(f"  Video: {selected_video}")
                print(f"  Segment: {num} (Start: {start_time}, {char_count:,} characters)")
                
                confirm = input("Proceed with this selection? (y/n): ").strip().lower()
                if confirm in ['y', 'yes']:
                    return selected_video, selected_segment
                else:
                    continue  # Back to segment selection
            else:
                print(f"Error: Invalid segment number: {num}")
                continue
        except ValueError:
            print("Error: Please enter a valid number")
            continue


def show_menu(input_dir: str) -> tuple:
    """Show interactive menu for video and model selection."""
    # Get available videos
    input_path = Path(input_dir)
    transcript_files = list(input_path.glob("*_transcripts.json"))
    
    if not transcript_files:
        print(f"No transcript files found in {input_dir}")
        return [], []
    
    # Extract video names
    videos = []
    for file in transcript_files:
        video_name = file.stem.replace("_transcripts", "")
        videos.append(video_name)
    
    videos.sort()  # Sort alphabetically
    
    # Available models
    available_models = [
        "llama3.1-8b",
        "mistral-7b-v0.3",
        # "phi3.5-mini",
        "gemma2-9b",
        # "gemini-flash (API)",
        "tinyllama",
        "qwen2-7b",
        # "qwen2.5-14b"
    ]
    
    selected_videos = []
    selected_models = []
    
    # Step 1: Video Selection
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
            return [], []
        
        if selection in ['all', 'a']:
            selected_videos = videos
            break
        
        try:
            # Handle ranges (e.g., "2-5")
            if '-' in selection:
                parts = selection.split('-')
                if len(parts) == 2:
                    start, end = int(parts[0]), int(parts[1])
                    if 1 <= start <= len(videos) and 1 <= end <= len(videos) and start <= end:
                        selected_videos = videos[start-1:end]
                        break
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
                break
            
            # Handle single number
            else:
                num = int(selection)
                if 1 <= num <= len(videos):
                    selected_videos = [videos[num-1]]
                    break
                else:
                    raise ValueError(f"Invalid video number: {num}")
        
        except ValueError as e:
            print(f"\nError: {e}")
            print("Please try again.")
    
    # Step 2: Model Selection
    while True:
        print("\n" + "="*60)
        print("           MODEL SELECTION MENU")
        print("="*60)
        print("Available models:")
        
        for i, model in enumerate(available_models, 1):
            print(f"  {i}. {model}")
        
        print("\nSelection options:")
        print("  - Single model: Enter number (e.g., '1')")
        print("  - Multiple models: Enter numbers separated by commas (e.g., '1,3')")
        print("  - Range: Enter range with dash (e.g., '1-3')")
        print("  - All models: Enter 'all' or 'a'")
        print("  - Back to video selection: Enter 'b' or 'back'")
        print("  - Cancel: Enter 'q' or 'quit'")
        
        selection = input("\nEnter model selection: ").strip().lower()
        
        if selection in ['q', 'quit']:
            return [], []
        
        if selection in ['b', 'back']:
            return show_menu(input_dir)  # Restart from video selection
        
        if selection in ['all', 'a']:
            selected_models = available_models
            break
        
        try:
            # Handle ranges (e.g., "1-3")
            if '-' in selection:
                parts = selection.split('-')
                if len(parts) == 2:
                    start, end = int(parts[0]), int(parts[1])
                    if 1 <= start <= len(available_models) and 1 <= end <= len(available_models) and start <= end:
                        selected_models = available_models[start-1:end]
                        break
                    else:
                        raise ValueError("Invalid range")
                else:
                    raise ValueError("Invalid range format")
            
            # Handle comma-separated numbers (e.g., "1,3")
            elif ',' in selection:
                numbers = [int(x.strip()) for x in selection.split(',')]
                for num in numbers:
                    if 1 <= num <= len(available_models):
                        selected_models.append(available_models[num-1])
                    else:
                        raise ValueError(f"Invalid model number: {num}")
                break
            
            # Handle single number
            else:
                num = int(selection)
                if 1 <= num <= len(available_models):
                    selected_models = [available_models[num-1]]
                    break
                else:
                    raise ValueError(f"Invalid model number: {num}")
        
        except ValueError as e:
            print(f"\nError: {e}")
            print("Please try again.")
    
    # Final Confirmation
    print(f"\nSelected videos: {', '.join(selected_videos)}")
    print(f"Selected models: {', '.join(selected_models)}")
    confirm = input("Proceed with these selections? (y/n): ").strip().lower()
    
    if confirm in ['y', 'yes']:
        return selected_videos, selected_models
    else:
        return show_menu(input_dir)  # Restart the menu


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
    parser.add_argument(
        "--segment-menu",
        action="store_true",
        help="Show interactive menu for specific video segment selection"
    )
    
    args = parser.parse_args()

    print(f"Input directory: {args.input_dir}")
    print(f"Output directory: {args.output_dir}")
    print(f"Using Gemini API: {args.gemini}")
    
    # Handle segment menu mode
    if args.segment_menu:
        video_name, segment_index = show_segment_menu(args.input_dir)
        if video_name is None or segment_index is None:
            print("No segment selected. Exiting.")
            return
        
        # Initialize generator and process single segment
        generator = TitleGenerator(use_gemini=args.gemini)
        generator.generate_single_segment_titles(args.input_dir, args.output_dir, video_name, segment_index)
        print(f"\n[PASS] Single segment title generation complete!")
        return
    
    # Handle menu mode
    if args.menu:
        selected_videos, selected_models = show_menu(args.input_dir)
        if not selected_videos or not selected_models:
            print("No videos or models selected. Exiting.")
            return
        
        # Enable Gemini if it's in the selected models
        if "gemini-flash" in selected_models:
            args.gemini = True
    else:
        selected_videos = None  # Process all videos
        selected_models = None  # Process all models
    
    # Initialize generator with selected models
    generator = TitleGenerator(use_gemini=args.gemini, selected_models=selected_models)
    
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