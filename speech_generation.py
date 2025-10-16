"""
Speech Generation Module for TextSense
Handles AI-powered text-to-speech with emotion/style support
"""

from __future__ import annotations

import os
import random
import urllib.parse
from typing import Any, Tuple
from fastapi.responses import StreamingResponse
import httpx


class SpeechGenerator:
    """Handles AI text-to-speech generation with emotion/style customization."""

    def __init__(self):
        # Pollinations AI TTS endpoints (try audio domain first, then text fallback)
        self.tts_base_urls = [
            "https://audio.pollinations.ai",  # primary TTS endpoint
            "https://text.pollinations.ai",   # fallback with model param
        ]
        self.api_key = os.getenv("POLLINATIONS_API_KEY", "").strip()

    def _construct_emotion_prompt(self, text: str, emotion_style: str = "") -> str:
        """Construct the full prompt with emotion/style context."""
        if not emotion_style.strip():
            return text.strip()

        return f"Speak {emotion_style.strip()}: {text.strip()}"

    def _get_headers(self) -> dict[str, str]:
        """Get headers for TTS API requests."""
        headers = {
            'User-Agent': 'TextSense-TTS/1.0',
            'Referer': 'https://pollinations.ai'
        }

        # Add API key if available
        if self.api_key:
            headers['Authorization'] = f"Bearer {self.api_key}"

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
        # Construct the full prompt
        full_prompt = self._construct_emotion_prompt(text, emotion_style)

        # URL encode the prompt
        encoded_prompt = urllib.parse.quote(full_prompt)

        # Try multiple attempts with different seeds
        last_error = ""

        for attempt in range(max_retries):
            try:
                # Generate random seed for this attempt
                seed = random.randint(1, 1000000)

                # Try both endpoints per attempt
                for base_url in self.tts_base_urls:
                    if base_url.endswith("audio.pollinations.ai"):
                        api_url = f"{base_url}/{encoded_prompt}?voice={voice}&seed={seed}"
                    else:
                        api_url = f"{base_url}/{encoded_prompt}?model=openai-audio&voice={voice}&seed={seed}"

                    headers = self._get_headers()
                    headers.setdefault("Accept", "audio/mpeg, audio/*;q=0.8, */*;q=0.5")

                    # If this isn't the first attempt and we got a 402, try anonymous auth
                    if attempt > 0 and "tier" in last_error.lower():
                        headers['Authorization'] = f"Bearer anonymous-{seed}"

                    async with httpx.AsyncClient() as client:
                        async with client.stream("GET", api_url, headers=headers, timeout=120) as response:
                            if response.status_code == 200:
                                media_type = response.headers.get("content-type", "audio/mpeg").split(";")[0]
                                async def stream_content():
                                    async for chunk in response.aiter_bytes(chunk_size=8192):
                                        yield chunk
                                return StreamingResponse(
                                    stream_content(),
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
                            last_error = f"{error_message} (endpoint: {base_url})"

                            # If fallback available, try next base_url before deciding to retry attempt
                            continue

                # If we got here, both endpoints failed this attempt
                if attempt == max_retries - 1:
                    raise RuntimeError(last_error or "TTS service error")
                import asyncio
                await asyncio.sleep(1)

            except httpx.RequestError as e:
                last_error = f"Request failed: {str(e)}"
                if attempt == max_retries - 1:
                    raise RuntimeError(f"TTS request failed after {max_retries} attempts: {last_error}")

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


# Convenience instance for easy importing
speech_generator = SpeechGenerator()
