from __future__ import annotations

import os
from typing import Union, Tuple

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import (
    HTMLResponse, JSONResponse, FileResponse, PlainTextResponse, StreamingResponse
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError as ReqConnectionError

# Import our image generation module
from image_generation import image_generator

HF_INFERENCE_URL_ENV = "HF_INFERENCE_URL"
HF_OCR_URL_ENV = "HF_OCR_URL"
HF_AUDIO_TEXT_URL_ENV = "HF_AUDIO_TEXT_URL"
DEFAULT_TIMEOUT_SECONDS = 120


# ----------------------
# Helper utilities
# ----------------------
def get_auth_headers() -> dict:
    """Build optional Authorization header from HF_API_KEY."""
    headers: dict = {}
    api_key = os.getenv("HF_API_KEY", "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


async def prepare_text_from_inputs(
    text: Union[str, None],
    file: Union[UploadFile, None],
    max_length: int = 50000,
) -> str:
    """Return text content from either direct text or uploaded file. Raises HTTPException on errors."""
    if (not text or not text.strip()) and (file is None or not getattr(file, "filename", None)):
        raise HTTPException(status_code=400, detail="No text or file provided.")

    submit_text: Union[str, None] = None
    if file is not None and file.filename:
        try:
            raw_bytes = await file.read()
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


def forward_post_json(
    remote_url: str,
    *,
    data: Union[dict, None] = None,
    files: Union[dict, None] = None,
    headers: Union[dict, None] = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    context: str = "Upstream",
) -> dict:
    """POST to upstream and return parsed JSON or raise HTTPException with useful status."""
    try:
        resp = requests.post(remote_url, data=data, files=files, headers=headers or {}, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except RequestException as req_err:
        raise HTTPException(status_code=502, detail=f"{context} request failed: {str(req_err)}") from req_err


async def build_image_files(
    image: Union[UploadFile, None], image_url: Union[str, None]
) -> dict:
    """Return a requests-compatible files dict for image upload, fetching remote URL if needed."""
    if image is not None and image.filename:
        content = await image.read()
        return {
            "image": (
                image.filename,
                content,
                image.content_type or "application/octet-stream",
            )
        }
    if image_url:
        try:
            r = requests.get(image_url.strip(), timeout=30, headers={"User-Agent": "TextSense-Relay/1.0"})
            r.raise_for_status()
        except RequestException as req_err:
            raise HTTPException(status_code=502, detail=f"Failed to fetch image URL: {str(req_err)}") from req_err
        mime = r.headers.get("content-type", "application/octet-stream").split(";")[0].strip()
        name = image_url.split("?")[0].rstrip("/").split("/")[-1] or "remote.jpg"
        return {"image": (name, r.content, mime)}
    raise HTTPException(status_code=400, detail="No image provided.")


async def build_audio_payload(
    audio: Union[UploadFile, None], audio_url: Union[str, None], return_timestamps: bool
) -> Tuple[Union[dict, None], dict]:
    """Return (files, data) tuple for audio transcription request."""
    data = {"return_timestamps": str(return_timestamps).lower()}
    if audio is not None and audio.filename:
        content = await audio.read()
        files = {
            "audio": (
                audio.filename,
                content,
                audio.content_type or "audio/mpeg",
            )
        }
        return files, data
    if audio_url:
        data["audio_url"] = audio_url.strip()
        return None, data
    raise HTTPException(status_code=400, detail="No audio provided.")


def get_remote_url() -> str:
    remote = os.getenv(HF_INFERENCE_URL_ENV, "").strip()
    if not remote:
        raise RuntimeError(
            "No remote inference URL configured. Set HF_INFERENCE_URL to your Hugging Face Space /analyze endpoint."
        )
    return remote


def get_ocr_url() -> str:
    remote = os.getenv(HF_OCR_URL_ENV, "").strip()
    if not remote:
        raise RuntimeError(
            "No OCR URL configured. Set HF_OCR_URL to your Hugging Face Space OCR endpoint."
        )
    return remote


def get_audio_text_url() -> str:
    remote = os.getenv(HF_AUDIO_TEXT_URL_ENV, "").strip()
    if not remote:
        raise RuntimeError(
            "No AUDIO URL configured. Set HF_AUDIO_TEXT_URL to your Hugging Face Space AUDIO endpoint."
        )
    return remote


app = FastAPI(title="TextSense Relay (FastAPI)")

# Static and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/favicon.ico")
async def favicon():
    return FileResponse("static/favicon.ico")


@app.get("/site.webmanifest")
async def site_webmanifest():
    return FileResponse("static/site.webmanifest", media_type="application/manifest+json")


@app.get("/apple-touch-icon.png")
async def apple_touch_icon():
    return FileResponse("static/apple-touch-icon.png")


@app.get("/favicon-32x32.png")
async def favicon_32x32():
    return FileResponse("static/favicon-32x32.png")


@app.get("/favicon-16x16.png")
async def favicon_16x16():
    return FileResponse("static/favicon-16x16.png")


@app.get("/android-chrome-192x192.png")
async def android_chrome_192():
    return FileResponse("static/android-chrome-192x192.png")


@app.get("/android-chrome-512x512.png")
async def android_chrome_512():
    return FileResponse("static/android-chrome-512x512.png")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    context = {"request": request, "contact_email": os.getenv("CONTACT_EMAIL", "textsense2@gmail.com")}
    return templates.TemplateResponse("index.html", context)


@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    context = {"request": request, "contact_email": os.getenv("CONTACT_EMAIL", "textsense2@gmail.com")}
    return templates.TemplateResponse("about.html", context)


@app.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    context = {"request": request, "contact_email": os.getenv("CONTACT_EMAIL", "textsense2@gmail.com")}
    return templates.TemplateResponse("privacy.html", context)


@app.get("/terms", response_class=HTMLResponse)
async def terms(request: Request):
    context = {"request": request, "contact_email": os.getenv("CONTACT_EMAIL", "textsense2@gmail.com")}
    return templates.TemplateResponse("terms.html", context)


@app.get("/contact", response_class=HTMLResponse)
async def contact(request: Request):
    context = {
        "request": request,
        "contact_email": os.getenv("CONTACT_EMAIL", "textsense2@gmail.com"),
        "recaptcha_site_key": os.getenv("RECAPTCHA_SITE_KEY", ""),
    }
    return templates.TemplateResponse("contact.html", context)


@app.get("/ocr", response_class=HTMLResponse)
async def ocr_page(request: Request):
    context = {"request": request, "contact_email": os.getenv("CONTACT_EMAIL", "textsense2@gmail.com")}
    return templates.TemplateResponse("ocr.html", context)


@app.get("/audio-text", response_class=HTMLResponse)
async def audio_text_page(request: Request):
    context = {"request": request, "contact_email": os.getenv("CONTACT_EMAIL", "textsense2@gmail.com")}
    return templates.TemplateResponse("audio-text.html", context)


@app.get("/ai-detector", response_class=HTMLResponse)
async def ai_detector_page(request: Request):
    context = {"request": request, "contact_email": os.getenv("CONTACT_EMAIL", "textsense2@gmail.com")}
    return templates.TemplateResponse("ai-detector.html", context)


@app.get("/generate-image-page", response_class=HTMLResponse)
async def generate_image_page(request: Request):
    context = {"request": request, "contact_email": os.getenv("CONTACT_EMAIL", "textsense2@gmail.com")}
    return templates.TemplateResponse("generate-image.html", context)


@app.post("/contact")
async def submit_contact(request: Request):
    form = await request.form()
    name = (form.get("name") or "").strip()
    email = (form.get("email") or "").strip()
    message = (form.get("message") or "").strip()
    token = (form.get("g-recaptcha-response") or "").strip()

    secret = os.getenv("RECAPTCHA_SECRET_KEY", "").strip()
    if secret:
        try:
            verify = requests.post(
                "https://www.google.com/recaptcha/api/siteverify",
                data={"secret": secret, "response": token},
                timeout=10,
            )
            if verify.status_code == 200:
                result = verify.json()
                if not result.get("success"):
                    return JSONResponse({"ok": False, "error": "reCAPTCHA verification failed"}, status_code=400)
        except (Timeout, ReqConnectionError) as net_err:
            return JSONResponse({"ok": False, "error": f"reCAPTCHA network error: {str(net_err)}"}, status_code=400)
        except RequestException as req_err:
            return JSONResponse({"ok": False, "error": f"reCAPTCHA request error: {str(req_err)}"}, status_code=400)

    return JSONResponse({"ok": True, "received": {"name": name, "email": email, "message": message}})


@app.get("/cookies", response_class=HTMLResponse)
async def cookies(request: Request):
    context = {"request": request, "contact_email": os.getenv("CONTACT_EMAIL", "textsense2@gmail.com")}
    return templates.TemplateResponse("cookies.html", context)


@app.get("/ads.txt", response_class=PlainTextResponse)
async def ads_txt():
    pub_id = os.getenv("ADSENSE_PUB_ID", "pub-2409576003450898").strip()
    return f"google.com, {pub_id}, DIRECT, f08c47fec0942fa0"


@app.post("/analyze")
async def analyze(text: Union[str, None] = Form(None), file: Union[UploadFile, None] = File(None)):
    submit_text = await prepare_text_from_inputs(text, file, max_length=50000)
    remote_url = get_remote_url()
    headers = get_auth_headers()
    result = forward_post_json(
        remote_url,
        data={"text": submit_text},
        headers=headers,
        context="Analyze",
    )
    return JSONResponse(result)


@app.post("/ocr")
async def ocr(image_url: Union[str, None] = Form(None), image: Union[UploadFile, None] = File(None), language: str = Form("en")):
    files = await build_image_files(image, image_url)
    remote_url = get_ocr_url()
    headers = get_auth_headers()
    result = forward_post_json(
        remote_url,
        data={"language": language},
        files=files,
        headers=headers,
        context="OCR",
    )
    return JSONResponse(result)


@app.post("/audio-transcribe")
async def audio_transcribe(audio: Union[UploadFile, None] = File(None), audio_url: Union[str, None] = Form(None), return_timestamps: bool = Form(False)):
    files, data = await build_audio_payload(audio, audio_url, return_timestamps)
    remote_url = get_audio_text_url()
    headers = get_auth_headers()
    result = forward_post_json(
        remote_url,
        data=data,
        files=files,
        headers=headers,
        context="Audio transcription",
    )
    return JSONResponse(result)


@app.post("/generate-image")
async def generate_image(
    prompt: str = Form(...),
    style_index: int = Form(0),
    aspect_ratio: str = Form("1:1"),
    num_images: int = Form(1),
    num_inference_steps: int = Form(4),
    enable_safety_checker: bool = Form(True),
    enable_prompt_optimizer: bool = Form(True),
    negative_prompt: Union[str, None] = Form("")
):
    try:
        result = image_generator.generate_images(
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


@app.get("/download-image")
async def download_image(url: str, filename: str = "generated_image.png"):
    if not url.startswith("https://image.pollinations.ai/"):
        raise HTTPException(status_code=400, detail="Invalid image URL")

    try:
        response = requests.get(url, timeout=30, stream=True)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "image/png")
        if not filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            if "jpeg" in content_type:
                filename += ".jpg"
            elif "webp" in content_type:
                filename += ".webp"
            else:
                filename += ".png"

        return StreamingResponse(
            (chunk for chunk in response.iter_content(chunk_size=8192)),
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename={filename}", "Cache-Control": "no-cache"}
        )
    except RequestException as req_err:
        raise HTTPException(status_code=502, detail=f"Image download failed: {str(req_err)}") from req_err


@app.get("/healthz")
async def healthz():
    return {"ok": True}
