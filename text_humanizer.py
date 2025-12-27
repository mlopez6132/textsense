import os
import re
import random
import math
import logging
import urllib.parse
from collections import defaultdict, Counter
from typing import List, Dict, Tuple, Optional

import httpx
from textstat import flesch_reading_ease, flesch_kincaid_grade

# Configure logging
logger = logging.getLogger(__name__)

# NLTK imports with error handling
try:
    import nltk
    from nltk.tokenize import sent_tokenize, word_tokenize
    from nltk.corpus import wordnet, stopwords
    
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
        """Main humanization method"""
        if not text or not text.strip():
            raise ValueError("Please provide text to humanize.")
        
        try:
            intensity_mapping = {"light": 1, "standard": 2, "heavy": 3}
            intensity_level = intensity_mapping.get(intensity, 2)
            
            current_text = text
            
            # Step 1: Local processing (Pattern replacement)
            current_text = self.replace_ai_patterns(current_text, intensity_level)
            
            # Step 2: Pollinations AI (if enabled and available)
            if use_pollinations:
                # Only send to Pollinations if text isn't too huge, or split it?
                # For now, send as is (limit might be an issue for very long texts)
                if len(current_text) < 4000: # Reasonable limit for URL param
                    pollinated_text = await self.call_pollinations_api(
                        current_text,
                        model="openai",
                        temperature=0.7
                    )
                    if pollinated_text and len(pollinated_text) > len(text) * 0.5: # Sanity check
                        current_text = pollinated_text
            
            # Step 3: Post-processing (Formatting, contractions)
            current_text = self.apply_advanced_contractions(current_text, intensity_level)
            
            if NLTK_AVAILABLE:
                current_text = self.add_human_touches(current_text, intensity_level)
            
            # Calculate metrics
            metrics = self.get_analysis_metrics(current_text)
            
            return current_text, metrics
            
        except Exception as e:
            logger.error(f"Humanization error: {e}")
            return text, {}

    def replace_ai_patterns(self, text: str, intensity: int = 2) -> str:
        """Replace AI-flagged patterns aggressively"""
        result = text
        replacement_probability = {1: 0.7, 2: 0.85, 3: 0.95}
        prob = replacement_probability.get(intensity, 0.85)
        
        for pattern, replacements in self.ai_indicators.items():
            matches = list(re.finditer(pattern, result, re.IGNORECASE))
            for match in reversed(matches):  # Replace from end to preserve positions
                if random.random() < prob:
                    replacement = random.choice(replacements)
                    result = result[:match.start()] + replacement + result[match.end():]
        
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
                current = sentence
                
                # Add natural starters occasionally
                if i > 0 and random.random() < prob and len(current.split()) > 6:
                    starter = random.choice(self.human_starters)
                    current = f"{starter} {current[0].lower() + current[1:]}"
                
                humanized.append(current)
            
            return " ".join(humanized)
        except Exception:
            return text

    def get_analysis_metrics(self, text: str) -> Dict:
        """Get detailed analysis of humanized text"""
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

            return {
                'readability_score': round(score, 1),
                'readability_level': level,
                'grade_level': round(grade, 1),
                'sentence_count': sentences,
                'word_count': words
            }
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            return {}

# Initialize singleton
text_humanizer = AdvancedAIHumanizer()

