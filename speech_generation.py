"""
Speech Generation Module for TextSense
Handles AI-powered text-to-speech with emotion/style support
"""

from __future__ import annotations

import os
import random
import urllib.parse
import re
from typing import Any, Tuple, List
from fastapi.responses import StreamingResponse
import requests

try:
    from pydub import AudioSegment
    from pydub.effects import normalize
    # Try to point pydub to a bundled ffmpeg binary (Render often lacks system ffmpeg)
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        ffmpeg_path = get_ffmpeg_exe()
        # pydub uses AudioSegment.converter as ffmpeg path
        AudioSegment.converter = ffmpeg_path
    except Exception as _ffmpeg_err:
        # Non-fatal: pydub may still work if system ffmpeg is available
        pass
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    print("Warning: pydub not available. Audio concatenation disabled.")


class SpeechGenerator:
    """Handles AI text-to-speech generation with emotion/style customization."""

    def __init__(self):
        # Pollinations AI TTS endpoint
        self.tts_base_url = "https://text.pollinations.ai"
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

    def _chunk_text(self, text: str, max_words: int = 300) -> List[str]:
        """Chunk text into smaller segments based on word count and sentence boundaries."""
        if not text or not text.strip():
            return []

        # Split by sentences first to maintain natural breaks
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())

        chunks = []
        current_chunk = ""
        current_word_count = 0

        for sentence in sentences:
            sentence_words = len(sentence.split())
            if sentence_words == 0:
                continue

            # If adding this sentence would exceed the limit and we already have content
            if current_word_count + sentence_words > max_words and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = sentence
                current_word_count = sentence_words
            else:
                current_chunk += " " + sentence if current_chunk else sentence
                current_word_count += sentence_words

        # Add the last chunk if it has content
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        # If we have only one chunk and it's still too long, split by words
        if len(chunks) == 1 and len(chunks[0].split()) > max_words:
            words = chunks[0].split()
            chunks = []
            for i in range(0, len(words), max_words):
                chunk_words = words[i:i + max_words]
                chunks.append(" ".join(chunk_words))

        return [chunk for chunk in chunks if chunk.strip()]

    def _generate_chunk_audio(
        self,
        text: str,
        voice: str,
        emotion_style: str,
        max_retries: int
    ) -> bytes:
        """Generate audio data for a text chunk (used for long-form concatenation)."""
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

                # Construct API URL
                api_url = f"{self.tts_base_url}/{encoded_prompt}?model=openai-audio&voice={voice}&seed={seed}"

                # Get headers
                headers = self._get_headers()

                # If this isn't the first attempt and we got a 402, try anonymous auth
                if attempt > 0 and "tier" in last_error.lower():
                    headers['Authorization'] = f"Bearer anonymous-{seed}"

                # Make the request
                response = requests.get(api_url, headers=headers, timeout=120)

                if response.status_code == 200:
                    # Return the raw audio data
                    return response.content

                # Handle specific error codes
                can_retry, error_message = self._handle_api_error(response)
                last_error = error_message

                if not can_retry or attempt == max_retries - 1:
                    raise RuntimeError(error_message)

                # Wait a bit before retrying
                import time
                time.sleep(1)

            except requests.RequestException as e:
                last_error = f"Request failed: {str(e)}"
                if attempt == max_retries - 1:
                    raise RuntimeError(f"TTS request failed after {max_retries} attempts: {last_error}")

        # This should never be reached, but just in case
        raise RuntimeError(f"TTS generation failed: {last_error}")

    def _concatenate_audio(self, audio_chunks: List[bytes]) -> bytes:
        """Concatenate multiple audio chunks into a single MP3 file."""
        if not PYDUB_AVAILABLE:
            raise RuntimeError("pydub is required for audio concatenation. Install with: pip install pydub")

        if len(audio_chunks) == 1:
            return audio_chunks[0]

        # Create AudioSegment objects from the audio data
        audio_segments = []
        for chunk_data in audio_chunks:
            try:
                from io import BytesIO
                # Interpret raw bytes as an MP3 stream
                segment = AudioSegment.from_file(BytesIO(chunk_data), format="mp3")
                # Add a small crossfade to smooth transitions
                if audio_segments:
                    segment = segment.fade_in(50)
                audio_segments.append(segment)
            except Exception as e:
                print(f"Warning: Failed to process audio chunk: {e}")
                continue

        if not audio_segments:
            raise RuntimeError("No valid audio segments to concatenate")

        # Concatenate all segments
        combined = audio_segments[0]
        for segment in audio_segments[1:]:
            combined += segment

        # Normalize the audio to consistent volume
        combined = normalize(combined)

        # Export as MP3 to in-memory buffer
        from io import BytesIO
        buffer = BytesIO()
        combined.export(buffer, format="mp3")
        buffer.seek(0)
        return buffer.read()

    def _handle_api_error(self, response: requests.Response) -> Tuple[bool, str]:
        """Handle API errors and determine if retry is possible."""
        if response.status_code == 402:
            return True, "TTS API requires authentication. Please visit https://auth.pollinations.ai to get a token or upgrade your tier."
        elif response.status_code == 429:
            return True, "Rate limit exceeded. Please try again later."
        elif response.status_code >= 500:
            return True, "TTS service temporarily unavailable. Please try again."
        else:
            return False, f"TTS API error: {response.text}"

    def generate_speech(
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

        if len(text.strip()) > 25000:  # Increased limit for long-form content
            raise ValueError("Text exceeds 25,000 character limit")

        if len(emotion_style.strip()) > 200:
            raise ValueError("Emotion style prompt exceeds 200 character limit")

        # Check if we need to chunk the text
        word_count = len(text.split())
        chunk_size = 250  # words per chunk for ~15-20 second segments

        if word_count <= chunk_size:
            # Short text - use single request
            return self._generate_single_speech(text, voice, emotion_style, max_retries)
        else:
            # Long text - chunk and concatenate
            return self._generate_long_speech(text, voice, emotion_style, chunk_size, max_retries)

    def _generate_single_speech(
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

                # Construct API URL
                api_url = f"{self.tts_base_url}/{encoded_prompt}?model=openai-audio&voice={voice}&seed={seed}"

                # Get headers
                headers = self._get_headers()

                # If this isn't the first attempt and we got a 402, try anonymous auth
                if attempt > 0 and "tier" in last_error.lower():
                    headers['Authorization'] = f"Bearer anonymous-{seed}"

                # Make the request
                response = requests.get(api_url, headers=headers, timeout=120, stream=True)

                if response.status_code == 200:
                    # Success! Return the streaming response
                    return StreamingResponse(
                        response.iter_content(chunk_size=8192),
                        media_type="audio/mpeg",
                        headers={
                            "Content-Disposition": "attachment; filename=generated_speech.mp3",
                            "Cache-Control": "no-cache",
                            "X-Speech-Provider": "openai",
                            "X-Speech-Voice": voice,
                            "X-Speech-Emotion": emotion_style or "neutral",
                            "X-Speech-Type": "single"
                        }
                    )

                # Handle specific error codes
                can_retry, error_message = self._handle_api_error(response)
                last_error = error_message

                if not can_retry or attempt == max_retries - 1:
                    raise RuntimeError(error_message)

                # Wait a bit before retrying
                import time
                time.sleep(1)

            except requests.RequestException as e:
                last_error = f"Request failed: {str(e)}"
                if attempt == max_retries - 1:
                    raise RuntimeError(f"TTS request failed after {max_retries} attempts: {last_error}")

        # This should never be reached, but just in case
        raise RuntimeError(f"TTS generation failed: {last_error}")

    def _generate_long_speech(
        self,
        text: str,
        voice: str,
        emotion_style: str,
        chunk_size: int,
        max_retries: int
    ) -> StreamingResponse:
        """Generate speech for long text by chunking and concatenating."""
        if not PYDUB_AVAILABLE:
            raise RuntimeError("Long-form speech requires pydub. Install with: pip install pydub")

        # Chunk the text
        text_chunks = self._chunk_text(text, chunk_size)
        print(f"Processing {len(text_chunks)} chunks for long-form speech")

        audio_chunks = []

        for i, chunk in enumerate(text_chunks):
            print(f"Processing chunk {i + 1}/{len(text_chunks)} ({len(chunk.split())} words)")

            # Generate speech for this chunk using direct API call
            chunk_audio_data = self._generate_chunk_audio(chunk, voice, emotion_style, max_retries)
            audio_chunks.append(chunk_audio_data)

        # Concatenate all audio chunks
        print("Concatenating audio chunks...")
        final_audio = self._concatenate_audio(audio_chunks)

        # Return the concatenated audio
        from io import BytesIO
        return StreamingResponse(
            BytesIO(final_audio),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "attachment; filename=generated_long_speech.mp3",
                "Cache-Control": "no-cache",
                "X-Speech-Provider": "openai",
                "X-Speech-Voice": voice,
                "X-Speech-Emotion": emotion_style or "neutral",
                "X-Speech-Type": "long-form",
                "X-Speech-Chunks": str(len(text_chunks))
            }
        )

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
