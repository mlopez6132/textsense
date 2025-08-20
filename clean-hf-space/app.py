import os
import tempfile
import subprocess
import requests
from typing import Optional, List, Dict
import asyncio
from openai import OpenAI

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from concurrent.futures import ThreadPoolExecutor

# -------------------
# Config
# -------------------
# OpenAI API configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    print("Warning: OPENAI_API_KEY environment variable not set")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Thread pool for processing so FastAPI loop is not blocked
executor = ThreadPoolExecutor(max_workers=int(os.getenv("DECODE_THREADS", "2")))

# Timeout settings
TRANSCRIPTION_TIMEOUT = int(os.getenv("TRANSCRIPTION_TIMEOUT", "300"))  # 5 minutes for transcription


# -------------------
# Helpers
# -------------------
def _ffmpeg_convert_to_wav_16k_mono(src_path: str) -> str:
    dst_fd, dst_path = tempfile.mkstemp(suffix=".wav")
    os.close(dst_fd)
    cmd = [
        "ffmpeg", "-y", "-i", src_path,
        "-ac", "1", "-ar", "16000", "-acodec", "pcm_s16le",
        dst_path,
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        if os.path.exists(dst_path):
            os.unlink(dst_path)
        raise RuntimeError(f"ffmpeg conversion failed: {e.stderr.decode(errors='ignore')}")
    return dst_path


app = FastAPI(title="TextSense Audio-to-Text (OpenAI Whisper)")

@app.on_event("startup")
async def startup_event():
    """Check OpenAI API configuration on startup."""
    print("Checking OpenAI API configuration...")
    if not OPENAI_API_KEY:
        print("Warning: OPENAI_API_KEY not configured. API calls will fail.")
    else:
        print("OpenAI API key configured successfully")


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
    suffix = os.path.splitext(url.split("?")[0].split("#")[0])[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(r.content)
    return tmp.name


# -------------------
# OpenAI Whisper Speech-to-Text helpers
# -------------------

async def _transcribe_with_whisper(audio_path: str, include_words: bool) -> Dict:
    """
    Transcribe audio using OpenAI Whisper API
    """
    if not client:
        raise RuntimeError("OPENAI_API_KEY not configured")
    
    try:
        print(f"Starting OpenAI Whisper transcription for: {audio_path}")
        print(f"Include word timestamps: {include_words}")
        
        # Read the audio file
        with open(audio_path, 'rb') as audio_file:
            print("Sending request to OpenAI Whisper API...")
            
            # Set up transcription parameters
            transcription_params = {
                "model": "whisper-1",
                "response_format": "verbose_json"
            }
            
            # Add timestamp granularities if word timestamps are requested
            if include_words:
                transcription_params["timestamp_granularities"] = ["word"]
            
            # Make the API call
            result = await asyncio.get_event_loop().run_in_executor(
                executor, 
                lambda: client.audio.transcriptions.create(
                    file=audio_file,
                    **transcription_params
                )
            )
                    
        print("OpenAI Whisper transcription completed successfully")
        return _process_whisper_response(result, include_words)
        
    except Exception as e:
        print(f"Error in _transcribe_with_whisper: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        raise RuntimeError(f"OpenAI Whisper transcription failed: {str(e)}")


def _process_whisper_response(whisper_result, include_words: bool) -> Dict:
    """
    Process OpenAI Whisper API response and convert to our standard format
    """
    print("Processing OpenAI Whisper response...")
    
    # Extract main text and language
    full_text = whisper_result.text.strip() if hasattr(whisper_result, 'text') else ""
    language_code = whisper_result.language if hasattr(whisper_result, 'language') else "en"
    
    print(f"Detected language: {language_code}")
    print(f"Full text length: {len(full_text)} characters")
    
    segments = []
    
    # Check if we have segments (verbose_json format)
    if hasattr(whisper_result, 'segments') and whisper_result.segments:
        print(f"Processing {len(whisper_result.segments)} segments")
        
        for segment in whisper_result.segments:
            segment_data = {
                "text": segment.text.strip(),
                "timestamp": [round(segment.start, 3), round(segment.end, 3)]
            }
            
            # Add word-level timestamps if available and requested
            if include_words and hasattr(whisper_result, 'words') and whisper_result.words:
                # Filter words that belong to this segment
                segment_words = []
                for word in whisper_result.words:
                    if segment.start <= word.start <= segment.end:
                        segment_words.append({
                            "text": word.word,
                            "timestamp": [round(word.start, 3), round(word.end, 3)]
                        })
                
                if segment_words:
                    segment_data["words"] = segment_words
            
            segments.append(segment_data)
            print(f"Created segment: '{segment_data['text']}' [{segment.start:.3f} - {segment.end:.3f}]")
    
    else:
        # Fallback: create a single segment with the full text
        if full_text:
            segment_data = {
                "text": full_text,
                "timestamp": [0.0, 0.0]
            }
            
            # Add word-level timestamps if available and requested
            if include_words and hasattr(whisper_result, 'words') and whisper_result.words:
                segment_data["words"] = [{
                    "text": word.word,
                    "timestamp": [round(word.start, 3), round(word.end, 3)]
                } for word in whisper_result.words]
            
            segments.append(segment_data)
            print(f"Created single segment with full text")
    
    print(f"Final result: {len(segments)} segments")
    
    return {
        "text": full_text,
        "chunks": segments,
        "engine": "openai_whisper",
        "model": "whisper-1",
        "language": language_code
    }


# -------------------
# FastAPI route
# -------------------
@app.post("/transcribe")
async def transcribe(
    audio: Optional[UploadFile] = File(None),
    audio_url: Optional[str] = Form(None),
    include_word_timestamps: bool = Form(False),
):
    tmp_path: Optional[str] = None
    wav_path: Optional[str] = None

    try:
        print("=== New transcription request ===")
        # Input handling
        if audio is not None and audio.filename:
            print(f"Processing uploaded file: {audio.filename}")
            tmp_path = await _write_upload_to_file(audio)
            print(f"Saved to temp path: {tmp_path}")
        elif audio_url:
            url = audio_url.strip()
            if not url:
                return JSONResponse({"error": "audio_url is empty"}, status_code=400)
            print(f"Downloading audio from URL: {url}")
            tmp_path = _download_audio_to_file(url)
            print(f"Downloaded to temp path: {tmp_path}")
        else:
            return JSONResponse({"error": "No audio provided"}, status_code=400)

        # Convert to WAV
        print("Converting audio to WAV format...")
        wav_path = _ffmpeg_convert_to_wav_16k_mono(tmp_path)
        print(f"Converted WAV path: {wav_path}")

        # Use OpenAI Whisper Speech-to-Text API
        print("Starting OpenAI Whisper transcription...")
        try:
            result = await asyncio.wait_for(
                _transcribe_with_whisper(wav_path, include_word_timestamps),
                timeout=TRANSCRIPTION_TIMEOUT
            )
            print("Transcription completed successfully")
            return JSONResponse(result)
        except asyncio.TimeoutError:
            print(f"Transcription timed out after {TRANSCRIPTION_TIMEOUT} seconds")
            return JSONResponse({"error": f"Transcription timed out after {TRANSCRIPTION_TIMEOUT} seconds. Try a shorter audio file."}, status_code=408)

    except requests.HTTPError as he:
        return JSONResponse({"error": f"Failed to fetch audio: {str(he)}"}, status_code=400)
    except RuntimeError as re:
        # Specific handling for model loading and transcription errors
        return JSONResponse({"error": f"Transcription error: {str(re)}"}, status_code=500)
    except Exception as e:
        # General error with more details
        import traceback
        error_details = traceback.format_exc()
        print(f"Unexpected error: {error_details}")
        return JSONResponse({"error": f"ASR error: {str(e)}"}, status_code=500)
    finally:
        for p in [tmp_path, wav_path]:
            if p and os.path.exists(p):
                try:
                    os.unlink(p)
                except Exception:
                    pass


@app.get("/healthz")
async def healthz():
    return {
        "ok": True,
        "engine": "openai_whisper",
        "model": "whisper-1",
        "api_key_configured": bool(OPENAI_API_KEY),
    }


