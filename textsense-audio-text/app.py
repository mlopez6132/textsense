import os
import io
import tempfile
import subprocess
from typing import Optional, Tuple, List, Dict

import requests
import numpy as np
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from huggingface_hub import hf_hub_download
import sherpa_onnx

# Model and runtime configuration (sherpa-onnx Whisper distil-small.en INT8)
WHISPER_VARIANT = os.getenv("WHISPER_VARIANT", "tiny.en")
MAX_CHUNK_SECONDS = float(os.getenv("MAX_CHUNK_SECONDS", "29.0"))
CHUNK_OVERLAP_SECONDS = float(os.getenv("CHUNK_OVERLAP_SECONDS", "1.0"))  # No overlap
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


def process_audio_chunks(samples: np.ndarray, sample_rate: int = 16000) -> List[Dict]:
    """
    Process audio in chunks with proper overlap handling and segment-level timestamps
    """
    max_chunk_samples = int(MAX_CHUNK_SECONDS * sample_rate)
    overlap_samples = int(CHUNK_OVERLAP_SECONDS * sample_rate)
    
    segments = []
    start = 0
    segment_index = 1
    
    # For short audio (under max chunk size), process as single chunk
    if len(samples) <= max_chunk_samples:
        s = recognizer.create_stream()
        s.accept_waveform(sample_rate, samples)
        recognizer.decode_stream(s)
        text = s.result.text.strip()
        
        if text:
            segments.append({
                "index": segment_index,
                "text": text,
                "start_time": 0.0,
                "end_time": round(len(samples) / sample_rate, 3),
                "timestamp": [0.0, round(len(samples) / sample_rate, 3)],
                "srt_timestamp": f"{format_timestamp_srt(0.0)} --> {format_timestamp_srt(len(samples) / sample_rate)}"
            })
        
        return segments
    
    # Process longer audio in chunks with overlap
    while start < len(samples):
        # Calculate chunk boundaries
        end = min(start + max_chunk_samples, len(samples))
        chunk = samples[start:end]
        
        # Ensure we have audio to process
        if len(chunk) == 0:
            break
            
        # Process chunk
        s = recognizer.create_stream()
        s.accept_waveform(sample_rate, chunk)
        recognizer.decode_stream(s)
        chunk_text = s.result.text.strip()
        
        if chunk_text:
            # Calculate actual timestamps
            chunk_start_s = start / sample_rate
            chunk_end_s = end / sample_rate
            
            # Handle overlap by trimming text from previous chunks if needed
            # This is a simple approach - for more sophisticated handling,
            # you might want to use word-level alignment
            if segments and start > 0:
                # Check if this chunk starts with similar content to previous chunk end
                # This helps avoid duplicate text due to overlap
                prev_text = segments[-1]["text"]
                if len(prev_text) > 50:  # Only check for longer texts
                    prev_words = prev_text.split()[-10:]  # Last 10 words
                    chunk_words = chunk_text.split()[:10]  # First 10 words
                    
                    # Simple overlap detection
                    common_words = set(prev_words) & set(chunk_words)
                    if len(common_words) > 3:  # If significant overlap
                        # Trim the overlapping part from current chunk
                        words = chunk_text.split()
                        if len(words) > 10:
                            chunk_text = " ".join(words[5:])  # Skip first 5 words
                            # Adjust start time accordingly (rough estimation)
                            chunk_start_s += (5 * (chunk_end_s - chunk_start_s) / len(words))
            
            if chunk_text:  # Only add if we still have text after overlap handling
                segments.append({
                    "index": segment_index,
                    "text": chunk_text,
                    "start_time": round(chunk_start_s, 3),
                    "end_time": round(chunk_end_s, 3),
                    "timestamp": [round(chunk_start_s, 3), round(chunk_end_s, 3)],
                    "srt_timestamp": f"{format_timestamp_srt(chunk_start_s)} --> {format_timestamp_srt(chunk_end_s)}"
                })
                segment_index += 1
        
        # Move to next chunk with proper overlap
        if end >= len(samples):  # Last chunk
            break
        
        # For next iteration, start at (current_end - overlap)
        start = end - overlap_samples
        
        # Ensure we don't go backwards
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


@app.post("/transcribe")
async def transcribe(
    audio: Optional[UploadFile] = File(None),
    audio_url: Optional[str] = Form(None),
    return_timestamps: bool = Form(False),
):
    try:
        tmp_path: Optional[str] = None
        if audio is not None and audio.filename:
            tmp_path = await _write_upload_to_file(audio)
        elif audio_url:
            url = audio_url.strip()
            if not url:
                return JSONResponse({"error": "audio_url is empty"}, status_code=400)
            try:
                tmp_path = _download_audio_to_file(url)
            except requests.exceptions.ConnectionError as ce:
                return JSONResponse({
                    "error": f"Network connection failed: {str(ce)}. The Space may have limited network access."
                }, status_code=400)
            except requests.exceptions.Timeout:
                return JSONResponse({"error": "Request timed out while fetching audio"}, status_code=400)
        else:
            return JSONResponse({"error": "No audio provided. Provide 'audio' file or 'audio_url'."}, status_code=400)

        # Ensure correct audio format for sherpa-onnx whisper (mono, 16kHz, s16le WAV)
        wav_path = _ffmpeg_convert_to_wav_16k_mono(tmp_path)
        try:
            # Read wav as int16 PCM and normalize to float32 in [-1,1]
            import wave as _wave
            with _wave.open(wav_path) as f:
                assert f.getnchannels() == 1, f.getnchannels()
                assert f.getsampwidth() == 2, f.getsampwidth()
                sample_rate = f.getframerate()
                assert sample_rate == 16000, sample_rate
                num_frames = f.getnframes()
                pcm_bytes = f.readframes(num_frames)
            samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

            # Calculate audio duration
            duration_seconds = len(samples) / 16000.0
            
            # Process audio with proper chunking
            segments = process_audio_chunks(samples, sample_rate=16000)
            
            # Combine all segment texts
            full_text = " ".join(seg["text"] for seg in segments).strip()
            
            # Add metadata
            response_data = {
                "text": full_text,
                "duration": round(duration_seconds, 3),
                "total_segments": len(segments)
            }
            
            if return_timestamps:
                response_data["chunks"] = segments
                
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