"""
Audio Transcription Module for TextSense
Uses OpenAI-compatible API for speech-to-text via base64 audio.
"""

from __future__ import annotations

import os
import base64
import logging
from typing import Optional, Tuple

import httpx

logger = logging.getLogger(__name__)


class AudioTranscriber:
    """Handles audio transcription against OpenAI-compatible endpoint."""

    def __init__(self) -> None:
        self.auth_token = os.getenv("OPENAI_SPEECH_TOKEN", "").strip()
        self.api_url = os.getenv("SPEECH_OPENAI_URL", "").strip()

        if self.auth_token:
            logger.info("STT initialized with authentication token")
        else:
            logger.warning("OPENAI_SPEECH_TOKEN not set - API may require authentication")

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "User-Agent": "TextSense-STT/1.0",
            "Referer": "https://pollinations.ai",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    @staticmethod
    def _normalize_audio_format(audio_format: Optional[str]) -> str:
        if not audio_format:
            return ""
        fmt = audio_format.lower().strip().lstrip(".")
        if fmt in {"mp3", "mpeg"}:
            return "mp3"
        if fmt in {"wav", "wave"}:
            return "wav"
        return fmt

    async def transcribe(
        self,
        *,
        audio_bytes: bytes,
        audio_format: str,
        question: str = "Transcribe this:",
        language: Optional[str] = None,
        return_timestamps: bool = False,
        timeout_seconds: int = 120,
    ) -> dict:
        """
        Send base64-encoded audio to OpenAI endpoint and return JSON.
        """
        normalized_format = self._normalize_audio_format(audio_format)
        if normalized_format not in {"mp3", "wav"}:
            raise ValueError("Unsupported audio format. Only mp3 and wav are supported.")

        b64 = base64.b64encode(audio_bytes).decode("utf-8")

        # Build content array with optional timestamp request
        content = [
            {"type": "text", "text": question},
            {
                "type": "input_audio",
                "input_audio": {"data": b64, "format": normalized_format},
            },
        ]
        
        # Add timestamp request if needed
        if return_timestamps:
            content.append({
                "type": "text", 
                "text": "Please include timestamps for each segment of speech."
            })

        payload: dict = {
            "model": "openai-audio",
            "messages": [
                {
                    "role": "user",
                    "content": content,
                }
            ],
        }
        if language:
            payload["language"] = language 

        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(self.api_url, headers=headers, json=payload)

        if response.status_code != 200:
            try:
                err_json = response.json()
                err_msg = err_json.get("error") or err_json
            except Exception:
                err_msg = response.text
            raise RuntimeError(f"Transcription API error ({response.status_code}): {err_msg}")

        return response.json()


audio_transcriber = AudioTranscriber()


