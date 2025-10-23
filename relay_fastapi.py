
import os
import hashlib
import asyncio
import logging
from typing import Optional, Annotated
from urllib.parse import quote

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import (
    HTMLResponse, JSONResponse, FileResponse, PlainTextResponse, StreamingResponse
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx
from httpx import HTTPError, TimeoutException, ConnectError
from cachetools import TTLCache
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Import our generation modules
from image_generation import image_generator
from speech_generation import speech_generator
from audio_transcription import audio_transcriber

HF_INFERENCE_URL_ENV = "HF_INFERENCE_URL"
HF_OCR_URL_ENV = "HF_OCR_URL"
HF_AUDIO_TEXT_URL_ENV = "HF_AUDIO_TEXT_URL"
DEFAULT_TIMEOUT_SECONDS = 120

# Initialize cache for AI detection results (1 hour TTL, max 1000 entries)
detection_cache = TTLCache(maxsize=1000, ttl=3600)
# Thread-safe lock for cache access
cache_lock = asyncio.Lock()

# Initialize async HTTP client with connection pooling
http_client = httpx.AsyncClient(
    limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
    timeout=httpx.Timeout(DEFAULT_TIMEOUT_SECONDS)
)


# ----------------------
# Helper utilities
# ----------------------
def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe use in Content-Disposition header."""
    if not filename:
        return "download"
    
    # Remove path separators and control characters
    safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_"
    sanitized = "".join(c for c in filename if c in safe_chars)
    
    # Ensure it's not empty and has reasonable length
    if not sanitized or len(sanitized) > 255:
        sanitized = "download"
    
    # Quote the filename for safe use in headers
    return quote(sanitized, safe="")


def get_auth_headers() -> dict:
    """Build optional Authorization header from HF_API_KEY."""
    headers: dict = {}
    api_key = os.getenv("HF_API_KEY", "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


async def prepare_text_from_inputs(
    text: str | None,
    file: UploadFile | None,
    max_length: int = 50000,
) -> str:
    """Return text content from either direct text or uploaded file. Raises HTTPException on errors."""
    if (not text or not text.strip()) and (file is None or not getattr(file, "filename", None)):
        raise HTTPException(status_code=400, detail="No text or file provided.")

    submit_text: str | None = None
    if file is not None and file.filename:
        # Optimize: Stream file reading with size limit check
        max_file_size = max_length * 2  # Allow 2x character limit in bytes
        chunks = []
        total_size = 0
        
        try:
            # Use async read() method to stream file in chunks
            await file.seek(0)
            while True:
                chunk = await file.read(8192)  # Read 8KB chunks
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > max_file_size:
                    raise HTTPException(
                        status_code=413, 
                        detail=f"File too large. Maximum size is {max_file_size:,} bytes."
                    )
                chunks.append(chunk)
            
            raw_bytes = b"".join(chunks)
        except OSError as e:
            raise HTTPException(status_code=400, detail=f"File read error: {str(e)}") from e
        
        try:
            submit_text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            submit_text = raw_bytes.decode("latin-1", errors="ignore")
    else:
        submit_text = (text or "").strip()

    if not submit_text:
        raise HTTPException(status_code=400, detail="No text content available.")
    # Only enforce limit when text param was used
    if text and len(submit_text) > max_length:
        raise HTTPException(status_code=400, detail=f"Text input exceeds {max_length:,} character limit.")
    return submit_text


async def forward_post_json(
    remote_url: str,
    *,
    data: dict | None = None,
    files: dict | None = None,
    headers: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    context: str = "Upstream",
) -> dict:
    """POST to upstream and return parsed JSON or raise HTTPException with useful status."""
    try:
        resp = await http_client.post(
            remote_url, 
            data=data, 
            files=files, 
            headers=headers or {}, 
            timeout=timeout
        )
        resp.raise_for_status()
        
        try:
            result = resp.json()
        except Exception as json_err:
            # If JSON parsing fails, include response text for debugging
            response_text = await resp.aread() if hasattr(resp, 'aread') else resp.text
            raise HTTPException(
                status_code=502, 
                detail=f"{context} returned invalid JSON (status {resp.status_code}): {str(json_err)}. Response: {response_text[:500]}"
            ) from json_err
        
        # Check if the response contains an error field
        if isinstance(result, dict) and "error" in result:
            raise HTTPException(status_code=500, detail=f"{context} failed: {result['error']}")
        
        return result
    except HTTPException:
        raise
    except (HTTPError, TimeoutException, ConnectError) as req_err:
        error_detail = f"{context} request failed"
        if hasattr(req_err, 'response') and req_err.response is not None:
            try:
                error_json = req_err.response.json()
                if isinstance(error_json, dict) and "error" in error_json:
                    error_detail = f"{context} failed: {error_json['error']}"
            except:
                # Include status code for better debugging
                status_code = getattr(req_err.response, 'status_code', 'unknown')
                error_detail = f"{context} failed (status {status_code}): {str(req_err)}"
        raise HTTPException(status_code=502, detail=error_detail) from req_err
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{context} failed: {str(e)}") from e


async def build_image_files(
    image: UploadFile | None, image_url: str | None
) -> dict:
    """Return a httpx-compatible files dict for image upload, fetching remote URL if needed."""
    if image is not None and image.filename:
        # Read the uploaded file with size check (max 16MB for images)
        max_image_size = 16 * 1024 * 1024
        
        try:
            # Use UploadFile's async read() method
            await image.seek(0)
            content = await image.read()
            
            if len(content) > max_image_size:
                raise HTTPException(
                    status_code=413,
                    detail="Image file too large. Maximum size is 16MB."
                )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        
        return {
            "image": (
                image.filename,
                content,
                image.content_type or "application/octet-stream",
            )
        }
    if image_url:
        try:
            r = await http_client.get(
                image_url.strip(), 
                timeout=30, 
                headers={"User-Agent": "TextSense-Relay/1.0"}
            )
            r.raise_for_status()
        except (HTTPError, TimeoutException, ConnectError) as req_err:
            raise HTTPException(status_code=502, detail=f"Failed to fetch image URL: {str(req_err)}") from req_err
        mime = r.headers.get("content-type", "application/octet-stream").split(";")[0].strip()
        name = image_url.split("?")[0].rstrip("/").split("/")[-1] or "remote.jpg"
        return {"image": (name, r.content, mime)}
    raise HTTPException(status_code=400, detail="No image provided.")


async def build_audio_payload(
    audio: UploadFile | None, audio_url: str | None, return_timestamps: bool
) -> tuple[dict | None, dict]:
    """Return (files, data) tuple for audio transcription request."""
    data = {"return_timestamps": str(return_timestamps).lower()}
    if audio is not None and audio.filename:
        # Stream read UploadFile using its async read() to avoid blocking and errors
        max_audio_size = 25 * 1024 * 1024  # 25MB
        total_size = 0
        chunks: list[bytes] = []

        try:
            await audio.seek(0)
            while True:
                chunk = await audio.read(8192)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > max_audio_size:
                    raise HTTPException(
                        status_code=413,
                        detail="Audio file too large. Maximum size is 25MB."
                    )
                chunks.append(chunk)
            content = b"".join(chunks)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Audio read error: {str(e)}") from e

        files = {
            "audio": (
                audio.filename,
                content,
                audio.content_type or "application/octet-stream",
            )
        }
        return files, data
    if audio_url:
        data["audio_url"] = audio_url.strip()
        return None, data
    raise HTTPException(status_code=400, detail="No audio provided.")


async def get_audio_bytes_and_format(
    audio: UploadFile | None, audio_url: str | None
) -> tuple[bytes, str]:
    """Return raw audio bytes and inferred format (mp3|wav) from upload or URL."""
    max_audio_size = 25 * 1024 * 1024  # 25MB limit
    if audio is not None and audio.filename:
        total_size = 0
        chunks: list[bytes] = []
        try:
            await audio.seek(0)
            while True:
                chunk = await audio.read(8192)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > max_audio_size:
                    raise HTTPException(status_code=413, detail="Audio file too large. Maximum size is 25MB.")
                chunks.append(chunk)
            content = b"".join(chunks)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Audio read error: {str(e)}") from e

        # Infer format from filename or content type
        ext = (audio.filename.rsplit(".", 1)[-1].lower() if "." in audio.filename else "").strip()
        content_type = (audio.content_type or "").lower()
        audio_format = ext or ("mp3" if "mpeg" in content_type else ("wav" if "wav" in content_type else ""))
        return content, audio_format

    if audio_url:
        try:
            r = await http_client.get(audio_url.strip(), timeout=30, headers={"User-Agent": "TextSense-Relay/1.0"})
            r.raise_for_status()
        except (HTTPError, TimeoutException, ConnectError) as req_err:
            raise HTTPException(status_code=502, detail=f"Failed to fetch audio URL: {str(req_err)}") from req_err

        # Stream and count bytes instead of trusting content-length header
        content = b""
        total_size = 0
        
        async for chunk in r.aiter_bytes(chunk_size=8192):
            total_size += len(chunk)
            if total_size > max_audio_size:
                raise HTTPException(status_code=413, detail="Audio file too large. Maximum size is 25MB.")
            content += chunk

        mime = r.headers.get("content-type", "application/octet-stream").split(";")[0].strip().lower()
        # Try infer format from URL extension if present
        name = audio_url.split("?")[0].rstrip("/").split("/")[-1]
        ext = (name.rsplit(".", 1)[-1].lower() if "." in name else "").strip()
        if ext in {"mp3", "wav"}:
            fmt = ext
        elif "mpeg" in mime or "mp3" in mime:
            fmt = "mp3"
        elif "wav" in mime:
            fmt = "wav"
        else:
            fmt = ""
        return content, fmt

    raise HTTPException(status_code=400, detail="No audio provided.")


def get_remote_url() -> str:
    remote = os.getenv(HF_INFERENCE_URL_ENV, "").strip()
    if not remote:
        raise HTTPException(
            status_code=500,
            detail="No remote inference URL configured. Set HF_INFERENCE_URL to your Hugging Face Space /analyze endpoint."
        )
    return remote


def get_ocr_url() -> str:
    remote = os.getenv(HF_OCR_URL_ENV, "").strip()
    if not remote:
        raise HTTPException(
            status_code=500,
            detail="No OCR URL configured. Set HF_OCR_URL to your Hugging Face Space OCR endpoint."
        )
    return remote


def get_audio_text_url() -> str:
    remote = os.getenv(HF_AUDIO_TEXT_URL_ENV, "").strip()
    if not remote:
        raise HTTPException(
            status_code=500,
            detail="No AUDIO URL configured. Set HF_AUDIO_TEXT_URL to your Hugging Face Space AUDIO endpoint."
        )
    return remote


def validate_environment():
    """Validate required environment variables on startup."""
    missing_vars = []
    
    if not os.getenv(HF_INFERENCE_URL_ENV, "").strip():
        missing_vars.append(f"{HF_INFERENCE_URL_ENV} (Hugging Face inference endpoint)")
    
    if not os.getenv(HF_OCR_URL_ENV, "").strip():
        missing_vars.append(f"{HF_OCR_URL_ENV} (Hugging Face OCR endpoint)")
    
    if not os.getenv(HF_AUDIO_TEXT_URL_ENV, "").strip():
        missing_vars.append(f"{HF_AUDIO_TEXT_URL_ENV} (Hugging Face audio endpoint)")
    
    if missing_vars:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
        print(f"ERROR: {error_msg}")
        raise RuntimeError(error_msg)


app = FastAPI(title="TextSense Relay (FastAPI)")

# Validate environment on startup
validate_environment()

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# Custom rate limit error handler with headers
async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    response = JSONResponse(
        {"error": "Rate limit exceeded", "detail": str(exc.detail)},
        status_code=429
    )
    # Add rate limit headers for frontend consumption
    if hasattr(exc, 'retry_after'):
        response.headers["Retry-After"] = str(exc.retry_after)
    response.headers["X-RateLimit-Limit"] = str(getattr(exc, 'limit', 'unknown'))
    response.headers["X-RateLimit-Remaining"] = "0"
    return response

app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)

# Static and templates
# SECURITY: templates/static is read-only and contains only trusted static assets
# No user uploads are written to this directory - it's safe to expose
app.mount("/static", StaticFiles(directory="templates/static"), name="static")
templates = Jinja2Templates(directory="templates")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Middleware to add cache headers to static files
@app.middleware("http")
async def add_cache_and_cdn_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Add cache headers for static assets
    if request.url.path.startswith("/static/"):
        # Check if file has version parameter (cache busting)
        if "?v=" in str(request.url):
            # Versioned files can be cached longer (1 week)
            response.headers["Cache-Control"] = "public, max-age=604800"
            response.headers["CDN-Cache-Control"] = "public, max-age=604800"
        else:
            # Non-versioned files should be cached shorter (1 hour)
            response.headers["Cache-Control"] = "public, max-age=3600"
            response.headers["CDN-Cache-Control"] = "public, max-age=3600"
        
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # CDN optimization headers
        response.headers["Vary"] = "Accept-Encoding"
    
    # Add modern security headers for all responses
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # Content Security Policy (restrictive but functional)
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://pagead2.googlesyndication.com https://www.google.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "img-src 'self' data: https:; "
        "font-src 'self' https://cdnjs.cloudflare.com; "
        "connect-src 'self' https:; "
        "frame-src https://www.google.com; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    response.headers["Content-Security-Policy"] = csp
    
    # Strict Transport Security (if served over HTTPS)
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    # Permissions Policy (restrictive permissions)
    permissions_policy = (
        "camera=(), "
        "microphone=(), "
        "geolocation=(), "
        "payment=(), "
        "usb=(), "
        "magnetometer=(), "
        "gyroscope=(), "
        "accelerometer=()"
    )
    response.headers["Permissions-Policy"] = permissions_policy
    
    return response


def get_cache_key(text: str) -> str:
    """Generate cache key from text content."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


@app.get("/favicon.ico")
async def favicon():
    return FileResponse("templates/static/favicon.ico")


@app.get("/site.webmanifest")
async def site_webmanifest():
    return FileResponse("templates/static/site.webmanifest", media_type="application/manifest+json")


@app.get("/apple-touch-icon.png")
async def apple_touch_icon():
    return FileResponse("templates/static/apple-touch-icon.png")


@app.get("/favicon-32x32.png")
async def favicon_32x32():
    return FileResponse("templates/static/favicon-32x32.png")


@app.get("/favicon-16x16.png")
async def favicon_16x16():
    return FileResponse("templates/static/favicon-16x16.png")


@app.get("/android-chrome-192x192.png")
async def android_chrome_192():
    return FileResponse("templates/static/android-chrome-192x192.png")


@app.get("/android-chrome-512x512.png")
async def android_chrome_512():
    return FileResponse("templates/static/android-chrome-512x512.png")


@app.get("/", response_class=HTMLResponse)
@app.head("/")
async def index(request: Request):
    context = {"request": request, "contact_email": os.getenv("CONTACT_EMAIL", "")}
    return templates.TemplateResponse("index.html", context)


@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    context = {"request": request, "contact_email": os.getenv("CONTACT_EMAIL", "")}
    return templates.TemplateResponse("about.html", context)


@app.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    context = {"request": request, "contact_email": os.getenv("CONTACT_EMAIL", "")}
    return templates.TemplateResponse("privacy.html", context)


@app.get("/terms", response_class=HTMLResponse)
async def terms(request: Request):
    context = {"request": request, "contact_email": os.getenv("CONTACT_EMAIL", "")}
    return templates.TemplateResponse("terms.html", context)


@app.get("/contact", response_class=HTMLResponse)
async def contact(request: Request):
    context = {
        "request": request,
        "contact_email": os.getenv("CONTACT_EMAIL", ""),
        "recaptcha_site_key": os.getenv("RECAPTCHA_SITE_KEY", ""),
    }
    return templates.TemplateResponse("contact.html", context)


@app.get("/ocr", response_class=HTMLResponse)
async def ocr_page(request: Request):
    context = {"request": request, "contact_email": os.getenv("CONTACT_EMAIL", "")}
    return templates.TemplateResponse("ocr.html", context)


@app.get("/audio-text", response_class=HTMLResponse)
async def audio_text_page(request: Request):
    context = {"request": request, "contact_email": os.getenv("CONTACT_EMAIL", "")}
    return templates.TemplateResponse("audio-text.html", context)


@app.get("/ai-detector", response_class=HTMLResponse)
async def ai_detector_page(request: Request):
    context = {"request": request, "contact_email": os.getenv("CONTACT_EMAIL", "")}
    return templates.TemplateResponse("ai-detector.html", context)


@app.get("/generate-image-page", response_class=HTMLResponse)
async def generate_image_page(request: Request):
    context = {"request": request, "contact_email": os.getenv("CONTACT_EMAIL", "")}
    return templates.TemplateResponse("generate-image.html", context)


@app.get("/text-to-speech", response_class=HTMLResponse)
async def text_to_speech_page(request: Request):
    context = {"request": request, "contact_email": os.getenv("CONTACT_EMAIL", "")}
    return templates.TemplateResponse("text-to-speech.html", context)


@app.post("/contact")
@limiter.limit("5/minute")  # Rate limit: 5 contact form submissions per minute
async def submit_contact(request: Request):
    form = await request.form()
    name = (form.get("name") or "").strip()
    email = (form.get("email") or "").strip()
    message = (form.get("message") or "").strip()
    token = (form.get("g-recaptcha-response") or "").strip()

    secret = os.getenv("RECAPTCHA_SECRET_KEY", "").strip()
    if secret:
        try:
            verify = await http_client.post(
                "https://www.google.com/recaptcha/api/siteverify",
                data={"secret": secret, "response": token},
                timeout=10,
            )
            
            if verify.status_code != 200:
                logging.warning(f"reCAPTCHA verification failed with status {verify.status_code}")
                return JSONResponse({"ok": False, "error": "reCAPTCHA verification failed"}, status_code=400)
            
            result = verify.json()
            if not result.get("success"):
                error_codes = result.get("error-codes", [])
                logging.warning(f"reCAPTCHA verification failed: {error_codes}")
                return JSONResponse({"ok": False, "error": "reCAPTCHA verification failed"}, status_code=400)
                
        except (TimeoutException, ConnectError) as net_err:
            logging.error(f"reCAPTCHA network error: {str(net_err)}")
            return JSONResponse({"ok": False, "error": f"reCAPTCHA network error: {str(net_err)}"}, status_code=400)
        except HTTPError as req_err:
            logging.error(f"reCAPTCHA request error: {str(req_err)}")
            return JSONResponse({"ok": False, "error": f"reCAPTCHA request error: {str(req_err)}"}, status_code=400)
        except Exception as e:
            logging.error(f"reCAPTCHA unexpected error: {str(e)}")
            return JSONResponse({"ok": False, "error": "reCAPTCHA verification failed"}, status_code=400)

    return JSONResponse({"ok": True, "received": {"name": name, "email": email, "message": message}})


@app.get("/cookies", response_class=HTMLResponse)
async def cookies(request: Request):
    context = {"request": request, "contact_email": os.getenv("CONTACT_EMAIL", "")}
    return templates.TemplateResponse("cookies.html", context)


@app.get("/ads.txt", response_class=PlainTextResponse)
async def ads_txt():
    pub_id = os.getenv("ADSENSE_PUB_ID", "pub-2409576003450898").strip()
    return f"google.com, {pub_id}, DIRECT, f08c47fec0942fa0"


@app.post("/analyze")
@limiter.limit("20/minute")  # Rate limit: 20 analysis requests per minute
async def analyze(
    request: Request,
    text: Annotated[Optional[str], Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
):
    submit_text = await prepare_text_from_inputs(text, file, max_length=50000)
    
    # Check cache first with thread-safe access
    cache_key = get_cache_key(submit_text)
    async with cache_lock:
        if cache_key in detection_cache:
            cached_result = detection_cache[cache_key]
            cached_result["cached"] = True
            return JSONResponse(cached_result)
    
    # Call remote API
    remote_url = get_remote_url()
    headers = get_auth_headers()
    result = await forward_post_json(
        remote_url,
        data={"text": submit_text},
        headers=headers,
        context="Analyze",
    )
    
    # Cache the result with thread-safe access
    result["cached"] = False
    async with cache_lock:
        detection_cache[cache_key] = result
    
    return JSONResponse(result)


@app.post("/ocr")
@limiter.limit("15/minute")  # Rate limit: 15 OCR requests per minute
async def ocr(
    request: Request,
    image_url: Annotated[Optional[str], Form()] = None,
    image: Annotated[UploadFile | None, File()] = None,
    language: Annotated[str, Form()] = "en",
):
    try:
        files = await build_image_files(image, image_url)
        remote_url = get_ocr_url()
        headers = get_auth_headers()
        result = await forward_post_json(
            remote_url,
            data={"language": language},
            files=files,
            headers=headers,
            context="OCR",
        )
        return JSONResponse(result)
    except HTTPException as e:
        # Return error in JSON format that the frontend expects
        return JSONResponse({"error": e.detail}, status_code=e.status_code)


@app.post("/audio-transcribe")
@limiter.limit("10/minute")  # Rate limit: 10 audio transcription requests per minute
async def audio_transcribe(
    request: Request,
    audio: Annotated[UploadFile | None, File()] = None,
    audio_url: Annotated[Optional[str], Form()] = None,
    audio_type: Annotated[Optional[str], Form()] = "general",
    language: Annotated[Optional[str], Form()] = None,
):
    audio_bytes, audio_format = await get_audio_bytes_and_format(audio, audio_url)

    normalized_fmt = (audio_format or "").lower()
    if normalized_fmt not in {"mp3", "wav"}:
        raise HTTPException(status_code=400, detail="Unsupported audio format. Only MP3 and WAV are supported.")

    try:
        openai_json = await audio_transcriber.transcribe(
            audio_bytes=audio_bytes,
            audio_format=normalized_fmt,
            question="Transcribe this:",
            audio_type=audio_type,
            language=language,
        )

        extracted_text: str = ""
        if isinstance(openai_json, dict):
            if isinstance(openai_json.get("text"), str):
                extracted_text = openai_json.get("text", "")
            else:
                try:
                    choices = openai_json.get("choices") or []
                    if choices:
                        message = choices[0].get("message") or {}
                        content = message.get("content")
                        if isinstance(content, str):
                            extracted_text = content
                except Exception:
                    extracted_text = ""

        response_body = {
            "text": extracted_text,
        }
        return JSONResponse(response_body)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except RuntimeError as re:
        raise HTTPException(status_code=502, detail=str(re))


@app.post("/generate-image")
@limiter.limit("5/minute")  # Rate limit: 5 image generation requests per minute (expensive operation)
async def generate_image(
    request: Request,
    prompt: str = Form(...),
    aspect_ratio: str = Form("1:1"),
    num_images: int = Form(1),
    enable_safety_checker: bool = Form(True),
    enable_prompt_optimizer: bool = Form(True),
    negative_prompt: Optional[str] = Form("")
):
    try:
        result = await image_generator.generate_images(
            prompt=prompt,
            negative_prompt=negative_prompt,
            aspect_ratio=aspect_ratio,
            num_images=num_images,
            enhance_prompt=enable_prompt_optimizer,
            enable_safety_checker=enable_safety_checker,
            model="flux"
        )
        return JSONResponse(result)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve)) from ve
    except RuntimeError as re:
        raise HTTPException(status_code=500, detail=f"Image generation runtime error: {str(re)}") from re


@app.post("/generate-speech")
@limiter.limit("8/minute")  # Rate limit: 8 speech generation requests per minute (expensive operation)
async def generate_speech(
    request: Request,
    text: str = Form(...),
    voice: str = Form("alloy"),
    vibe: str = Form("")
):
    """Generate speech from text using the speech generation module."""
    try:
        # Use the speech generator module to handle all the logic
        return await speech_generator.generate_speech(
            text=text,
            voice=voice,
            vibe=vibe,
            max_retries=3
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except RuntimeError as re:
        raise HTTPException(status_code=502, detail=str(re))


@app.get("/download-image")
@limiter.limit("10/minute")  # Rate limit: 10 image downloads per minute (prevent bandwidth abuse)
async def download_image(request: Request, url: str, filename: str = "generated_image.png"):
    if not url.startswith("https://image.pollinations.ai/"):
        raise HTTPException(status_code=400, detail="Invalid image URL")

    try:
        async with http_client.stream("GET", url, timeout=30) as response:
            response.raise_for_status()
            
            # Check file size to prevent abuse (max 100MB)
            content_length = int(response.headers.get("content-length", 0))
            if content_length > 100 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="File too large (max 100MB)")
            
            content_type = response.headers.get("content-type", "image/png")
            if not filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                if "jpeg" in content_type:
                    filename += ".jpg"
                elif "webp" in content_type:
                    filename += ".webp"
                else:
                    filename += ".png"

            # Sanitize filename for safe use in Content-Disposition
            safe_filename = sanitize_filename(filename)

            async def stream_content():
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    yield chunk

            return StreamingResponse(
                stream_content(),
                media_type=content_type,
                headers={
                    "Content-Disposition": f"attachment; filename=\"{safe_filename}\"",
                    "Cache-Control": "no-cache"
                }
            )
    except HTTPException:
        raise
    except (HTTPError, TimeoutException, ConnectError) as req_err:
        raise HTTPException(status_code=502, detail=f"Image download failed: {str(req_err)}") from req_err


@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.get("/clear-cache")
async def clear_cache():
    """Clear CDN cache for static files (development/debugging only)."""
    # This is a simple endpoint to help with cache issues during development
    # In production, you might want to restrict access to this endpoint
    return {
        "message": "Cache headers updated. Please hard refresh your browser (Ctrl+F5 or Cmd+Shift+R)",
        "timestamp": "2025-01-23",
        "note": "Static files now have shorter cache times for easier development"
    }


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    await http_client.aclose()
