#!/usr/bin/env python3
"""
AI Video Chapter Name Generator - High-Performance GPU Version
Generates engaging YouTube-style chapter names using state-of-the-art NLP models
Optimized for RunPod GPU environments with maximum quality focus
"""

import json
import pandas as pd
import numpy as np
import re
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple
from collections import Counter, defaultdict
import argparse
from datetime import datetime

# Lightweight imports
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    import spacy
    nlp = spacy.load("en_core_web_sm")  # Use smaller model
    SPACY_AVAILABLE = True
except (ImportError, OSError):
    SPACY_AVAILABLE = False

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import warnings
warnings.filterwarnings('ignore')

class HighPerformanceChapterTitleGenerator:
    """
    Generates engaging YouTube-style chapter titles using state-of-the-art NLP models
    Optimized for GPU acceleration and maximum quality
    """
    
    def __init__(self, device=None):
        """Initialize the generator with available models"""
        # Auto-detect GPU if available, prefer CUDA
        import torch
        if device is None:
            if torch.cuda.is_available():
                self.device = 'cuda'
                print(f"GPU detected! Using CUDA device: {torch.cuda.get_device_name()}")
                print(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
            else:
                self.device = 'cpu'
                print("No GPU detected, falling back to CPU")
        else:
            self.device = device
        print(f"Using device: {self.device}")
        # Initialize available models
        self._load_models()
        
    def _load_models(self):
        """Load high-performance models optimized for GPU"""
        print("Loading high-performance models for GPU acceleration...")
        
        # Load multiple sentence transformer models for comparison
        self.sentence_models = {}
        
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            # Model 1: MPNet (best overall quality)
            try:
                model_name = 'all-mpnet-base-v2'  # Best quality SentenceTransformer model
                print(f"Loading {model_name} on {self.device}...")
                self.sentence_models['mpnet'] = SentenceTransformer(model_name, device=self.device)
                print(f"MPNet model loaded on {self.device}")
            except Exception as e:
                print(f"⚠ MPNet model failed: {e}")
                
            # Model 2: RoBERTa (alternative high-quality model)
            try:
                model_name = 'all-roberta-large-v1'  # RoBERTa-based model
                print(f"Loading {model_name} on {self.device}...")
                self.sentence_models['roberta'] = SentenceTransformer(model_name, device=self.device)
                print(f"RoBERTa model loaded on {self.device}")
            except Exception as e:
                print(f"⚠ RoBERTa model failed, trying backup: {e}")
                try:
                    # Backup RoBERTa model
                    model_name = 'sentence-transformers/all-roberta-large-v1'
                    self.sentence_models['roberta'] = SentenceTransformer(model_name, device=self.device)
                    print(f"RoBERTa backup model loaded on {self.device}")
                except Exception as e2:
                    print(f"⚠ RoBERTa backup failed: {e2}")
                    
            # Fallback if both specialized models fail
            if not self.sentence_models:
                try:
                    model_name = 'all-MiniLM-L12-v2'
                    self.sentence_models['fallback'] = SentenceTransformer(model_name, device=self.device)
                    print(f"Fallback model {model_name} loaded on {self.device}")
                except Exception as e:
                    print(f"⚠ All models failed: {e}")
                    
        # Set primary model for backwards compatibility
        self.sentence_model = list(self.sentence_models.values())[0] if self.sentence_models else None
        
        if not self.sentence_models:
            print("No sentence transformers available")
            
        # Load larger spaCy model for better NER
        if SPACY_AVAILABLE:
            try:
                # Try to load the large model for better accuracy
                import spacy
                try:
                    self.nlp = spacy.load("en_core_web_lg")  # Large model for better accuracy
                    print("spaCy large model (en_core_web_lg) loaded")
                except OSError:
                    try:
                        self.nlp = spacy.load("en_core_web_md")  # Medium model fallback
                        print("spaCy medium model (en_core_web_md) loaded")
                    except OSError:
                        self.nlp = spacy.load("en_core_web_sm")  # Small model final fallback
                        print("spaCy small model (en_core_web_sm) loaded")
            except Exception as e:
                print(f"spaCy loading failed: {e}")
                self.nlp = None
        else:
            self.nlp = None
            print("spaCy not available")
            
        # Enhanced TF-IDF vectorizer for better feature extraction
        self.tfidf_vectorizer = TfidfVectorizer(
            ngram_range=(1, 4),  # Include up to 4-grams for better phrases
            max_features=5000,   # More features for better analysis
            stop_words='english',
            lowercase=True,
            min_df=1,           # Don't ignore rare terms in small datasets
            max_df=0.99         # Allow slightly more common terms
        )
        print("Enhanced TF-IDF vectorizer ready")
        
        print(f"High-performance models loaded successfully! Available models: {list(self.sentence_models.keys())}")
        
    def load_data(self, chapters_path: str, scores_path: str) -> Tuple[List[Dict], pd.DataFrame]:
        """Load chapters and scores data"""
        with open(chapters_path, 'r') as f:
            chapters = json.load(f)
            
        scores_df = pd.read_csv(scores_path)
        
        print(f"Loaded {len(chapters)} chapters and {len(scores_df)} transcript segments")
        return chapters, scores_df
        
    def extract_chapter_content(self, chapter: Dict, next_chapter: Dict, scores_df: pd.DataFrame) -> List[Dict]:
        """Extract all content for a specific chapter timeframe"""
        start_time = chapter['start']
        end_time = next_chapter['start'] if next_chapter else scores_df['end'].max()
        
        # Get all segments within this chapter
        chapter_segments = scores_df[
            (scores_df['start'] >= start_time) & 
            (scores_df['start'] < end_time)
        ].copy()
        
        return chapter_segments.to_dict('records')
        
    def extract_features(self, segments: List[Dict], model_name: str = None) -> Dict[str, Any]:
        """Extract features from chapter segments, focusing on high-scoring content"""
        if not segments:
            return {}
            
        # Sort segments by score (higher = more relevant)
        segments_sorted = sorted(segments, key=lambda x: x['score'], reverse=True)
        
        # Focus on top-scoring segments (most relevant content)
        high_score_threshold = 0.7  # Focus on segments with score > 0.7
        high_scoring_segments = [seg for seg in segments_sorted if seg['score'] > high_score_threshold]
        
        # If no high-scoring segments, take top 30% of segments
        if not high_scoring_segments:
            top_count = max(1, len(segments_sorted) // 3)
            high_scoring_segments = segments_sorted[:top_count]
        
        # Combine text from most relevant segments
        high_relevance_text = ' '.join([seg['transcript'] for seg in high_scoring_segments])
        full_text = ' '.join([seg['transcript'] for seg in segments])
        scores = [seg['score'] for seg in segments]
        
        features = {
            'full_text': full_text,
            'high_relevance_text': high_relevance_text,  # Focus on this for titles
            'avg_score': np.mean(scores),
            'max_score': np.max(scores),
            'high_score_segments': len(high_scoring_segments),
            'text_length': len(full_text),
            'segment_count': len(segments),
            'model_name': model_name or 'default'
        }
        
        # Extract entities from high-relevance text
        entities = self._extract_entities(high_relevance_text)
        features['entities'] = entities
        
        # Extract key phrases from high-relevance text
        key_phrases = self._extract_key_phrases(high_relevance_text)
        features['key_phrases'] = key_phrases
        
        # Get embeddings if available (use high-relevance text)
        if self.sentence_models and model_name and model_name in self.sentence_models:
            embeddings = self._get_embeddings(high_relevance_text, model_name)
            features['embeddings'] = embeddings
        elif self.sentence_model:
            embeddings = self._get_embeddings(high_relevance_text)
            features['embeddings'] = embeddings
        
        return features
        
    def _extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract entities using available methods"""
        entities = defaultdict(list)
        
        if self.nlp:
            # Use spaCy for entity extraction
            doc = self.nlp(text)
            for ent in doc.ents:
                if ent.label_ not in ['CARDINAL', 'ORDINAL', 'PERCENT', 'MONEY']:
                    entities[ent.label_].append(ent.text)
        else:
            # Fallback: simple pattern matching for common entities
            # Names (capitalized words)
            names = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
            if names:
                entities['PERSON'] = list(set(names))[:5]
                
            # Years
            years = re.findall(r'\b(19|20)\d{2}\b', text)
            if years:
                entities['DATE'] = list(set(years))[:3]
                
        # Clean and deduplicate
        cleaned_entities = {}
        for label, items in entities.items():
            cleaned = list(set([item.strip() for item in items if len(item.strip()) > 1]))
            if cleaned:
                cleaned_entities[label] = cleaned[:5]  # Top 5 per category
                
        return cleaned_entities
        
    def _extract_key_phrases(self, text: str) -> List[str]:
        """Extract key phrases using TF-IDF and patterns, focusing on meaningful content"""
        key_phrases = []
        
        # TF-IDF based extraction
        try:
            tfidf_matrix = self.tfidf_vectorizer.fit_transform([text])
            feature_names = self.tfidf_vectorizer.get_feature_names_out()
            scores = tfidf_matrix.toarray()[0]
            
            # Get top phrases with higher threshold
            top_indices = scores.argsort()[-20:][::-1]  # More candidates
            for idx in top_indices:
                if scores[idx] > 0.1:  # Higher threshold for quality
                    phrase = feature_names[idx]
                    # Focus on meaningful phrases
                    if len(phrase.split()) >= 1 and len(phrase) > 3:
                        key_phrases.append(phrase)
        except Exception as e:
            print(f"TF-IDF extraction failed: {e}")
            
        # Pattern-based phrase extraction for important concepts
        if self.nlp:
            doc = self.nlp(text)
            # Noun phrases that might be important
            for chunk in doc.noun_chunks:
                chunk_text = chunk.text.lower().strip()
                if 2 <= len(chunk_text.split()) <= 5 and len(chunk_text) > 5:
                    # Filter out generic phrases
                    if not any(generic in chunk_text for generic in ['this', 'that', 'these', 'those', 'some', 'many']):
                        key_phrases.append(chunk_text)
        
        # Remove duplicates and return top phrases
        unique_phrases = list(set(key_phrases))
        return unique_phrases[:15]
        
    def _identify_content_type(self, text: str) -> List[str]:
        """Dynamically identify content characteristics from actual text"""
        content_types = []
        
        # Use TF-IDF to find the most important terms, then categorize dynamically
        try:
            # Simple TF-IDF to find important terms
            words = text.lower().split()
            word_freq = Counter(words)
            
            # Get most frequent meaningful words (excluding common stop words)
            stop_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'was', 'are', 'were', 'a', 'an'}
            important_words = [word for word, count in word_freq.most_common(20) 
                             if len(word) > 3 and word not in stop_words]
            
            # Dynamically categorize based on actual content
            if important_words:
                content_types.extend(important_words[:5])  # Top 5 important words as content types
                
        except Exception as e:
            print(f"Content type identification failed: {e}")
                
        return content_types
        
    def _identify_educational_patterns(self, text: str) -> List[str]:
        """Dynamically identify patterns from actual content structure"""
        patterns = []
        
        # Analyze sentence patterns rather than hardcoding
        if self.nlp:
            doc = self.nlp(text)
            
            # Look for question patterns
            questions = [sent.text for sent in doc.sents if sent.text.strip().endswith('?')]
            if questions:
                patterns.append('questioning')
                
            # Look for explanation patterns (sentences with "because", "since", "due to")
            explanation_indicators = ['because', 'since', 'due to', 'as a result', 'therefore']
            for sent in doc.sents:
                if any(indicator in sent.text.lower() for indicator in explanation_indicators):
                    patterns.append('explanation')
                    break
                    
            # Look for sequential patterns (first, second, then, next, finally)
            sequence_indicators = ['first', 'second', 'third', 'then', 'next', 'finally', 'last']
            for sent in doc.sents:
                if any(indicator in sent.text.lower() for indicator in sequence_indicators):
                    patterns.append('sequential')
                    break
        else:
            # Simple pattern detection without spaCy
            text_lower = text.lower()
            if '?' in text:
                patterns.append('questioning')
            if any(word in text_lower for word in ['because', 'therefore', 'as a result']):
                patterns.append('explanation')
            if any(word in text_lower for word in ['first', 'second', 'then', 'next', 'finally']):
                patterns.append('sequential')
                
        return patterns
        
    def _get_embeddings(self, text: str, model_name: str = None) -> np.ndarray:
        """Get semantic embeddings using GPU acceleration if available"""
        if model_name and model_name in self.sentence_models:
            # Use specific model
            model = self.sentence_models[model_name]
            return model.encode(
                text, 
                convert_to_tensor=False,
                device=self.device,
                show_progress_bar=False,
                batch_size=1
            )
        elif self.sentence_model:
            # Use default model
            return self.sentence_model.encode(
                text, 
                convert_to_tensor=False,
                device=self.device,
                show_progress_bar=False,
                batch_size=1
            )
        return None
        
    def generate_title_candidates(self, features: Dict[str, Any]) -> List[str]:
        """Generate title candidates focusing on actual content from high-scoring segments"""
        candidates = []
        
        # Strategy 1: Direct entity-based titles
        candidates.extend(self._generate_entity_titles(features))
        
        # Strategy 2: Key phrase titles (from high-relevance content)
        candidates.extend(self._generate_phrase_titles(features))
        
        # Strategy 3: Content-specific titles
        candidates.extend(self._generate_content_specific_titles(features))
        
        # Strategy 4: Simple descriptive titles
        candidates.extend(self._generate_descriptive_titles(features))
        
        return list(set(candidates))  # Remove duplicates
        
    def _generate_entity_titles(self, features: Dict[str, Any]) -> List[str]:
        """Generate titles based on actual named entities found - completely dynamic"""
        titles = []
        entities = features.get('entities', {})
        key_phrases = features.get('key_phrases', [])
        
        # Use entities directly without hardcoded templates
        for entity_type, entity_list in entities.items():
            for entity in entity_list[:3]:  # Top 3 entities per type
                if len(entity.strip()) > 2:
                    # Just use the entity name as-is
                    clean_entity = entity.strip()
                    titles.append(clean_entity)
                    
                    # Only add "The" if it makes sense contextually
                    if not clean_entity.lower().startswith('the '):
                        titles.append(f"The {clean_entity}")
        
        # Combine entities with contextual phrases from the content
        if entities and key_phrases:
            # Find the most relevant entity
            all_entities = []
            for entity_list in entities.values():
                all_entities.extend(entity_list[:2])
            
            # Combine with top key phrases naturally
            for entity in all_entities[:2]:
                for phrase in key_phrases[:2]:
                    if len(phrase) > 3 and entity.lower() not in phrase.lower():
                        # Create natural combinations
                        clean_phrase = phrase.title()
                        titles.append(f"{entity}: {clean_phrase}")
                        titles.append(f"{clean_phrase} - {entity}")
                
        return titles
        
    def _generate_content_specific_titles(self, features: Dict[str, Any]) -> List[str]:
        """Generate titles based on dynamically extracted content without hardcoded patterns"""
        titles = []
        entities = features.get('entities', {})
        key_phrases = features.get('key_phrases', [])
        
        # Use entities and phrases in their natural context
        all_entities = []
        for entity_list in entities.values():
            all_entities.extend(entity_list[:2])
            
        # Create titles from key phrases directly
        for phrase in key_phrases[:5]:
            if len(phrase) > 4:
                clean_phrase = phrase.title().strip()
                titles.append(clean_phrase)
                
        # Combine entities with phrases naturally (no forced templates)
        for entity in all_entities[:3]:
            if len(entity) > 2:
                titles.append(entity.strip())
                
                # Look for natural combinations in the content
                for phrase in key_phrases[:3]:
                    if entity.lower() not in phrase.lower() and len(phrase) > 4:
                        # Only combine if it creates a meaningful title
                        combined = f"{entity} {phrase}".title()
                        if len(combined) <= 60:
                            titles.append(combined)
                            
        return titles
        
    def _generate_descriptive_titles(self, features: Dict[str, Any]) -> List[str]:
        """Generate simple descriptive titles"""
        titles = []
        key_phrases = features.get('key_phrases', [])
        
        # Use the most important phrases directly
        for phrase in key_phrases[:5]:
            clean_phrase = phrase.title().strip()
            if 5 <= len(clean_phrase) <= 50:
                # Add the phrase as-is if it's meaningful
                if not any(generic in clean_phrase.lower() for generic in ['this', 'that', 'some', 'many', 'other']):
                    titles.append(clean_phrase)
                    
        return titles
        
    def _generate_phrase_titles(self, features: Dict[str, Any]) -> List[str]:
        """Generate titles from key phrases found in high-relevance content"""
        titles = []
        phrases = features.get('key_phrases', [])
        
        for phrase in phrases[:10]:
            # Clean and process the phrase
            clean_phrase = phrase.strip()
            if 3 <= len(clean_phrase) <= 60:
                # Capitalize properly
                title_phrase = ' '.join(word.capitalize() for word in clean_phrase.split())
                titles.append(title_phrase)
                
                # Add a few variations for important phrases
                if len(clean_phrase) > 8 and not title_phrase.startswith('The'):
                    titles.append(f"The {title_phrase}")
                
        return titles
        
    def score_titles(self, candidates: List[str], features: Dict[str, Any], original_name: str) -> List[Tuple[str, float]]:
        """Score title candidates"""
        scored_titles = []
        
        for title in candidates:
            score = self._calculate_title_score(title, features, original_name)
            scored_titles.append((title, score))
            
        # Sort by score descending
        scored_titles.sort(key=lambda x: x[1], reverse=True)
        return scored_titles
        
    def _calculate_title_score(self, title: str, features: Dict[str, Any], original_name: str) -> float:
        """Calculate score for a title candidate based on relevance and quality"""
        score = 0.0
        model_name = features.get('model_name', 'default')
        
        # Length score (20-70 chars optimal for YouTube)
        length = len(title)
        if 20 <= length <= 70:
            score += 1.5
        elif 15 <= length < 20 or 70 < length <= 90:
            score += 1.0
        else:
            score += 0.3
            
        # Boost score based on high-relevance content quality
        avg_score = features.get('avg_score', 0.5)
        max_score = features.get('max_score', 0.5)
        
        # Higher weight for chapters with high-scoring content
        content_quality_bonus = (avg_score * 0.5 + max_score * 0.5) * 2.0
        score += content_quality_bonus
        
        # Semantic similarity if available (use model-specific embeddings)
        if features.get('embeddings') is not None:
            try:
                # Use the same model that generated the content embeddings
                if model_name in self.sentence_models:
                    model = self.sentence_models[model_name]
                else:
                    model = self.sentence_model
                    
                if model:
                    title_embedding = model.encode(
                        title, 
                        convert_to_tensor=False,
                        device=self.device,
                        show_progress_bar=False
                    )
                    content_embedding = features['embeddings']
                    similarity = cosine_similarity([title_embedding], [content_embedding])[0][0]
                    score += similarity * 4.0  # Higher weight for high-quality semantic similarity
            except Exception as e:
                print(f"⚠ Similarity calculation failed: {e}")
                pass
                
        # Entity presence (more weight for actual entities found)
        entities = features.get('entities', {})
        title_lower = title.lower()
        entity_bonus = 0.0
        for entity_type, entity_list in entities.items():
            for entity in entity_list:
                if entity.lower() in title_lower:
                    entity_bonus += 0.8  # Higher bonus for entity matches
        score += min(entity_bonus, 2.0)
                    
        # Key phrase presence (from high-relevance content)
        key_phrases = features.get('key_phrases', [])
        phrase_bonus = 0.0
        for phrase in key_phrases[:5]:  # Focus on top phrases
            if phrase.lower() in title_lower:
                phrase_bonus += 0.6
        score += min(phrase_bonus, 1.5)
                
        # Penalize overly generic titles (but don't hardcode specific penalty words)
        title_words = title_lower.split()
        generic_score = 0
        
        # Penalize very short or very generic single-word titles
        if len(title_words) == 1 and len(title) < 8:
            generic_score += 0.5
            
        # Penalize titles that are mostly common words
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        common_word_ratio = sum(1 for word in title_words if word in common_words) / len(title_words)
        if common_word_ratio > 0.6:
            generic_score += 0.3
            
        score -= generic_score
            
        # Avoid duplicating original name
        if title.lower() == original_name.lower():
            score -= 2.0
            
        return max(score, 0.0)  # Ensure non-negative
        
    def generate_chapter_titles(self, chapters_path: str, scores_path: str, output_path: str = None) -> Dict[str, List[Dict]]:
        """Main function to generate enhanced chapter titles using multiple models"""
        print("Starting high-performance GPU chapter title generation with multiple models...")
        
        # Load data
        chapters, scores_df = self.load_data(chapters_path, scores_path)
        
        # Generate titles for each available model
        all_results = {}
        available_models = list(self.sentence_models.keys()) if self.sentence_models else ['default']
        
        for model_name in available_models:
            print(f"\nGenerating titles with {model_name.upper()} model...")
            enhanced_chapters = []
            
            for i, chapter in enumerate(chapters):
                print(f"Processing chapter {i+1}/{len(chapters)} with {model_name}: {chapter['name']}")
                
                # Get next chapter for time boundary
                next_chapter = chapters[i+1] if i+1 < len(chapters) else None
                
                # Extract content for this chapter
                segments = self.extract_chapter_content(chapter, next_chapter, scores_df)
                
                if not segments:
                    print(f"  No content found for chapter {i+1}")
                    enhanced_chapters.append(chapter)
                    continue
                    
                # Extract features with specific model
                features = self.extract_features(segments, model_name)
                
                # Generate title candidates
                candidates = self.generate_title_candidates(features)
                
                if not candidates:
                    print(f"  No candidates generated for chapter {i+1}, keeping original")
                    enhanced_chapters.append(chapter)
                    continue
                    
                # Score and select best title
                scored_titles = self.score_titles(candidates, features, chapter['name'])
                
                if scored_titles and scored_titles[0][1] > 0.5:  # Only use if score is decent
                    best_title = scored_titles[0][0]
                    print(f"  Generated: '{best_title}' (score: {scored_titles[0][1]:.3f})")
                    
                    enhanced_chapter = {
                        'name': best_title,
                        'start': chapter['start'],
                        'original_name': chapter['name'],
                        'score': scored_titles[0][1],
                        'model': model_name
                    }
                else:
                    print(f"  Keeping original: '{chapter['name']}'")
                    enhanced_chapter = chapter.copy()
                    enhanced_chapter['model'] = model_name
                    
                enhanced_chapters.append(enhanced_chapter)
            
            all_results[model_name] = enhanced_chapters
            
            # Only save individual model results if output_path is provided (manual mode)
            if output_path:
                # Save detailed results to details folder inside segments
                segments_dir = Path("output/segments")
                details_dir = segments_dir / "details"
                details_dir.mkdir(parents=True, exist_ok=True)
                
                model_output_path = details_dir / f"{Path(output_path).stem}_{model_name}.json"
                with open(model_output_path, 'w') as f:
                    json.dump(enhanced_chapters, f, indent=2)
                print(f"Enhanced chapters for {model_name} saved to: {model_output_path}")
                
                # Ensure segments folder exists
                segments_dir.mkdir(parents=True, exist_ok=True)
                
                simple_chapters = []
                for chapter in enhanced_chapters:
                    simple_chapter = {
                        'name': chapter['name'],
                        'start': chapter['start']
                    }
                    simple_chapters.append(simple_chapter)
                
                simple_output_path = segments_dir / f"{Path(output_path).stem}_chapters_{model_name}.json"
                with open(simple_output_path, 'w') as f:
                    json.dump(simple_chapters, f, indent=2)
                print(f"Simple chapter format for {model_name} saved to: {simple_output_path}")
        
        return all_results

def detect_matching_files():
    """Detect matching chapter and score files"""
    chapters_dir = Path("output/chapters")
    scores_dir = Path("output/scores")
    
    if not chapters_dir.exists() or not scores_dir.exists():
        print("⚠ Required directories not found. Please ensure output/chapters and output/scores exist.")
        return []
    
    # Find all chapter files
    chapter_files = list(chapters_dir.glob("*_chapters.json"))
    matching_pairs = []
    
    for chapter_file in chapter_files:
        # Extract base name (e.g., "robbers_cave" from "robbers_cave_chapters.json")
        base_name = chapter_file.stem.replace("_chapters", "")
        
        # Look for corresponding score file
        score_file = scores_dir / f"{base_name}_export.csv"
        
        if score_file.exists():
            matching_pairs.append({
                'base_name': base_name,
                'chapters_path': str(chapter_file),
                'scores_path': str(score_file),
                'display_name': base_name.replace('_', ' ').title()
            })
    
    return matching_pairs

def save_enhanced_segments(chapters_with_segments: List[Dict], base_name: str, model_name: str):
    """Save enhanced chapters and details to separate directories"""
    # Create directory structures - details folder is inside segments
    segments_dir = Path("output/segments") / model_name
    details_dir = Path("output/segments") / "details" / model_name
    segments_dir.mkdir(parents=True, exist_ok=True)
    details_dir.mkdir(parents=True, exist_ok=True)
    
    # Save detailed data to details folder (inside segments)
    detailed_output_file = details_dir / f"{base_name}_enhanced_chapters_{model_name}.json"
    with open(detailed_output_file, 'w') as f:
        json.dump(chapters_with_segments, f, indent=2)
    
    print(f"Enhanced chapters with segments saved to: {detailed_output_file}")
    
    # Create simple chapter format (name and start only) for segments folder
    simple_chapters = []
    for chapter in chapters_with_segments:
        simple_chapter = {
            'name': chapter['name'],
            'start': chapter['start']
        }
        simple_chapters.append(simple_chapter)
    
    # Save simple format file to segments folder
    simple_output_file = segments_dir / f"{base_name}_chapters_{model_name}.json"
    with open(simple_output_file, 'w') as f:
        json.dump(simple_chapters, f, indent=2)
    
    print(f"Simple chapter format saved to: {simple_output_file}")
    
    return str(detailed_output_file)

def main():
    parser = argparse.ArgumentParser(description="Generate engaging YouTube-style chapter titles (High-Performance GPU)")
    parser.add_argument("--chapters", help="Path to chapters.json file (optional if using auto-detection)")
    parser.add_argument("--scores", help="Path to scores.csv file (optional if using auto-detection)")
    parser.add_argument("--output", help="Output path for enhanced chapters")
    parser.add_argument("--device", default="auto", help="Device to use (auto/cuda/cpu - auto will detect GPU)")
    parser.add_argument("--auto", action="store_true", help="Auto-detect matching files and prompt for selection")
    
    args = parser.parse_args()
    
    # Handle device selection
    device = None if args.device == "auto" else args.device
    
    # Initialize generator with GPU optimization
    generator = HighPerformanceChapterTitleGenerator(device=device)
    
    # Auto-detection mode or manual file specification
    if args.auto or (not args.chapters and not args.scores):
        print("Auto-detecting matching chapter and score files...")
        matching_pairs = detect_matching_files()
        
        if not matching_pairs:
            print("No matching chapter/score file pairs found.")
            print("   Please ensure files exist in output/chapters/ and output/scores/")
            return
        
        print(f"\nFound {len(matching_pairs)} matching file pairs:")
        print("=" * 60)
        for i, pair in enumerate(matching_pairs, 1):
            print(f"{i:2d}. {pair['display_name']}")
            print(f"    Chapters: {pair['chapters_path']}")
            print(f"    Scores:   {pair['scores_path']}")
            print()
        
        # Get user selection
        print("Select files to process:")
        print("eg. '1', 1,2 or 'all'")
        
        while True:
            selection = input("\nYour choice: ").strip().lower()
            
            if selection == 'all':
                selected_pairs = matching_pairs
                break
            elif selection.isdigit():
                idx = int(selection) - 1
                if 0 <= idx < len(matching_pairs):
                    selected_pairs = [matching_pairs[idx]]
                    break
                else:
                    print(f"Invalid selection. Please enter 1-{len(matching_pairs)}")
            elif ',' in selection:
                try:
                    indices = [int(x.strip()) - 1 for x in selection.split(',')]
                    if all(0 <= idx < len(matching_pairs) for idx in indices):
                        selected_pairs = [matching_pairs[idx] for idx in indices]
                        break
                    else:
                        print(f"Invalid selection. Please enter numbers between 1-{len(matching_pairs)}")
                except ValueError:
                    print("Invalid format. Use numbers separated by commas (e.g., '1,2,3')")
            else:
                print("Invalid input. Enter 'all', a single number, or comma-separated numbers.")
        
        print(f"\nProcessing {len(selected_pairs)} file pair(s)...")
        
        # Process each selected pair
        all_results = {}
        for pair in selected_pairs:
            print(f"\n{'='*80}")
            print(f"Processing: {pair['display_name']}")
            print(f"{'='*80}")
            
            # Generate enhanced chapters for this pair
            pair_results = generator.generate_chapter_titles(
                pair['chapters_path'], 
                pair['scores_path']
            )
            
            # Save enhanced chapters with segments for each model
            for model_name, enhanced_chapters in pair_results.items():
                print(f"\nSaving {model_name.upper()} results for {pair['display_name']}...")
                
                # Load the original scores data to include segments
                scores_df = pd.read_csv(pair['scores_path'])
                
                # Add segment data to each chapter
                chapters_with_segments = []
                for i, chapter in enumerate(enhanced_chapters):
                    next_chapter = enhanced_chapters[i+1] if i+1 < len(enhanced_chapters) else None
                    segments = generator.extract_chapter_content(chapter, next_chapter, scores_df)
                    
                    chapter_with_segments = chapter.copy()
                    chapter_with_segments['segments'] = segments
                    chapter_with_segments['segment_count'] = len(segments)
                    chapters_with_segments.append(chapter_with_segments)
                
                # Save to output/segments/{model}/
                output_file = save_enhanced_segments(
                    chapters_with_segments, 
                    pair['base_name'], 
                    model_name
                )
            
            all_results[pair['base_name']] = pair_results
        
        # Display summary
        print(f"\nPROCESSING COMPLETE!")
        print("=" * 80)
        print(f"Processed {len(selected_pairs)} dataset(s)")
        print(f"Simple chapters saved to: output/segments/[model]/[dataset]_chapters_[model].json")
        print(f"Detailed files saved to: output/segments/details/[model]/[dataset]_enhanced_chapters_[model].json")
        
        for pair in selected_pairs:
            if pair['base_name'] in all_results:
                pair_results = all_results[pair['base_name']]
                print(f"\n{pair['display_name']}:")
                for model_name, chapters in pair_results.items():
                    avg_score = np.mean([ch.get('score', 0) for ch in chapters if 'score' in ch])
                    improved_count = sum(1 for ch in chapters if 'original_name' in ch and ch['name'] != ch['original_name'])
                    print(f"   {model_name.upper():>8}: {improved_count}/{len(chapters)} chapters improved (avg score: {avg_score:.3f})")
    
    else:
        # Manual mode (original behavior)
        if not args.chapters or not args.scores:
            print("❌ Please provide both --chapters and --scores arguments, or use --auto for auto-detection")
            return
        
        # Generate output path if not provided
        output_path = args.output
        if not output_path:
            base_name = Path(args.chapters).stem.replace('_chapters', '')
            output_path = f"{base_name}_enhanced_chapters.json"
            
        all_enhanced_chapters = generator.generate_chapter_titles(
            args.chapters, 
            args.scores, 
            output_path
        )
        
        # Display results for each model
        for model_name, enhanced_chapters in all_enhanced_chapters.items():
            print(f"\nResults from {model_name.upper()} Model:")
            print("=" * 80)
            print(f"Generated {len(enhanced_chapters)} enhanced chapters")
            print(f"\nEnhanced Chapters ({model_name.upper()}):")
            print("=" * 60)
            for i, chapter in enumerate(enhanced_chapters):
                print(f"{i+1:2d}. {chapter['name']}")
                if 'original_name' in chapter and chapter['name'] != chapter['original_name']:
                    print(f"    Original: {chapter['original_name']}")
                print(f"    Start: {chapter['start']}s")
                if 'score' in chapter:
                    print(f"    Score: {chapter['score']:.3f}")
                print()
        # Summary comparison
        if len(all_enhanced_chapters) > 1:
            print("\nMODEL COMPARISON SUMMARY:")
            print("=" * 80)
            for model_name, chapters in all_enhanced_chapters.items():
                avg_score = np.mean([ch.get('score', 0) for ch in chapters if 'score' in ch])
                improved_count = sum(1 for ch in chapters if 'original_name' in ch and ch['name'] != ch['original_name'])
                print(f"{model_name.upper():>10}: Avg Score: {avg_score:.3f} | Improved: {improved_count}/{len(chapters)} chapters")

if __name__ == "__main__":
    main()
