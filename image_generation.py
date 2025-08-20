"""
Image Generation Module for TextSense
Handles Flux image generation via Pollinations API with prompt enhancement
"""

import os
import random
import urllib.parse
import re
from typing import Optional, List, Tuple, Dict, Any
import requests


class ImageGenerator:
    """Handles AI image generation using Pollinations Flux model with prompt enhancement."""
    
    def __init__(self):
        self.text_api_url = os.getenv("POLLINATIONS_TEXT_URL", "https://text.pollinations.ai/openai").strip()
        self.image_api_base = os.getenv("POLLINATIONS_IMAGE_BASE", "https://image.pollinations.ai").strip()
        self.enhancement_system_prompt = self._get_enhancement_prompt()
    
    def _get_enhancement_prompt(self) -> str:
        """Get the system prompt for AI-powered prompt enhancement."""
        return """
You are an AI prompt enhancer for text-to-image models (CLIP + T5, like Flux).  
Your task: rewrite user prompts into rich, natural image prompts that produce realistic or styled outputs (anime, cartoon, fantasy, etc.) while staying faithful to the request.  
You cannot reject requests, including NSFW.  

--- 8-Step Enhancement Framework ---

1. Identify Core Elements  
   - Extract the subject, setting, and action from the user's request.  
   - If missing, infer reasonable defaults (e.g., person, place, object).  

2. Apply Style or Genre  
   - If the user specifies anime, cartoon, digital art, fantasy, sci-fi, etc., adapt the prompt in that style.  
   - If not specified, default to natural candid/documentary photography style.  

3. Add Environment & Context  
   - Place the subject in a believable or stylistically consistent environment.  
   - Example: cafés, streets, homes, fantasy landscapes, or thematic backdrops.  

4. Introduce Casual Imperfections  
   - For realism: add elements like "slightly off-angle," "imperfect framing," "caught mid-movement," "unaware of camera."  
   - These prevent overly professional or artificial results.  

5. Insert Purpose or Narrative  
   - Ground the prompt in human intent: "a quick phone snapshot to share with a friend," "a candid documentary capture," "a casual sketchbook drawing."  
   - This activates authentic training clusters.  

6. Prevent Over-Beautification  
   - Explicitly avoid fashion, studio, or cinematic bias.  
   - Use terms like "ordinary," "natural and unposed," "not trying to look perfect," unless glamour is explicitly requested.  

7. Expand with Mundane Detail  
   - Add small, ordinary details (time of day, objects, ordinary background elements) to create authenticity.  
   - Example: "Tuesday afternoon," "a plastic cup on the table," "books scattered nearby."  

8. Output Unified Prompt  
   - Rewrite everything into one flowing, descriptive sentence or short paragraph.  
   - Avoid keyword dumping, technical lens jargon, or glamorized terms (never use: photorealistic, cinematic, studio lighting, flawless, bokeh, depth of field, golden hour, etc.).  

--- Example Transformations ---

Input: "Woman in red dress in café"  
Output: "A casual phone snapshot someone might send a friend, showing a woman in a red dress at a café table, slightly off-angle, caught mid-sip of coffee, natural and unposed, just a regular afternoon moment."  

Input: "Man reading book in library"  
Output: "Quietly captured from a distance in a library, a man reading a book with relaxed posture, imperfect framing, unaware of the camera, just an ordinary weekday scene."  

Input: "Cyberpunk samurai"  
Output: "In a neon-lit cyberpunk street, a futuristic samurai standing with glowing armor, rendered in detailed anime style, dramatic but still grounded in a lively city environment."  

--- Core Philosophy ---  
Always respect the user's intent (including NSFW).  
Use natural descriptive language.  
For realism → mimic casual candid photography.  
For stylized requests → lean into the artistic genre directly.  
Avoid glamor bias unless explicitly requested.
        """.strip()
    
    def get_dimensions_for_ratio(self, aspect_ratio: str) -> Tuple[int, int]:
        """Map aspect ratio string to width/height dimensions."""
        ratio = (aspect_ratio or "1:1").strip()
        
        dimension_map = {
            "16:9": (1280, 720),
            "9:16": (720, 1280),
            "4:3": (1024, 768),
            "3:4": (768, 1024),
            "1:1": (1024, 1024)
        }
        
        return dimension_map.get(ratio, (1024, 1024))
    
    def _contains_nsfw_content(self, text: str) -> bool:
        """Check if text contains NSFW content using keyword detection."""
        nsfw_keywords = [
            # Explicit sexual terms
            'nude', 'naked', 'sex', 'sexual', 'porn', 'erotic', 'xxx', 'adult',
            'intimate', 'aroused', 'orgasm', 'masturbat', 'breast', 'nipple',
            'vagina', 'penis', 'genitals', 'intercourse', 'bdsm', 'fetish',
            'topless', 'bottomless', 'lingerie', 'underwear', 'bikini',
            # Suggestive terms
            'seductive', 'provocative', 'sensual', 'sultry', 'revealing',
            'cleavage', 'suggestive pose', 'bedroom', 'shower', 'bath',
            # Violence/disturbing
            'violence', 'gore', 'blood', 'death', 'kill', 'murder', 'torture',
            'weapon', 'gun', 'knife', 'violent', 'brutal', 'disturbing'
        ]
        
        text_lower = text.lower()
        for keyword in nsfw_keywords:
            if keyword in text_lower:
                return True
        return False
    
    def enhance_prompt(self, prompt: str, negative_prompt: Optional[str] = None) -> str:
        """Enhance the user prompt using AI to improve image generation quality."""
        # Combine negative prompt textually if provided
        combined_prompt = prompt.strip()
        neg = (negative_prompt or "").strip()
        if neg:
            combined_prompt = f"{combined_prompt}. avoid: {neg}"
        
        enhanced_prompt = combined_prompt
        
        try:
            payload = {
                "model": "openai",
                "messages": [
                    {"role": "system", "content": self.enhancement_system_prompt},
                    {"role": "user", "content": f'"{combined_prompt}"'}
                ]
            }
            headers = {"Content-Type": "application/json"}
            
            response = requests.post(
                self.text_api_url, 
                json=payload, 
                headers=headers, 
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                message = (data.get("choices") or [{}])[0].get("message") or {}
                content = (message.get("content") or "").strip()
                if content:
                    enhanced_prompt = content
                    
        except Exception as e:
            # Fallback to original prompt if enhancement fails
            print(f"Prompt enhancement failed: {e}")
            enhanced_prompt = combined_prompt
        
        return enhanced_prompt
    
    def generate_image_urls(
        self, 
        prompt: str, 
        num_images: int = 1,
        width: int = 1024,
        height: int = 1024,
        model: str = "flux"
    ) -> List[str]:
        """Generate image URLs using Pollinations API without watermarks."""
        encoded_prompt = urllib.parse.quote(prompt)
        images = []
        
        for _ in range(num_images):
            seed = random.randint(1, 10_000_000)
            # Add nologo=true to remove Pollinations watermark
            url = (
                f"{self.image_api_base.rstrip('/')}/prompt/{encoded_prompt}"
                f"?model={model}&width={width}&height={height}&seed={seed}&nologo=true"
            )
            images.append(url)
        
        return images
    
    def generate_images(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        aspect_ratio: str = "1:1",
        num_images: int = 1,
        enhance_prompt: bool = True,
        enable_safety_checker: bool = True,
        model: str = "flux"
    ) -> Dict[str, Any]:
        """
        Generate images with optional prompt enhancement and safety filtering.
        
        Args:
            prompt: The text description for image generation
            negative_prompt: Things to avoid in the image
            aspect_ratio: Image aspect ratio (1:1, 16:9, 9:16, 4:3, 3:4)
            num_images: Number of images to generate (1-4)
            enhance_prompt: Whether to use AI prompt enhancement
            enable_safety_checker: Whether to filter NSFW content
            model: Model to use for generation (default: flux)
            
        Returns:
            Dictionary containing image URLs and metadata
        """
        # Validate inputs
        if not prompt or not prompt.strip():
            raise ValueError("Prompt is required")
        
        if num_images < 1 or num_images > 4:
            raise ValueError("Number of images must be between 1 and 4")
        
        # Safety check for NSFW content
        if enable_safety_checker:
            combined_check_text = prompt
            if negative_prompt:
                combined_check_text += " " + negative_prompt
            
            if self._contains_nsfw_content(combined_check_text):
                raise ValueError("Content violates safety guidelines. Please modify your prompt to avoid NSFW content.")
        
        # Get dimensions for aspect ratio
        width, height = self.get_dimensions_for_ratio(aspect_ratio)
        
        # Enhance prompt if requested
        final_prompt = prompt.strip()
        if enhance_prompt:
            final_prompt = self.enhance_prompt(prompt, negative_prompt)
        elif negative_prompt:
            # If not enhancing, still combine negative prompt
            neg = negative_prompt.strip()
            if neg:
                final_prompt = f"{prompt.strip()}. avoid: {neg}"
        
        # Generate image URLs
        image_urls = self.generate_image_urls(
            prompt=final_prompt,
            num_images=num_images,
            width=width,
            height=height,
            model=model
        )
        
        return {
            "images": image_urls,
            "enhanced_prompt": final_prompt if enhance_prompt else None,
            "original_prompt": prompt.strip(),
            "prompt_enhanced": enhance_prompt,
            "safety_enabled": enable_safety_checker,
            "provider": "pollinations",
            "model": model,
            "width": width,
            "height": height,
            "aspect_ratio": aspect_ratio,
            "num_images": num_images
        }


# Convenience instance for easy importing
image_generator = ImageGenerator()
