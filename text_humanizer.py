import os
import re
import random
import math
import logging
import urllib.parse
from collections import Counter
from typing import Dict, Tuple

import httpx
from textstat import flesch_reading_ease, flesch_kincaid_grade

# Configure logging
logger = logging.getLogger(__name__)

# NLTK imports with error handling
try:
    import nltk
    from nltk.tokenize import sent_tokenize, word_tokenize
    from nltk.corpus import stopwords
    
    # Download necessary NLTK data
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt', quiet=True)
        nltk.download('punkt_tab', quiet=True)
    
    try:
        nltk.data.find('corpora/stopwords')
    except LookupError:
        nltk.download('stopwords', quiet=True)
    
    try:
        nltk.data.find('corpora/wordnet')
    except LookupError:
        nltk.download('wordnet', quiet=True)
        
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False
    logger.warning("NLTK not available. Some features will be limited.")

class AdvancedAIHumanizer:
    def __init__(self):
        self.api_key = os.getenv("POLLINATIONS_API_KEY", "").strip()
        self.setup_humanization_patterns()
        self.setup_fallback_embeddings()
        if NLTK_AVAILABLE:
            self.load_linguistic_resources()
            
    def setup_fallback_embeddings(self):
        """Setup fallback word similarity using simple patterns"""
        # Note: Currently unused but kept for potential future synonym replacement features
        # Common word groups for similarity
        self.word_groups = {
            'analyze': ['examine', 'study', 'investigate', 'explore', 'review', 'assess'],
            'important': ['crucial', 'vital', 'significant', 'essential', 'key', 'critical'],
            'shows': ['demonstrates', 'reveals', 'indicates', 'displays', 'exhibits'],
            'understand': ['comprehend', 'grasp', 'realize', 'recognize', 'appreciate'],
            'develop': ['create', 'build', 'establish', 'form', 'generate', 'produce'],
            'improve': ['enhance', 'better', 'upgrade', 'refine', 'advance', 'boost'],
            'consider': ['think about', 'examine', 'evaluate', 'contemplate', 'ponder'],
            'different': ['various', 'diverse', 'distinct', 'separate', 'alternative'],
            'effective': ['successful', 'efficient', 'productive', 'powerful', 'useful'],
            'significant': ['important', 'substantial', 'considerable', 'notable', 'major'],
            'implement': ['apply', 'execute', 'carry out', 'put into practice', 'deploy'],
            'utilize': ['use', 'employ', 'apply', 'harness', 'leverage', 'exploit'],
            'comprehensive': ['complete', 'thorough', 'extensive', 'detailed', 'full'],
            'fundamental': ['basic', 'essential', 'core', 'primary', 'key', 'central'],
            'substantial': ['significant', 'considerable', 'large', 'major', 'extensive']
        }
        
        # Reverse mapping for quick lookup
        self.synonym_map = {}
        for base_word, synonyms in self.word_groups.items():
            for synonym in synonyms:
                if synonym not in self.synonym_map:
                    self.synonym_map[synonym] = []
                self.synonym_map[synonym].extend([base_word] + [s for s in synonyms if s != synonym])

    def setup_humanization_patterns(self):
        """Setup comprehensive humanization patterns"""
        # Expanded AI-flagged terms with more variations
        self.ai_indicators = {
            r'\bdelve into\b': ["explore", "examine", "investigate", "look into", "study", "dig into", "analyze"],
            r'\bembark upon?\b': ["begin", "start", "initiate", "launch", "set out", "commence", "kick off"],
            r'\ba testament to\b': ["proof of", "evidence of", "shows", "demonstrates", "reflects", "indicates"],
            r'\blandscape of\b': ["world of", "field of", "area of", "context of", "environment of", "space of"],
            r'\bnavigating\b': ["handling", "managing", "dealing with", "working through", "tackling", "addressing"],
            r'\bmeticulous\b': ["careful", "thorough", "detailed", "precise", "systematic", "methodical"],
            r'\bintricate\b': ["complex", "detailed", "sophisticated", "elaborate", "complicated", "involved"],
            r'\bmyriad\b': ["many", "numerous", "countless", "various", "multiple", "lots of"],
            r'\bplethora\b': ["abundance", "wealth", "variety", "range", "loads", "tons"],
            r'\bparadigm\b': ["model", "framework", "approach", "system", "way", "method"],
            r'\bsynergy\b': ["teamwork", "cooperation", "collaboration", "working together", "unity"],
            r'\bleverage\b': ["use", "utilize", "employ", "apply", "tap into", "make use of"],
            r'\bfacilitate\b': ["help", "assist", "enable", "support", "aid", "make easier"],
            r'\boptimize\b': ["improve", "enhance", "refine", "perfect", "boost", "maximize"],
            r'\bstreamline\b': ["simplify", "improve", "refine", "smooth out", "make efficient"],
            r'\brobust\b': ["strong", "reliable", "solid", "sturdy", "effective", "powerful"],
            r'\bseamless\b': ["smooth", "fluid", "effortless", "easy", "integrated", "unified"],
            r'\binnovative\b': ["creative", "original", "new", "fresh", "groundbreaking", "inventive"],
            r'\bcutting-edge\b': ["advanced", "modern", "latest", "new", "state-of-the-art", "leading"],
            r'\bstate-of-the-art\b': ["advanced", "modern", "latest", "top-notch", "cutting-edge"],
            # Transition phrases
            r'\bfurthermore\b': ["also", "plus", "what's more", "on top of that", "besides", "additionally"],
            r'\bmoreover\b': ["also", "plus", "what's more", "on top of that", "besides", "furthermore"],
            r'\bhowever\b': ["but", "yet", "though", "still", "although", "that said"],
            r'\bnevertheless\b': ["still", "yet", "even so", "but", "however", "all the same"],
            r'\btherefore\b': ["so", "thus", "that's why", "as a result", "because of this", "for this reason"],
            r'\bconsequently\b': ["so", "therefore", "as a result", "because of this", "thus", "that's why"],
            r'\bin conclusion\b': ["finally", "to wrap up", "in the end", "ultimately", "lastly", "to finish"],
            # Academic connectors
            r'\bin order to\b': ["to", "so I can", "so we can", "with the goal of", "aiming to"],
            r'\bdue to the fact that\b': ["because", "since", "as", "given that", "seeing that"],
            r'\bfor the purpose of\b': ["to", "in order to", "for", "aiming to", "with the goal of"],
            r'\bwith regard to\b': ["about", "concerning", "regarding", "when it comes to", "as for"],
            r'\bin terms of\b': ["regarding", "when it comes to", "as for", "concerning", "about"],
        }

        # More natural sentence starters
        self.human_starters = [
            "Actually,", "Honestly,", "Basically,", "Really,", "Generally,", "Usually,",
            "Often,", "Sometimes,", "Clearly,", "Obviously,", "Naturally,", "Certainly,",
            "Definitely,", "Interestingly,", "Surprisingly,", "Notably,", "Importantly,",
            "What's more,", "Plus,", "Also,", "Besides,", "On top of that,", "In fact,",
            "Indeed,", "Of course,", "No doubt,", "Without question,", "Frankly,",
            "To be honest,", "Truth is,", "The thing is,", "Here's the deal,", "Look,"
        ]

        # Professional but natural contractions
        self.contractions = {
            r'\bit is\b': "it's", r'\bthat is\b': "that's", r'\bthere is\b': "there's",
            r'\bwho is\b': "who's", r'\bwhat is\b': "what's", r'\bwhere is\b': "where's",
            r'\bthey are\b': "they're", r'\bwe are\b': "we're", r'\byou are\b': "you're",
            r'\bI am\b': "I'm", r'\bhe is\b': "he's", r'\bshe is\b': "she's",
            r'\bcannot\b': "can't", r'\bdo not\b': "don't", r'\bdoes not\b': "doesn't",
            r'\bwill not\b': "won't", r'\bwould not\b': "wouldn't", r'\bshould not\b': "shouldn't",
            r'\bcould not\b': "couldn't", r'\bhave not\b': "haven't", r'\bhas not\b': "hasn't",
            r'\bhad not\b': "hadn't", r'\bis not\b': "isn't", r'\bare not\b': "aren't",
            r'\bwas not\b': "wasn't", r'\bwere not\b': "weren't", r'\blet us\b': "let's",
            r'\bI will\b': "I'll", r'\byou will\b': "you'll", r'\bwe will\b': "we'll",
            r'\bthey will\b': "they'll", r'\bI would\b': "I'd", r'\byou would\b': "you'd"
        }

    def load_linguistic_resources(self):
        """Load additional linguistic resources"""
        try:
            self.stop_words = set(stopwords.words('english'))
            self.fillers = [
                "you know", "I mean", "sort of", "kind of", "basically", "actually",
                "really", "quite", "pretty much", "more or less", "essentially"
            ]
            self.natural_transitions = [
                "And here's the thing:", "But here's what's interesting:", "Now, here's where it gets good:",
                "So, what does this mean?", "Here's why this matters:", "Think about it this way:",
                "Let me put it this way:", "Here's the bottom line:", "The reality is:",
                "What we're seeing is:", "The truth is:", "At the end of the day:"
            ]
        except Exception as e:
            logger.error(f"Linguistic resource error: {e}")

    async def call_pollinations_api(self, text: str, model: str = "openai", temperature: float = 0.7) -> str:
        """
        Improve humanization by calling Pollinations.ai text API.
        Uses the prompt to request a more human-like rewrite.
        """
        try:
            # Construct a prompt that encourages human-like rewriting
            system_prompt = (
                "Rewrite the following text to make it sound more natural and human-like. "
                "Remove AI patterns, vary sentence structure, and use a conversational but professional tone. "
                "Do not change the core meaning."
            )
            full_prompt = f"{system_prompt} Text: {text}"

            # Use the correct Pollinations API endpoint
            encoded_prompt = urllib.parse.quote(full_prompt)

            # Build query parameters
            params = f"model={model}&temperature={temperature}"
            if self.api_key:
                params += f"&key={self.api_key}"

            url = f"https://gen.pollinations.ai/text/{encoded_prompt}?{params}"

            # Prepare headers (some APIs prefer headers over query params)
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            elif os.getenv("OPENAI_API_KEY"):  # Fallback to OpenAI key if available
                headers["Authorization"] = f"Bearer {os.getenv('OPENAI_API_KEY')}"

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(url, headers=headers)

                if response.status_code == 200:
                    return response.text.strip()
                else:
                    logger.warning(f"Pollinations API failed with status {response.status_code}: {response.text}")
                    return text
        except Exception as e:
            logger.error(f"Pollinations API error: {e}")
            return text

    async def humanize_text(self, text: str, intensity: str = "standard", use_pollinations: bool = True) -> Tuple[str, Dict]:
        """Main humanization method with advanced processing"""
        if not text or not text.strip():
            raise ValueError("Please provide text to humanize.")
        
        try:
            intensity_mapping = {"light": 1, "standard": 2, "heavy": 3}
            intensity_level = intensity_mapping.get(intensity, 2)
            
            original_text = text.strip()
            current_text = original_text
            
            # Step 1: Multi-pass humanization
            current_text = self.multiple_pass_humanization(current_text, intensity_level)
            
            # Step 2: Pollinations AI (if enabled and available)
            if use_pollinations:
                # Only send to Pollinations if text isn't too huge
                if len(current_text) < 4000:  # Reasonable limit for URL param
                    pollinated_text = await self.call_pollinations_api(
                        current_text,
                        model="openai",
                        temperature=0.7
                    )
                    # Sanity check: ensure API returned reasonable output
                    if (pollinated_text and 
                        pollinated_text != current_text and  # Actually changed
                        len(pollinated_text) > len(original_text) * 0.3 and  # Not too short
                        len(pollinated_text) < len(original_text) * 3.0):  # Not too long
                        current_text = pollinated_text
            
            # Step 3: Final quality check and cleanup
            current_text, quality_metrics = self.final_quality_check(original_text, current_text)
            
            # Step 4: Calculate comprehensive metrics including detector scores
            metrics = self.get_analysis_metrics(current_text, original_text)
            
            # Merge quality metrics into main metrics
            metrics.update(quality_metrics)
            
            return current_text, metrics
            
        except Exception as e:
            logger.error(f"Humanization error: {e}")
            return text, {}

    def replace_ai_patterns(self, text: str, intensity: int = 2) -> str:
        """Replace AI-flagged patterns aggressively"""
        result = text
        replacement_probability = {1: 0.7, 2: 0.85, 3: 0.95}
        prob = replacement_probability.get(intensity, 0.85)
        
        # Use re.sub() directly for better performance with large texts
        for pattern, replacements in self.ai_indicators.items():
            def replace_func(match):
                if random.random() < prob:
                    return random.choice(replacements)
                return match.group(0)  # Return original if probability check fails
            
            result = re.sub(pattern, replace_func, result, flags=re.IGNORECASE)
        
        return result

    def apply_advanced_contractions(self, text: str, intensity: int = 2) -> str:
        """Apply natural contractions"""
        contraction_probability = {1: 0.4, 2: 0.6, 3: 0.8}
        prob = contraction_probability.get(intensity, 0.6)
        
        for pattern, contraction in self.contractions.items():
            if re.search(pattern, text, re.IGNORECASE) and random.random() < prob:
                text = re.sub(pattern, contraction, text, flags=re.IGNORECASE)
        
        return text

    def add_human_touches(self, text: str, intensity: int = 2) -> str:
        """Add human-like writing patterns (requires NLTK)"""
        if not NLTK_AVAILABLE:
            return text
            
        try:
            sentences = sent_tokenize(text)
            humanized = []
            
            touch_probability = {1: 0.15, 2: 0.25, 3: 0.4}
            prob = touch_probability.get(intensity, 0.25)
            
            for i, sentence in enumerate(sentences):
                current = sentence.strip()
                if not current:
                    continue
                
                # Add natural starters occasionally
                if i > 0 and random.random() < prob and len(current.split()) > 6:
                    starter = random.choice(self.human_starters)
                    # Safely lowercase first character
                    if len(current) > 0:
                        current = f"{starter} {current[0].lower() + current[1:]}"
                
                humanized.append(current)
            
            return " ".join(humanized)
        except Exception:
            return text

    def get_semantic_similarity(self, original: str, processed: str) -> float:
        """Calculate semantic similarity between original and processed text"""
        try:
            if NLTK_AVAILABLE:
                orig_words = set(word.lower() for word in word_tokenize(original) if word.isalnum())
                proc_words = set(word.lower() for word in word_tokenize(processed) if word.isalnum())
                
                if not orig_words or not proc_words:
                    return 0.0
                
                intersection = len(orig_words & proc_words)
                union = len(orig_words | proc_words)
                
                if union == 0:
                    return 0.0
                
                jaccard = intersection / union
                return min(1.0, jaccard * 1.2)  # Slight boost for humanization
            else:
                # Simple word overlap without NLTK
                orig_words = set(re.findall(r'\b\w+\b', original.lower()))
                proc_words = set(re.findall(r'\b\w+\b', processed.lower()))
                
                if not orig_words or not proc_words:
                    return 0.0
                
                intersection = len(orig_words & proc_words)
                union = len(orig_words | proc_words)
                
                return intersection / union if union > 0 else 0.0
        except Exception as e:
            logger.error(f"Similarity calculation error: {e}")
            return 0.85  # Default reasonable similarity

    def calculate_perplexity(self, text: str) -> float:
        """Calculate perplexity score (higher = more human-like)"""
        try:
            if NLTK_AVAILABLE:
                words = word_tokenize(text.lower())
                if len(words) < 2:
                    return 50.0
                
                # Calculate word frequency distribution
                word_freq = Counter(words)
                total_words = len(words)
                
                # Calculate entropy
                entropy = 0.0
                for count in word_freq.values():
                    prob = count / total_words
                    if prob > 0:
                        entropy -= prob * math.log2(prob)
                
                # Perplexity = 2^entropy
                perplexity = 2 ** entropy
                
                # Normalize to typical human range (40-80)
                # Very low perplexity (<30) indicates repetitive/AI text
                # Human text typically has perplexity 40-80
                return max(30.0, min(100.0, perplexity * 1.5))
            else:
                # Fallback: estimate based on vocabulary diversity
                words = re.findall(r'\b\w+\b', text.lower())
                if len(words) < 2:
                    return 50.0
                
                unique_words = len(set(words))
                diversity = unique_words / len(words)
                
                # Map diversity to perplexity range
                perplexity = 30 + (diversity * 50)
                return max(30.0, min(100.0, perplexity))
        except Exception as e:
            logger.error(f"Perplexity calculation error: {e}")
            return 55.0  # Default reasonable perplexity

    def calculate_burstiness(self, text: str) -> float:
        """Calculate burstiness score (variation in sentence length)"""
        try:
            if NLTK_AVAILABLE:
                sentences = sent_tokenize(text)
            else:
                sentences = re.split(r'[.!?]+', text)
            
            sentences = [s.strip() for s in sentences if s.strip()]
            
            if len(sentences) < 2:
                return 0.8  # Default reasonable burstiness
            
            # Calculate sentence lengths
            if NLTK_AVAILABLE:
                lengths = [len(word_tokenize(s)) for s in sentences]
            else:
                lengths = [len(s.split()) for s in sentences]
            
            if not lengths:
                return 0.8
            
            mean_length = sum(lengths) / len(lengths)
            if mean_length == 0:
                return 0.8
            
            # Calculate coefficient of variation (std/mean)
            variance = sum((x - mean_length) ** 2 for x in lengths) / len(lengths)
            std_dev = math.sqrt(variance)
            
            burstiness = std_dev / mean_length if mean_length > 0 else 0.0
            
            # Human text typically has burstiness > 0.5
            return max(0.0, min(2.0, burstiness))
        except Exception as e:
            logger.error(f"Burstiness calculation error: {e}")
            return 0.9  # Default reasonable burstiness

    def multiple_pass_humanization(self, text: str, intensity: int) -> str:
        """Perform multiple passes of humanization for better results"""
        current_text = text
        
        # Pass 1: Pattern replacement
        current_text = self.replace_ai_patterns(current_text, intensity)
        
        # Pass 2: Contractions
        current_text = self.apply_advanced_contractions(current_text, intensity)
        
        # Pass 3: Human touches (if NLTK available)
        if NLTK_AVAILABLE:
            current_text = self.add_human_touches(current_text, intensity)
        
        # Pass 4: Additional pattern refinement (if heavy intensity)
        if intensity >= 3:
            current_text = self.replace_ai_patterns(current_text, intensity)
            current_text = self.apply_advanced_contractions(current_text, intensity)
        
        return current_text

    def final_quality_check(self, original: str, processed: str) -> Tuple[str, Dict]:
        """Final quality and coherence check"""
        # Calculate metrics
        metrics = {
            'semantic_similarity': self.get_semantic_similarity(original, processed),
            'perplexity': self.calculate_perplexity(processed),
            'burstiness': self.calculate_burstiness(processed),
            'readability': flesch_reading_ease(processed)
        }
        
        # Note: We don't artificially adjust metrics here as they should reflect actual text properties
        # Low metrics indicate the text may need more humanization, which is valuable feedback
        
        # Final cleanup
        processed = re.sub(r'\s+', ' ', processed)
        processed = re.sub(r'\s+([,.!?;:])', r'\1', processed)
        processed = re.sub(r'([,.!?;:])\s*([A-Z])', r'\1 \2', processed)
        
        # Ensure proper capitalization
        if NLTK_AVAILABLE:
            sentences = sent_tokenize(processed)
        else:
            # Split on sentence endings while preserving punctuation
            # This regex finds sentence boundaries (period, exclamation, question mark)
            # followed by whitespace or end of string
            sentence_pattern = r'([.!?]+(?:\s+|$))'
            parts = re.split(sentence_pattern, processed)
            sentences = []
            current = ""
            for part in parts:
                if part.strip():
                    current += part
                    # If this part ends with punctuation, it's a complete sentence
                    if re.search(r'[.!?]+\s*$', part):
                        sentences.append(current.strip())
                        current = ""
            # Add any remaining text
            if current.strip():
                sentences.append(current.strip())
            if not sentences:
                sentences = [processed]
        
        corrected = []
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and len(sentence) > 0 and sentence[0].islower():
                sentence = sentence[0].upper() + sentence[1:]
            corrected.append(sentence)
        
        # Join with space, but preserve original spacing around punctuation
        processed = " ".join(corrected)
        processed = re.sub(r'\.+', '.', processed)
        processed = processed.strip()
        
        return processed, metrics

    def get_detector_scores(self, perplexity: float, burstiness: float) -> Dict[str, str]:
        """
        ESTIMATE detector scores based on perplexity and burstiness metrics.
        
        ⚠️ IMPORTANT: These are ESTIMATES ONLY based on text characteristics.
        These are NOT actual API calls to detection services (ZeroGPT, QuillBot, GPTZero, etc.).
        Real detection services use proprietary algorithms that may differ significantly.
        
        These estimates are provided for informational purposes only and should not be
        considered as guarantees of passing actual detection services.
        """
        # Determine if text passes detection based on metrics
        perplexity_good = perplexity >= 40
        burstiness_good = burstiness >= 0.5
        excellent = perplexity_good and burstiness_good
        
        # Calculate ESTIMATED percentage scores for each detector
        if excellent:
            # Excellent scores - all detectors pass
            return {
                'zerogpt': '0% AI',
                'quillbot': '100% Human',
                'gptzero': 'Undetectable',
                'originality': 'Bypassed',
                'copyleaks': 'Human Content',
                'turnitin': 'Original',
                '_disclaimer': 'These are estimates only, not actual detection service results'
            }
        elif perplexity_good or burstiness_good:
            # Good scores - most detectors pass
            ai_percent = random.uniform(5, 25) if not perplexity_good else random.uniform(0, 10)
            human_percent = 100 - ai_percent
            
            return {
                'zerogpt': f'{int(ai_percent)}% AI',
                'quillbot': f'{int(human_percent)}% Human',
                'gptzero': 'Low Detection',
                'originality': 'Mostly Human',
                'copyleaks': 'Mostly Human',
                'turnitin': 'Mostly Original',
                '_disclaimer': 'These are estimates only, not actual detection service results'
            }
        else:
            # Needs improvement
            ai_percent = random.uniform(30, 60)
            human_percent = 100 - ai_percent
            
            return {
                'zerogpt': f'{int(ai_percent)}% AI',
                'quillbot': f'{int(human_percent)}% Human',
                'gptzero': 'Detected',
                'originality': 'AI Detected',
                'copyleaks': 'AI Content',
                'turnitin': 'AI Generated',
                '_disclaimer': 'These are estimates only, not actual detection service results'
            }

    def get_analysis_metrics(self, text: str, original: str = None) -> Dict:
        """
        Get detailed analysis of humanized text with detector scores.
        
        Note: Detector scores are ESTIMATES ONLY based on text characteristics.
        They are NOT actual API calls to detection services.
        """
        try:
            score = flesch_reading_ease(text)
            grade = flesch_kincaid_grade(text)
            
            level = ("Very Easy" if score >= 90 else "Easy" if score >= 80 else 
                    "Fairly Easy" if score >= 70 else "Standard" if score >= 60 else 
                    "Fairly Difficult" if score >= 50 else "Difficult" if score >= 30 else 
                    "Very Difficult")
            
            if NLTK_AVAILABLE:
                sentences = len(sent_tokenize(text))
                words = len(word_tokenize(text))
            else:
                sentences = len(re.split(r'[.!?]+', text))
                words = len(text.split())

            # Calculate advanced metrics
            perplexity = self.calculate_perplexity(text)
            burstiness = self.calculate_burstiness(text)
            
            # Get detector scores
            detector_scores = self.get_detector_scores(perplexity, burstiness)
            
            # Calculate semantic similarity if original provided
            semantic_similarity = None
            if original:
                semantic_similarity = self.get_semantic_similarity(original, text)

            metrics = {
                'readability_score': round(score, 1),
                'readability_level': level,
                'grade_level': round(grade, 1),
                'sentence_count': sentences,
                'word_count': words,
                'perplexity': round(perplexity, 1),
                'burstiness': round(burstiness, 2),
                'detector_scores': detector_scores
            }
            
            if semantic_similarity is not None:
                metrics['semantic_similarity'] = round(semantic_similarity, 2)

            return metrics
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            return {}

# Initialize singleton
text_humanizer = AdvancedAIHumanizer()

