import os
import tempfile
import subprocess
import requests
from typing import Optional, List, Dict
import asyncio
import aiohttp

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from concurrent.futures import ThreadPoolExecutor

# -------------------
# Config
# -------------------
# ElevenLabs API configuration
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/speech-to-text"

if not ELEVENLABS_API_KEY:
    print("Warning: ELEVENLABS_API_KEY environment variable not set")

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


app = FastAPI(title="TextSense Audio-to-Text (ElevenLabs)")

@app.on_event("startup")
async def startup_event():
    """Check ElevenLabs API configuration on startup."""
    print("Checking ElevenLabs API configuration...")
    if not ELEVENLABS_API_KEY:
        print("Warning: ELEVENLABS_API_KEY not configured. API calls will fail.")
    else:
        print("ElevenLabs API key configured successfully")


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
# ElevenLabs Speech-to-Text helpers
# -------------------

async def _transcribe_with_elevenlabs(audio_path: str, include_words: bool) -> Dict:
    """
    Transcribe audio using ElevenLabs Speech-to-Text API
    """
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY not configured")
    
    try:
        print(f"Starting ElevenLabs transcription for: {audio_path}")
        print(f"Include word timestamps: {include_words}")
        
        # Prepare the file for upload
        headers = {
            'xi-api-key': ELEVENLABS_API_KEY
        }
        
        print("Sending request to ElevenLabs API...")
        
        async with aiohttp.ClientSession() as session:
            # Create form data
            data = aiohttp.FormData()
            data.add_field('model_id', 'eleven_scribe_v1')
            data.add_field('output_format', 'json')
            
            # Add the audio file
            with open(audio_path, 'rb') as audio_file:
                data.add_field('audio', audio_file, 
                             filename=os.path.basename(audio_path),
                             content_type='audio/wav')
                
                async with session.post(
                    ELEVENLABS_API_URL,
                    data=data,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=TRANSCRIPTION_TIMEOUT)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise RuntimeError(f"ElevenLabs API error ({response.status}): {error_text}")
                    
                    result = await response.json()
                    
        print("ElevenLabs transcription completed successfully")
        return _process_elevenlabs_response(result, include_words)
        
    except Exception as e:
        print(f"Error in _transcribe_with_elevenlabs: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        raise RuntimeError(f"ElevenLabs transcription failed: {str(e)}")


def _process_elevenlabs_response(elevenlabs_result: Dict, include_words: bool) -> Dict:
    """
    Process ElevenLabs API response and convert to our standard format
    """
    print("Processing ElevenLabs response...")
    
    # Extract main text and language
    full_text = elevenlabs_result.get("text", "").strip()
    language_code = elevenlabs_result.get("language_code", "en")
    
    print(f"Detected language: {language_code}")
    print(f"Full text length: {len(full_text)} characters")
    
    # Process words into segments and word-level timestamps
    words = elevenlabs_result.get("words", [])
    segments = []
    
    if not words:
        # If no words, create a single segment with the full text
        if full_text:
            segments.append({
                "text": full_text,
                "timestamp": [0.0, 0.0]
            })
    else:
        # Group words into sentences/segments based on punctuation or speaker changes
        current_segment_words = []
        current_speaker = None
        
        for word_data in words:
            if word_data.get("type") != "word":
                continue
                
            word_text = word_data.get("text", "").strip()
            if not word_text:
                continue
                
            word_start = float(word_data.get("start", 0))
            word_end = float(word_data.get("end", 0))
            speaker_id = word_data.get("speaker_id", "speaker_0")
            
            # Start new segment if speaker changes or we hit sentence-ending punctuation
            if (current_speaker and current_speaker != speaker_id) or \
               (current_segment_words and word_text.endswith(('.', '!', '?'))):
                
                if current_segment_words:
                    # Create segment from accumulated words
                    segment_text = "".join(w["text"] for w in current_segment_words).strip()
                    segment_start = current_segment_words[0]["start"]
                    segment_end = current_segment_words[-1]["end"]
                    
                    segment = {
                        "text": segment_text,
                        "timestamp": [round(segment_start, 3), round(segment_end, 3)]
                    }
                    
                    if include_words:
                        segment["words"] = [{
                            "text": w["text"],
                            "timestamp": [round(w["start"], 3), round(w["end"], 3)]
                        } for w in current_segment_words]
                    
                    segments.append(segment)
                    print(f"Created segment: '{segment_text}' [{segment_start:.3f} - {segment_end:.3f}]")
                
                current_segment_words = []
            
            current_segment_words.append({
                "text": word_text,
                "start": word_start,
                "end": word_end
            })
            current_speaker = speaker_id
        
        # Don't forget the last segment
        if current_segment_words:
            segment_text = "".join(w["text"] for w in current_segment_words).strip()
            segment_start = current_segment_words[0]["start"]
            segment_end = current_segment_words[-1]["end"]
            
            segment = {
                "text": segment_text,
                "timestamp": [round(segment_start, 3), round(segment_end, 3)]
            }
            
            if include_words:
                segment["words"] = [{
                    "text": w["text"],
                    "timestamp": [round(w["start"], 3), round(w["end"], 3)]
                } for w in current_segment_words]
            
            segments.append(segment)
            print(f"Created final segment: '{segment_text}' [{segment_start:.3f} - {segment_end:.3f}]")
    
    print(f"Final result: {len(segments)} segments")
    
    return {
        "text": full_text,
        "chunks": segments,
        "engine": "elevenlabs",
        "model": "eleven_scribe_v1",
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

        # Use ElevenLabs Speech-to-Text API
        print("Starting ElevenLabs transcription...")
        try:
            result = await asyncio.wait_for(
                _transcribe_with_elevenlabs(wav_path, include_word_timestamps),
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
        "engine": "elevenlabs",
        "model": "eleven_scribe_v1",
        "api_key_configured": bool(ELEVENLABS_API_KEY),
    }


