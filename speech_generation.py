"""
Speech Generation Module for TextSense
Handles AI-powered text-to-speech with optional vibe support
"""

from __future__ import annotations

import os
import random
import urllib.parse
import logging
import base64
from typing import Any, Tuple
from fastapi.responses import StreamingResponse
import httpx

logger = logging.getLogger(__name__)

class SpeechGenerator:
    """Handles AI text-to-speech generation with optional vibe customization."""

    def __init__(self):
        self.api_base_url = "https://gen.pollinations.ai"
        self.auth_token = os.getenv("POLLINATIONS_API_KEY", "sk_pWuBiNAFXyKDcPrZOuoT6io25ySyj1VD").strip()

        if self.auth_token:
            logger.info("TTS initialized with Pollinations API key")
        else:
            logger.warning("POLLINATIONS_API_KEY not set - API may require authentication")

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
        """Get headers for Pollinations API requests."""
        headers = {
            'User-Agent': 'TextSense-TTS/1.0',
            'Content-Type': 'application/json'
        }

        if self.auth_token:
            headers['Authorization'] = f"Bearer {self.auth_token}"

        return headers


    def _handle_api_error(self, response: httpx.Response) -> Tuple[bool, str]:
        """Handle Pollinations API errors and determine if retry is possible."""
        if response.status_code == 401:
            return False, "Authentication required. Please set POLLINATIONS_API_KEY environment variable."
        elif response.status_code == 402:
            return True, "API quota exceeded. Please upgrade your Pollinations tier."
        elif response.status_code == 429:
            return True, "Rate limit exceeded. Please try again later."
        elif response.status_code >= 500:
            return True, "Pollinations service temporarily unavailable. Please try again."
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", response.text)
            except:
                error_msg = response.text
            return False, f"Pollinations API error: {error_msg}"

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
        """Generate speech using Pollinations /v1/chat/completions API with openai-audio model"""
        # Construct system instruction for emotion/vibe control
        if vibe.strip():
            system_instruction = (
                f"Only repeat what I say. "
                f"Now say with proper emphasis in a \"{vibe.strip()}\" emotion this statement."
            )
        else:
            system_instruction = "Only repeat what I say exactly as written, with natural speech patterns."

        last_error = ""

        for attempt in range(max_retries):
            try:
                api_url = f"{self.api_base_url}/v1/chat/completions"
                logger.info(f"Attempt {attempt + 1}: Requesting TTS from {api_url}")

                payload = {
                    "model": "openai-audio",
                    "modalities": ["text", "audio"], 
                    "audio": {
                        "voice": voice,
                        "format": "mp3"
                    },
                    "messages": [
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": text.strip()}
                    ],
                    "seed": random.randint(1, 1000000) if attempt == 0 else random.randint(1, 1000000)
                }

                headers = self._get_headers()

                async with httpx.AsyncClient(timeout=120.0) as client:
                    response = await client.post(api_url, json=payload, headers=headers)
                    logger.info(f"Response status: {response.status_code}")

                    if response.status_code == 200:
                        response_data = response.json()
                        try:
                            # Extract base64 audio data from response
                            audio_b64 = response_data['choices'][0]['message']['audio']['data']
                            audio_bytes = base64.b64decode(audio_b64)

                            if len(audio_bytes) == 0:
                                last_error = "Empty audio data in response"
                                continue

                            # Return as streaming response
                            async def stream_audio():
                                yield audio_bytes

                            return StreamingResponse(
                                stream_audio(),
                                media_type="audio/mpeg",
                                headers={
                                    "Content-Disposition": "attachment; filename=generated_speech.mp3",
                                    "Cache-Control": "no-cache",
                                    "X-Speech-Provider": "pollinations",
                                    "X-Speech-Voice": voice,
                                    "X-Speech-Vibe": vibe or ""
                                }
                            )
                        except KeyError as e:
                            last_error = f"Missing expected field in response: {e}. Response: {response_data}"
                            logger.warning(f"Response structure: {response_data}")
                            continue

                    can_retry, error_message = self._handle_api_error(response)
                    last_error = error_message or f"API error: {response.text}"
                    logger.error(f"API error: {last_error}")

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