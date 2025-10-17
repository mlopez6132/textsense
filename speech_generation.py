"""
Speech Generation Module for TextSense
Handles AI-powered text-to-speech with emotion/style support
"""

from __future__ import annotations

import os
import random
import urllib.parse
import logging
from typing import Any, Tuple
from fastapi.responses import StreamingResponse
import httpx

# Set up logging
logger = logging.getLogger(__name__)


class SpeechGenerator:
    """Handles AI text-to-speech generation with emotion/style customization."""

    def __init__(self):
        # Use the reliable Pollinations audio endpoint directly
        self.tts_url_template = "https://audio.pollinations.ai/{prompt}?voice={voice}&seed={seed}"
        self.fallback_url_template = "https://text.pollinations.ai/{prompt}?model=openai-audio&voice={voice}&seed={seed}"
        logger.info("TTS initialized with audio.pollinations.ai endpoint")

    def _construct_emotion_prompt(self, text: str, emotion_style: str = "") -> str:
        """Construct the full prompt with emotion/style context."""
        if not emotion_style.strip():
            return text.strip()

        return f"Speak {emotion_style.strip()}: {text.strip()}"

    def _get_headers(self) -> dict[str, str]:
        """Get headers for TTS API requests."""
        headers = {
            'User-Agent': 'TextSense-TTS/1.0',
            'Referer': 'https://pollinations.ai',
            'Accept': 'audio/mpeg, audio/*;q=0.8, */*;q=0.5'
        }

        return headers


    def _handle_api_error(self, response: httpx.Response) -> Tuple[bool, str]:
        """Handle API errors and determine if retry is possible."""
        if response.status_code == 402:
            return True, "TTS API requires authentication. Please visit https://auth.pollinations.ai to get a token or upgrade your tier."
        elif response.status_code == 429:
            return True, "Rate limit exceeded. Please try again later."
        elif response.status_code >= 500:
            return True, "TTS service temporarily unavailable. Please try again."
        else:
            return False, f"TTS API error: {response.text}"

    async def generate_speech(
        self,
        text: str,
        voice: str = "alloy",
        emotion_style: str = "",
        max_retries: int = 3
    ) -> StreamingResponse:
        """
        Generate speech from text with emotion/style support.
        Automatically handles long-form content by chunking and concatenating.

        Args:
            text: The text to convert to speech
            voice: Voice to use (alloy, echo, fable, onyx, nova, shimmer, coral, verse, ballad, ash, sage, amuch, dan)
            emotion_style: Custom emotion/style description
            max_retries: Maximum number of retry attempts

        Returns:
            StreamingResponse containing audio data

        Raises:
            ValueError: If input validation fails
            RuntimeError: If all retry attempts fail
        """
        # Validate inputs
        if not text or not text.strip():
            raise ValueError("Text is required")

        if len(text.strip()) > 5000:
            raise ValueError("Text exceeds 5,000 character limit")

        if len(emotion_style.strip()) > 200:
            raise ValueError("Emotion style prompt exceeds 200 character limit")

        # Generate speech using single request
        return await self._generate_single_speech(text, voice, emotion_style, max_retries)

    async def _generate_single_speech(
        self,
        text: str,
        voice: str,
        emotion_style: str,
        max_retries: int
    ) -> StreamingResponse:
        """Generate speech for short text (single request)."""
        full_prompt = self._construct_emotion_prompt(text, emotion_style)

        # URL encode the prompt
        encoded_prompt = urllib.parse.quote(full_prompt)
        encoded_emotion = urllib.parse.quote(emotion_style or "neutral")

        last_error = ""
        use_fallback = False

        for attempt in range(max_retries):
            try:
                seed = random.randint(1, 1000000)

                # Try fallback URL if primary failed with 502/5xx
                if use_fallback:
                    api_url = self.fallback_url_template.format(
                        prompt=encoded_prompt,
                        voice=voice,
                        seed=seed
                    )
                    logger.info(f"Attempt {attempt + 1}: Using fallback URL")
                else:
                    try:
                        api_url = self.tts_url_template.format(
                            prompt=encoded_prompt,
                            emotion=encoded_emotion,
                            voice=voice,
                            seed=seed
                        )
                    except KeyError:
                        # If emotion is not in template, try without it
                        api_url = self.tts_url_template.format(
                            prompt=encoded_prompt,
                            voice=voice,
                            seed=seed
                        )
                    logger.info(f"Attempt {attempt + 1}: Requesting TTS from {api_url[:80]}...")

                headers = self._get_headers()

                async with httpx.AsyncClient(timeout=120.0) as client:
                    async with client.stream("GET", api_url, headers=headers) as response:
                        logger.info(f"Response status: {response.status_code}")
                        if response.status_code == 200:
                            content_type_header = response.headers.get("content-type", "audio/mpeg").lower()
                            if "audio" not in content_type_header:
                                last_error = f"Unexpected content type: {content_type_header}"
                                continue
                            
                            media_type = content_type_header.split(";")[0]
                            
                            # Collect the audio data first to avoid streaming issues
                            audio_data = b""
                            async for chunk in response.aiter_bytes(chunk_size=8192):
                                audio_data += chunk
                            
                            # Return as streaming response
                            async def stream_audio():
                                yield audio_data
                            
                            return StreamingResponse(
                                stream_audio(),
                                media_type=media_type,
                                headers={
                                    "Content-Disposition": "attachment; filename=generated_speech.mp3",
                                    "Cache-Control": "no-cache",
                                    "X-Speech-Provider": "pollinations",
                                    "X-Speech-Voice": voice,
                                    "X-Speech-Emotion": emotion_style or "neutral"
                                }
                            )

                        # Handle specific error codes
                        can_retry, error_message = self._handle_api_error(response)
                        last_error = error_message
                        logger.error(f"API error: {error_message}")
                        
                        # Enable fallback on 502/5xx errors
                        if response.status_code >= 502 and not use_fallback:
                            logger.warning(f"Got {response.status_code}, switching to fallback endpoint")
                            use_fallback = True
                            continue

                # If we got here we failed this attempt; decide to retry
                if attempt == max_retries - 1:
                    logger.error(f"All retries exhausted. Last error: {last_error}")
                    raise RuntimeError(last_error or "TTS service error")
                
                logger.info(f"Retrying after 2 second delay...")
                import asyncio
                await asyncio.sleep(2)  # Increased delay between retries

            except httpx.RequestError as e:
                error_str = str(e)
                last_error = f"Request failed: {error_str}"
                logger.error(f"HTTP request error: {last_error}")
                logger.error(f"Failed URL was: {api_url}")
                
                # DNS error - critical infrastructure issue
                if "Name or service not known" in error_str or "getaddrinfo failed" in error_str:
                    logger.critical("DNS resolution failure! Server cannot resolve domain names. This is a server infrastructure issue.")
                    raise RuntimeError(f"DNS resolution failed - server networking issue. Cannot reach {api_url.split('/')[2]}. Check server DNS configuration.")
                
                # Try fallback on other connection errors
                if not use_fallback:
                    logger.warning("Connection error, switching to fallback endpoint")
                    use_fallback = True
                    continue
                    
                if attempt == max_retries - 1:
                    logger.error(f"All retries exhausted after connection errors")
                    raise RuntimeError(f"TTS request failed after {max_retries} attempts: {last_error}")
                
                import asyncio
                await asyncio.sleep(2)

        # This should never be reached, but just in case
        raise RuntimeError(f"TTS generation failed: {last_error}")

    def get_available_voices(self) -> list[dict[str, str]]:
        """Get list of available voices with descriptions."""
        return [
            {"id": "alloy", "name": "Alloy", "description": "Balanced, neutral voice"},
            {"id": "echo", "name": "Echo", "description": "Male voice with warm tone"},
            {"id": "fable", "name": "Fable", "description": "British accent, clear articulation"},
            {"id": "onyx", "name": "Onyx", "description": "Deep male voice, authoritative"},
            {"id": "nova", "name": "Nova", "description": "Youthful, energetic voice"},
            {"id": "shimmer", "name": "Shimmer", "description": "Warm female voice, expressive"},
            {"id": "coral", "name": "Coral", "description": "Soft, melodic female voice"},
            {"id": "verse", "name": "Verse", "description": "Poetic and expressive voice"},
            {"id": "ballad", "name": "Ballad", "description": "Storytelling, narrative voice"},
            {"id": "ash", "name": "Ash", "description": "Calm, soothing male voice"},
            {"id": "sage", "name": "Sage", "description": "Wise, experienced voice"},
            {"id": "amuch", "name": "Amuch", "description": "Unique, distinctive character voice"},
            {"id": "dan", "name": "Dan", "description": "Friendly, approachable male voice"}
        ]

    def validate_inputs(
        self,
        text: str,
        voice: str,
        emotion_style: str
    ) -> dict[str, Any]:
        """
        Validate inputs and return validation results.

        Returns:
            Dictionary with validation status and any error messages
        """
        errors = []
        warnings = []

        # Text validation
        if not text or not text.strip():
            errors.append("Text is required")
        elif len(text.strip()) > 5000:
            errors.append("Text exceeds 5000 character limit")
        elif len(text.strip()) < 1:
            errors.append("Text is too short")

        # Voice validation
        valid_voices = [v["id"] for v in self.get_available_voices()]
        if voice not in valid_voices:
            errors.append(f"Invalid voice. Must be one of: {', '.join(valid_voices)}")

        # Emotion style validation
        if len(emotion_style.strip()) > 200:
            errors.append("Emotion style prompt exceeds 200 character limit")
        elif len(emotion_style.strip()) > 150:
            warnings.append("Emotion style prompt is long, consider shortening for better results")

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "text_length": len(text.strip()),
            "emotion_style_length": len(emotion_style.strip())
        }


speech_generator = SpeechGenerator()