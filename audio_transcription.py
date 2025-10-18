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
        # Allow provider-specific model override; default to provider's audio model name
        self.model = os.getenv("OPENAI_TRANSCRIBE_MODEL", "openai-audio").strip() or "openai-audio"

        if self.auth_token:
            logger.info("STT initialized with authentication token")
        else:
            logger.warning("OPENAI_SPEECH_TOKEN not set - API may require authentication")

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "User-Agent": "TextSense-STT/1.0",
            "Referer": "https://pollinations.ai",
            "Accept": "application/json",
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
        question: str = "Transcribe this:",  # kept for API compatibility; unused in multipart
        language: Optional[str] = None,
        timeout_seconds: int = 120,
    ) -> dict:
        """
        Send audio to OpenAI-compatible transcriptions endpoint using multipart/form-data.
        """
        normalized_format = self._normalize_audio_format(audio_format)
        if normalized_format not in {"mp3", "wav"}:
            raise ValueError("Unsupported audio format. Only mp3 and wav are supported.")

        # Build multipart form: files + data
        filename = f"audio.{normalized_format}"
        mimetype = "audio/mpeg" if normalized_format == "mp3" else "audio/wav"

        data: dict[str, str] = {"model": self.model}
        if language:
            data["language"] = language

        headers = self._get_headers()  # no Content-Type; httpx sets multipart boundary

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            # Attempt 1: standard OpenAI-compatible field name
            response = await client.post(
                self.api_url,
                headers=headers,
                data=data,
                files={"file": (filename, audio_bytes, mimetype)},
            )

            ok_json: dict | None = None
            if response.status_code == 200:
                try:
                    first_json = response.json()
                    # Accept if it contains a direct 'text' field
                    if isinstance(first_json, dict) and (
                        isinstance(first_json.get("text"), str) and first_json.get("text")
                    ):
                        ok_json = first_json
                except Exception:
                    ok_json = None

            if ok_json is None:
                # Attempt 2: provider-specific field name 'audio'
                response = await client.post(
                    self.api_url,
                    headers=headers,
                    data=data,
                    files={"audio": (filename, audio_bytes, mimetype)},
                )
                if response.status_code == 200:
                    try:
                        second_json = response.json()
                        if isinstance(second_json, dict) and (
                            isinstance(second_json.get("text"), str) and second_json.get("text")
                        ):
                            ok_json = second_json
                        else:
                            # As a last resort, pass through whatever JSON we got
                            ok_json = second_json
                    except Exception:
                        ok_json = None

            if response.status_code != 200 and ok_json is None:
                try:
                    err_json = response.json()
                    err_msg = err_json.get("error") or err_json
                except Exception:
                    err_msg = response.text
                raise RuntimeError(f"Transcription API error ({response.status_code}): {err_msg}")

        return ok_json if ok_json is not None else response.json()


audio_transcriber = AudioTranscriber()


