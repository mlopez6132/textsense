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

    def _build_system_prompt(self, audio_type: Optional[str]) -> str:
        prompts = {
            "general": (
                "You are a strict transcription tool. Your ONLY task is to transcribe audio content verbatim. "
                "RULES:\n"
                "1. TRANSCRIBE ALL SPOKEN WORDS/LYRICS EXACTLY AS HEARD\n"
                "2. Include filler words (um, ah, like, etc.)\n"
                "3. Note background noises in [brackets]\n"
                "4. For multiple speakers, indicate with [Speaker 1], [Speaker 2] etc.\n"
                "5. DO NOT describe the music, instruments, mood, or genre\n"
                "6. DO NOT analyze or interpret the content\n"
                "7. DO NOT summarize - include every word\n"
                "8. If you can't understand something, write [inaudible] or [unclear]\n"
                "9. For music, transcribe ALL lyrics line by line\n"
                "10. Be literal and objective - no commentary allowed"
            ),
            "music": (
                "TRANSCRIBE ALL LYRICS LINE BY LINE EXACTLY AS SUNG. Include repetitions, ad-libs, and background vocals. "
                "Do not describe the music - only transcribe the words being sung."
            ),
            "speech": (
                "TRANSCRIBE ALL SPOKEN WORDS VERBATIM. Include filler words, pauses, and repetitions. "
                "Indicate different speakers with [Speaker X]. Do not summarize or interpret."
            ),
            "interview": (
                "TRANSCRIBE THE ENTIRE CONVERSATION. Identify speakers as [Interviewer] and [Interviewee]. "
                "Include every question and response exactly as spoken."
            ),
            "lecture": (
                "TRANSCRIBE THE ENTIRE LECTURE WORD FOR WORD. Include technical terms, examples, and asides. "
                "Do not summarize or omit content."
            ),
        }
        key = (audio_type or "general").lower().strip()
        return prompts.get(key, prompts["general"])  # default to general

    async def transcribe(
        self,
        *,
        audio_bytes: bytes,
        audio_format: str,
        question: str = "Transcribe this:",
        audio_type: Optional[str] = "general",
        language: Optional[str] = None,
        timeout_seconds: int = 120,
    ) -> dict:
        """
        Send to either OpenAI-compatible chat or transcriptions endpoint based on URL.
        - If api_url contains '/audio/transcriptions', send multipart/form-data.
        - Otherwise, send Chat Completions JSON with system prompt derived from audio_type.
        """
        normalized_format = self._normalize_audio_format(audio_format)
        if normalized_format not in {"mp3", "wav"}:
            raise ValueError("Unsupported audio format. Only mp3 and wav are supported.")

        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            if "/audio/transcriptions" in (self.api_url or ""):
                filename = f"audio.{normalized_format}"
                mimetype = "audio/mpeg" if normalized_format == "mp3" else "audio/wav"
                data: dict[str, str] = {"model": os.getenv("OPENAI_CHAT_AUDIO_MODEL")}
                if language:
                    data["language"] = language
                response = await client.post(
                    self.api_url,
                    headers=headers,
                    data=data,
                    files={"file": (filename, audio_bytes, mimetype)},
                )
            else:
                b64 = base64.b64encode(audio_bytes).decode("utf-8")
                system_text = self._build_system_prompt(audio_type)
                payload: dict = {
                    "model": os.getenv("OPENAI_CHAT_AUDIO_MODEL"),
                    "private": True,
                    "messages": [
                        {
                            "role": "system",
                            "content": [
                                {"type": "text", "text": system_text}
                            ],
                        },
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": question},
                                {"type": "input_audio", "input_audio": {"data": b64, "format": normalized_format}},
                            ],
                        },
                    ],
                }
                if language:
                    payload["language"] = language
                json_headers = dict(headers)
                json_headers["Content-Type"] = "application/json"
                response = await client.post(self.api_url, headers=json_headers, json=payload)

        if response.status_code != 200:
            try:
                err_json = response.json()
                err_msg = err_json.get("error") or err_json
            except Exception:
                err_msg = response.text
            raise RuntimeError(f"Transcription API error ({response.status_code}): {err_msg}")

        return response.json()


audio_transcriber = AudioTranscriber()


