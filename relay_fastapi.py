import os
import io
import json
import time
from typing import Optional

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import requests

# Import our image generation module
from image_generation import image_generator

HF_INFERENCE_URL_ENV = "HF_INFERENCE_URL"
HF_OCR_URL_ENV = "HF_OCR_URL"
HF_AUDIO_TEXT_URL_ENV = "HF_AUDIO_TEXT_URL"
HF_QWEN_IMAGE_URL_ENV = "HF_QWEN_IMAGE_URL"
DEFAULT_TIMEOUT_SECONDS = 120


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
            "No OCR URL configured. Set HF_OCR_URL to your Hugging Face Space OCR endpoint (e.g. https://<space>.hf.space/extract)."
        )
    return remote


def get_audio_text_url() -> str:
    remote = os.getenv(HF_AUDIO_TEXT_URL_ENV, "").strip()
    if not remote:
        raise RuntimeError(
            "No AUDIO URL configured. Set HF_AUDIO_TEXT_URL to your Hugging Face Space AUDIO endpoint (e.g. https://<space>.hf.space/extract)."
        )
    return remote


def get_qwen_image_url() -> str:
    remote = os.getenv(HF_QWEN_IMAGE_URL_ENV, "").strip()
    if not remote:
        raise RuntimeError(
            "No Qwen Image URL configured. Set HF_QWEN_IMAGE_URL to your Hugging Face Space Qwen Image endpoint (e.g. https://<space>.hf.space/gradio_api/call/infer)."
        )
    return remote


app = FastAPI(title="TextSense Relay (FastAPI)")

# Static and templates to preserve the existing UI
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/favicon.ico")
async def favicon():
    return FileResponse("static/favicon.ico")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    context = {
        "request": request,
        "contact_email": os.getenv("CONTACT_EMAIL", "textsense2@gmail.com"),
    }
    return templates.TemplateResponse("index.html", context)


@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    context = {
        "request": request,
        "contact_email": os.getenv("CONTACT_EMAIL", "textsense2@gmail.com"),
    }
    return templates.TemplateResponse("about.html", context)


@app.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    context = {
        "request": request,
        "contact_email": os.getenv("CONTACT_EMAIL", "textsense2@gmail.com"),
    }
    return templates.TemplateResponse("privacy.html", context)


@app.get("/terms", response_class=HTMLResponse)
async def terms(request: Request):
    context = {
        "request": request,
        "contact_email": os.getenv("CONTACT_EMAIL", "support@example.com"),
    }
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
    context = {
        "request": request,
        "contact_email": os.getenv("CONTACT_EMAIL", "textsense2@gmail.com"),
    }
    return templates.TemplateResponse("ocr.html", context)


@app.get("/audio-text", response_class=HTMLResponse)
async def audio_text_page(request: Request):
    context = {
        "request": request,
        "contact_email": os.getenv("CONTACT_EMAIL", "textsense2@gmail.com"),
    }
    return templates.TemplateResponse("audio-text.html", context)


@app.get("/generate-image-page", response_class=HTMLResponse)
async def generate_image_page(request: Request):
    context = {
        "request": request,
        "contact_email": os.getenv("CONTACT_EMAIL", "textsense2@gmail.com"),
    }
    return templates.TemplateResponse("generate-image.html", context)


@app.post("/contact")
async def submit_contact(request: Request):
    form = await request.form()
    name = (form.get("name") or "").strip()
    email = (form.get("email") or "").strip()
    message = (form.get("message") or "").strip()
    token = (form.get("g-recaptcha-response") or "").strip()

    # Optional reCAPTCHA v3 verification
    secret = os.getenv("RECAPTCHA_SECRET_KEY", "").strip()
    if secret:
        import requests as _r
        try:
            verify = _r.post("https://www.google.com/recaptcha/api/siteverify", data={
                "secret": secret,
                "response": token,
            }, timeout=10)
            
            if verify.status_code == 200:
                result = verify.json()
                if result.get("success"):
                    # reCAPTCHA v3 returns a score from 0.0 to 1.0
                    score = result.get("score", 0.0)
                    threshold = float(os.getenv("RECAPTCHA_THRESHOLD", "0.5"))
                    
                    if score < threshold:
                        return JSONResponse({
                            "ok": False, 
                            "error": f"reCAPTCHA score too low ({score:.2f}). Please try again."
                        }, status_code=400)
                else:
                    return JSONResponse({
                        "ok": False, 
                        "error": "reCAPTCHA verification failed"
                    }, status_code=400)
            else:
                return JSONResponse({
                    "ok": False, 
                    "error": "reCAPTCHA verification error"
                }, status_code=400)
        except Exception:
            return JSONResponse({
                "ok": False, 
                "error": "reCAPTCHA network error"
            }, status_code=400)
    # For now, just acknowledge receipt. Integrate email service later.
    return JSONResponse({
        "ok": True,
        "received": {"name": name, "email": email, "message": message}
    })


@app.get("/cookies", response_class=HTMLResponse)
async def cookies(request: Request):
    context = {
        "request": request,
        "contact_email": os.getenv("CONTACT_EMAIL", "textsense2@gmail.com"),
    }
    return templates.TemplateResponse("cookies.html", context)


@app.get("/ads.txt", response_class=PlainTextResponse)
async def ads_txt():
    pub_id = os.getenv("ADSENSE_PUB_ID", "pub-2409576003450898").strip()
    # IAB ads.txt entry for Google AdSense
    return f"google.com, {pub_id}, DIRECT, f08c47fec0942fa0"


@app.post("/analyze")
async def analyze(text: Optional[str] = Form(None), file: Optional[UploadFile] = File(None)):
    # Validate input similar to the original Flask endpoint
    if not text and not file:
        return JSONResponse({"error": "No text or file provided."}, status_code=400)

    # If file provided, read content; else use text
    submit_text: Optional[str] = None
    if file is not None and file.filename:
        try:
            raw_bytes = await file.read()
            try:
                submit_text = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                submit_text = raw_bytes.decode("latin-1", errors="ignore")
        except Exception:
            return JSONResponse({"error": "Could not read file content. The file might be corrupted or in an unsupported format."}, status_code=400)
    else:
        submit_text = (text or "").strip()

    if not submit_text:
        return JSONResponse({"error": "No text or file provided."}, status_code=400)
    if len(submit_text) > 50000:
        return JSONResponse({"error": "Text exceeds the 50,000 character limit."}, status_code=400)

    # Proxy to HF Space
    try:
        remote_url = get_remote_url()
        # Send as form-data to stay compatible with either file or text on remote
        form = {"text": submit_text}
        headers = {}

        # Optional: support private endpoints via HF_API_KEY
        api_key = os.getenv("HF_API_KEY", "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        resp = requests.post(
            remote_url,
            data=form,
            headers=headers,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        if resp.status_code != 200:
            # Attempt to surface remote error
            try:
                payload = resp.json()
            except Exception:
                payload = {"error": f"Upstream error (status {resp.status_code})."}
            raise HTTPException(status_code=resp.status_code, detail=payload.get("error") or payload)

        return JSONResponse(resp.json())
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse({"error": f"Relay error: {str(e)}"}, status_code=500)


@app.post("/ocr")
async def ocr(
    image_url: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
):
    if not image_url and (image is None or not image.filename):
        return JSONResponse({"error": "No image provided. Provide 'image' file or 'image_url'."}, status_code=400)

    try:
        remote_url = get_ocr_url()
        headers = {}
        api_key = os.getenv("HF_API_KEY", "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        files = None

        if image is not None and image.filename:
            # Forward uploaded file directly to the Space as field name 'image'
            content = await image.read()
            filename = image.filename
            mime = image.content_type or "application/octet-stream"
            files = {"image": (filename, content, mime)}
        elif image_url:
            # Workaround: fetch URL here (Render has egress), then send bytes to Space
            url = image_url.strip()
            if not url:
                return JSONResponse({"error": "image_url is empty"}, status_code=400)
            try:
                fetch_headers = {"User-Agent": "TextSense-Relay/1.0"}
                r = requests.get(url, timeout=30, headers=fetch_headers)
                r.raise_for_status()
            except requests.exceptions.RequestException as re:
                return JSONResponse({"error": f"Failed to fetch image URL: {str(re)}"}, status_code=400)

            mime = r.headers.get("content-type", "application/octet-stream").split(";")[0].strip()
            # Derive a filename
            name = url.split("?")[0].rstrip("/").split("/")[-1] or "remote.jpg"
            files = {"image": (name, r.content, mime)}

        resp = requests.post(
            remote_url,
            files=files,
            headers=headers,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        if resp.status_code != 200:
            try:
                payload = resp.json()
            except Exception:
                payload = {"error": f"Upstream error (status {resp.status_code})."}
            raise HTTPException(status_code=resp.status_code, detail=payload.get("error") or payload)

        return JSONResponse(resp.json())
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse({"error": f"Relay error: {str(e)}"}, status_code=500)


@app.post("/audio-transcribe")
async def audio_transcribe(
    audio: Optional[UploadFile] = File(None),
    audio_url: Optional[str] = Form(None),
    return_timestamps: bool = Form(False),
):
    if not audio_url and (audio is None or not audio.filename):
        return JSONResponse({"error": "No audio provided. Provide 'audio' file or 'audio_url'."}, status_code=400)

    try:
        remote_url = get_audio_text_url()
        headers = {}
        api_key = os.getenv("HF_API_KEY", "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        # Prepare the request
        data = {"return_timestamps": str(return_timestamps).lower()}
        files = None

        if audio is not None and audio.filename:
            # Forward uploaded audio file
            content = await audio.read()
            filename = audio.filename
            mime = audio.content_type or "audio/mpeg"
            files = {"audio": (filename, content, mime)}
        elif audio_url:
            # Forward audio URL
            data["audio_url"] = audio_url.strip()

        resp = requests.post(
            remote_url,
            data=data,
            files=files,
            headers=headers,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        if resp.status_code != 200:
            try:
                payload = resp.json()
            except Exception:
                payload = {"error": f"Upstream error (status {resp.status_code})."}
            raise HTTPException(status_code=resp.status_code, detail=payload.get("error") or payload)

        return JSONResponse(resp.json())
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse({"error": f"Relay error: {str(e)}"}, status_code=500)


@app.post("/generate-image")
async def generate_image(
    prompt: str = Form(...),
    style_index: int = Form(0),
    aspect_ratio: str = Form("1:1"),
    num_images: int = Form(1),
    num_inference_steps: int = Form(4),
    enable_safety_checker: bool = Form(True),
    enable_prompt_optimizer: bool = Form(True),
    negative_prompt: Optional[str] = Form("")
):
    """Generate images using Pollinations Flux with AI prompt enhancement.
    
    The endpoint maintains the same form fields for compatibility with existing frontend,
    but maps them to Pollinations parameters. Generated images have no watermarks.
    """
    try:
        # Use the image generation module
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
        
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": f"Image generation failed: {str(e)}"}, status_code=500)


@app.post("/test-qwen-api")
async def test_qwen_api():
    """Test endpoint to debug Qwen Image API response format."""
    try:
        remote_url = get_qwen_image_url()
        headers = {"Content-Type": "application/json"}
        
        # Simple test payload
        payload = {
            "data": [
                "test image",  # prompt
                "",            # negative_prompt
                True,          # enable_safety_checker
                "1:1",         # aspect_ratio
                1,             # num_images
                4,             # num_inference_steps
                True           # additional parameter
            ]
        }
        
        resp = requests.post(remote_url, json=payload, headers=headers, timeout=30)
        
        return JSONResponse({
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
            "response": resp.json() if resp.status_code == 200 else resp.text,
            "url": remote_url
        })
        
    except Exception as e:
        return JSONResponse({"error": f"Test failed: {str(e)}"}, status_code=500)


@app.get("/healthz")
async def healthz():
    return {"ok": True}
    