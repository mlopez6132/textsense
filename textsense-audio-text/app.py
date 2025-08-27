from __future__ import annotations

import os
import tempfile
import subprocess
import wave
from typing import Any

import requests
import numpy as np
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from huggingface_hub import hf_hub_download
import sherpa_onnx  # type: ignore

# Model and runtime configuration (sherpa-onnx Whisper distil-small.en INT8)
WHISPER_VARIANT = os.getenv("WHISPER_VARIANT", "tiny.en")

# Safe conversion with fallback values
def safe_float_env(var_name: str, default: str) -> float:
    try:
        value = os.getenv(var_name, default)
        return float(value)
    except (ValueError, TypeError):
        print(f"Warning: Invalid value for {var_name}, using default: {default}")
        return float(default)

MAX_CHUNK_SECONDS = safe_float_env("MAX_CHUNK_SECONDS", "29.0")
CHUNK_OVERLAP_SECONDS = safe_float_env("CHUNK_OVERLAP_SECONDS", "1.0")

HF_CACHE_DIR = "/tmp/hf"
os.makedirs(HF_CACHE_DIR, exist_ok=True)
os.environ.setdefault("HF_HOME", HF_CACHE_DIR)
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", HF_CACHE_DIR)

def _ffmpeg_convert_to_wav_16k_mono(src_path: str) -> str:
    dst_fd, dst_path = tempfile.mkstemp(suffix=".wav")
    os.close(dst_fd)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        src_path,
        "-ac",
        "1",
        "-ar",
        "16000",
        "-acodec",
        "pcm_s16le",
        dst_path,
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        try:
            if os.path.exists(dst_path):
                os.unlink(dst_path)
        except Exception:
            pass
        raise RuntimeError(f"ffmpeg conversion failed: {e.stderr.decode(errors='ignore')}")
    return dst_path


def _get_nn_model_filename(repo_id: str, filename: str, subfolder: str = ".") -> str:
    return hf_hub_download(repo_id=repo_id, filename=filename, subfolder=subfolder)


def _get_token_filename(repo_id: str, filename: str, subfolder: str = ".") -> str:
    return hf_hub_download(repo_id=repo_id, filename=filename, subfolder=subfolder)

def format_timestamp_srt(seconds: float) -> str:
    """Format timestamp in SRT format (HH:MM:SS,mmm)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace('.', ',')


def load_recognizer(name: str) -> sherpa_onnx.OfflineRecognizer:
    supported = {
        "tiny.en",
        "base.en",
        "small.en",
        "medium.en",
        "tiny",
        "base",
        "small",
        "medium",
        "medium-aishell",
        "distil-small.en",
        "distil-medium.en",
    }
    if name not in supported:
        raise ValueError(f"Unsupported Whisper variant: {name}")
    full_repo_id = f"csukuangfj/sherpa-onnx-whisper-{name}"
    encoder = _get_nn_model_filename(repo_id=full_repo_id, filename=f"{name}-encoder.int8.onnx")
    decoder = _get_nn_model_filename(repo_id=full_repo_id, filename=f"{name}-decoder.int8.onnx")
    tokens = _get_token_filename(repo_id=full_repo_id, filename=f"{name}-tokens.txt")
    recognizer = sherpa_onnx.OfflineRecognizer.from_whisper(
        encoder=encoder,
        decoder=decoder,
        tokens=tokens,
        num_threads=int(os.getenv("SHERPA_NUM_THREADS", "2")),
    )
    return recognizer


def _decode_chunk_to_text(chunk_samples: np.ndarray, sample_rate: int) -> str:
    s = recognizer.create_stream()
    s.accept_waveform(sample_rate, chunk_samples)
    recognizer.decode_stream(s)
    return s.result.text.strip()


def _maybe_trim_overlap(prev_text: str, current_text: str, chunk_start_s: float, chunk_end_s: float) -> tuple[str, float]:
    if not prev_text or len(prev_text) <= 50:
        return current_text, chunk_start_s
    prev_words = prev_text.split()[-10:]
    curr_words = current_text.split()[:10]
    common_words = set(prev_words) & set(curr_words)
    if len(common_words) <= 3:
        return current_text, chunk_start_s
    words = current_text.split()
    if len(words) <= 10:
        return current_text, chunk_start_s
    trimmed_text = " ".join(words[5:])
    adjusted_start = chunk_start_s + (5 * (chunk_end_s - chunk_start_s) / max(len(words), 1))
    return trimmed_text, adjusted_start


def _append_segment(segments: list[dict], index: int, text: str, start_s: float, end_s: float) -> None:
    segments.append({
        "index": index,
        "text": text,
        "start_time": round(start_s, 3),
        "end_time": round(end_s, 3),
        "timestamp": [round(start_s, 3), round(end_s, 3)],
        "srt_timestamp": f"{format_timestamp_srt(start_s)} --> {format_timestamp_srt(end_s)}",
    })


def _process_short_audio(samples: np.ndarray, sample_rate: int, segment_index: int) -> list[dict]:
    text = _decode_chunk_to_text(samples, sample_rate)
    if not text:
        return []
    end_s = len(samples) / sample_rate
    segs: list[dict] = []
    _append_segment(segs, segment_index, text, 0.0, end_s)
    return segs


def process_audio_chunks(samples: np.ndarray, sample_rate: int = 16000) -> list[dict]:
    """
    Process audio in chunks with proper overlap handling and segment-level timestamps
    """
    max_chunk_samples = int(MAX_CHUNK_SECONDS * sample_rate)
    overlap_samples = int(CHUNK_OVERLAP_SECONDS * sample_rate)

    segments: list[dict] = []
    start = 0
    segment_index = 1

    if len(samples) <= max_chunk_samples:
        return _process_short_audio(samples, sample_rate, segment_index)

    while start < len(samples):
        end = min(start + max_chunk_samples, len(samples))
        chunk = samples[start:end]
        if len(chunk) == 0:
            break

        chunk_text = _decode_chunk_to_text(chunk, sample_rate)
        if chunk_text:
            chunk_start_s = start / sample_rate
            chunk_end_s = end / sample_rate

            if segments and start > 0:
                prev_text = segments[-1]["text"]
                chunk_text, chunk_start_s = _maybe_trim_overlap(prev_text, chunk_text, chunk_start_s, chunk_end_s)

            if chunk_text:
                _append_segment(segments, segment_index, chunk_text, chunk_start_s, chunk_end_s)
                segment_index += 1

        if end >= len(samples):
            break
        start = end - overlap_samples
        if start < 0:
            start = 0

    return segments


recognizer = load_recognizer(WHISPER_VARIANT)

app = FastAPI(title="TextSense Audio-to-Text (Whisper ONNX, INT8)")


async def _write_upload_to_file(upload: UploadFile) -> str:
    filename = upload.filename or "audio.wav"
    suffix = os.path.splitext(filename)[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await upload.read()
        tmp.write(content)
        return tmp.name


def _download_audio_to_file(url: str) -> str:
    headers = {"User-Agent": "TextSense-AudioText/1.0"}
    r = requests.get(url, timeout=30, headers=headers)
    r.raise_for_status()
    # Try to infer extension from URL
    suffix = os.path.splitext(url.split("?")[0].split("#")[0])[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(r.content)
        return tmp.name


async def _resolve_tmp_audio_path(audio: UploadFile | None, audio_url: str | None) -> str:
    """Return a temporary local path for provided audio upload or URL.
    Raises ValueError for empty URL. Propagates network errors from requests.
    """
    if audio is not None and getattr(audio, "filename", None):
        return await _write_upload_to_file(audio)
    if audio_url:
        url = audio_url.strip()
        if not url:
            raise ValueError("audio_url is empty")
        return _download_audio_to_file(url)
    raise ValueError("No audio provided. Provide 'audio' file or 'audio_url'.")


def _read_wav_as_float32_mono_16k(path: str) -> tuple[np.ndarray, int]:
    """Read a mono 16kHz WAV as float32 normalized to [-1, 1]."""
    with wave.open(path) as f:
        if f.getnchannels() != 1:
            raise ValueError(f"Expected mono audio, got {f.getnchannels()} channels")
        if f.getsampwidth() != 2:
            raise ValueError(f"Expected 16-bit audio, got {f.getsampwidth() * 8}-bit")
        sample_rate = f.getframerate()
        if sample_rate != 16000:
            raise ValueError(f"Expected 16kHz audio, got {sample_rate}Hz")
        num_frames = f.getnframes()
        pcm_bytes = f.readframes(num_frames)
    samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    return samples, sample_rate


def _build_transcription_response(segments: list[dict], duration_seconds: float, return_timestamps: bool) -> dict:
    full_text = " ".join(seg["text"] for seg in segments).strip()
    response_data: dict = {
        "text": full_text,
        "duration": round(duration_seconds, 3),
        "total_segments": len(segments),
    }
    if return_timestamps:
        response_data["chunks"] = segments
    return response_data


@app.post("/transcribe")
async def transcribe(
    audio: UploadFile | None = File(None),
    audio_url: str | None = Form(None),
    return_timestamps: bool = Form(False),
):
    try:
        tmp_path: str | None = None
        try:
            tmp_path = await _resolve_tmp_audio_path(audio, audio_url)
        except requests.exceptions.ConnectionError as ce:
            return JSONResponse({
                "error": f"Network connection failed: {str(ce)}. The Space may have limited network access."
            }, status_code=400)
        except requests.exceptions.Timeout:
            return JSONResponse({"error": "Request timed out while fetching audio"}, status_code=400)
        except ValueError as ve:
            return JSONResponse({"error": str(ve)}, status_code=400)

        wav_path = _ffmpeg_convert_to_wav_16k_mono(tmp_path)
        try:
            samples, sample_rate = _read_wav_as_float32_mono_16k(wav_path)
            duration_seconds = len(samples) / float(sample_rate)
            segments = process_audio_chunks(samples, sample_rate=sample_rate)
            response_data = _build_transcription_response(segments, duration_seconds, return_timestamps)
        finally:
            try:
                if os.path.exists(wav_path):
                    os.unlink(wav_path)
            except Exception:
                pass

        return JSONResponse(response_data)

    except requests.HTTPError as he:
        return JSONResponse({"error": f"Failed to fetch audio: {str(he)}"}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": f"ASR error: {str(e)}"}, status_code=500)
    finally:
        try:
            if 'tmp_path' in locals() and tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass


@app.get("/healthz")
async def healthz():
    return {
        "ok": True,
        "engine": "sherpa-onnx",
        "variant": WHISPER_VARIANT,
        "max_chunk_seconds": MAX_CHUNK_SECONDS,
        "chunk_overlap_seconds": CHUNK_OVERLAP_SECONDS,
        "supports_long_audio": True,
    }
