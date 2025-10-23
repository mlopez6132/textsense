"""
Speech Generation Module for TextSense
Handles AI-powered text-to-speech with optional vibe support
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
    """Handles AI text-to-speech generation with optional vibe customization."""

    def __init__(self):
        self.auth_token = os.getenv("OPENAI_SPEECH_TOKEN", "").strip()
        self.tts_url_template = os.getenv("OPENAI_SPEECH_API_KEY", "").strip()
        
        if not self.tts_url_template:
            logger.error("OPENAI_SPEECH_API_KEY not set - TTS URL template is required")
            raise RuntimeError("TTS URL template not configured")
        
        logger.info(f"TTS URL template configured: {self.tts_url_template[:50]}...")
        
        if self.auth_token:
            logger.info("TTS initialized with authentication token")
        else:
            logger.warning("OPENAI_SPEECH_TOKEN not set - API may require authentication")

    def _construct_prompt(self, text: str, vibe: str = "") -> str:
        """Construct the full prompt with vibe context."""
        sanitized_text = text.strip()
        
        if vibe.strip():
            return (
                f"Read the following text with this specific vibe and style: {vibe.strip()}\n\n"
                f"Text to read: \"\"\"{sanitized_text}\"\"\""
            )
        else:
            return (
                "Read exactly and only the following text, "
                "without adding, removing, reordering, translating, or paraphrasing any words. "
                "Preserve punctuation and numbers verbatim: \n\n\"\"\"" + sanitized_text + "\"\"\""
            )

    def _get_headers(self) -> dict[str, str]:
        """Get headers for TTS API requests."""
        headers = {
            'User-Agent': 'TextSense-TTS/1.0',
            'Referer': 'https://pollinations.ai',
            'Accept': 'audio/mpeg, audio/*;q=0.8, */*;q=0.5'
        }

        if self.auth_token:
            headers['Authorization'] = f"Bearer {self.auth_token}"

        return headers


    def _handle_api_error(self, response: httpx.Response) -> Tuple[bool, str]:
        """Handle API errors and determine if retry is possible."""
        if response.status_code == 400:
            return False, f"Bad Request (400): Invalid URL or parameters. Check URL template configuration."
        elif response.status_code == 402:
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
        vibe: str = "",
        max_retries: int = 3
    ) -> StreamingResponse:
        """
        Generate speech from text with optional vibe support.
        Automatically handles long-form content by chunking and concatenating.

        Args:
            text: The text to convert to speech
            voice: Voice to use (alloy, echo, fable, onyx, nova, shimmer, coral, verse, ballad, ash, sage, amuch, dan)
            vibe: Optional vibe description
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

        if len(text.strip()) > 999:
            raise ValueError("Text exceeds 999 character limit")

        return await self._generate_single_speech(text, voice, vibe, max_retries)

    async def _generate_single_speech(
        self,
        text: str,
        voice: str,
        vibe: str,
        max_retries: int
    ) -> StreamingResponse:
        """Generate speech"""
        full_prompt = self._construct_prompt(text, vibe)

        encoded_prompt = urllib.parse.quote(full_prompt)

        last_error = ""

        for attempt in range(max_retries):
            try:
                seed = random.randint(1, 1000000)

                # Construct the API URL properly
                if "{prompt}" in self.tts_url_template:
                    # If template has placeholders, use format method
                    api_url = self.tts_url_template.format(
                        prompt=encoded_prompt,
                        voice=voice,
                        seed=seed
                    )
                else:
                    # If it's a base URL, append query parameters
                    api_url = f"{self.tts_url_template}?prompt={encoded_prompt}&voice={voice}&seed={seed}"
                
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
                            
                            # Validate audio data
                            if len(audio_data) == 0:
                                last_error = "Received empty audio data"
                                continue
                            
                            logger.info(f"Received {len(audio_data)} bytes of audio data")
                            
                            # Return as streaming response
                            async def stream_audio():
                                yield audio_data
                            
                            return StreamingResponse(
                                stream_audio(),
                                media_type=media_type,
                                headers={
                                    "Content-Disposition": "attachment; filename=generated_speech.mp3",
                                    "Cache-Control": "no-cache",
                                    "X-Speech-Provider": "openai",
                                    "X-Speech-Voice": voice,
                                    "X-Speech-Vibe": vibe or "",
                                    "Content-Length": str(len(audio_data))
                                }
                            )

                        # Handle specific error codes
                        can_retry, error_message = self._handle_api_error(response)
                        last_error = error_message
                        logger.error(f"API error: {error_message}")

                # If we got here we failed this attempt; decide to retry
                if attempt == max_retries - 1:
                    logger.error(f"All retries exhausted. Last error: {last_error}")
                    raise RuntimeError(last_error or "TTS service error")
                
                logger.info(f"Retrying after 2 second delay...")
                import asyncio
                await asyncio.sleep(2)

            except httpx.RequestError as e:
                error_str = str(e)
                last_error = f"Request failed: {error_str}"
                logger.error(f"HTTP request error: {last_error}")
                logger.error(f"Failed URL was: {api_url}")
                
                # DNS error - check domain configuration
                if "Name or service not known" in error_str or "getaddrinfo failed" in error_str:
                    logger.critical(f"DNS resolution failure for speech API")
                    raise RuntimeError(f"DNS resolution failed. Cannot reach speech API. Check server DNS configuration.")
                    
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
        vibe: str
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
        elif len(text.strip()) > 999:
            errors.append("Text exceeds 999 character limit")
        elif len(text.strip()) < 1:
            errors.append("Text is too short")

        # Voice validation
        valid_voices = [v["id"] for v in self.get_available_voices()]
        if voice not in valid_voices:
            errors.append(f"Invalid voice. Must be one of: {', '.join(valid_voices)}")

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "text_length": len(text.strip()),
            "vibe_length": len(vibe.strip())
        }


speech_generator = SpeechGenerator()