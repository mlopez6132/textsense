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
    negative_prompt: Optional[str] = Form("")
):
    """Generate images using Qwen Image API via Hugging Face Space.
    Matches Qwen-Image-Fast input schema.
    """
    if not prompt or not prompt.strip():
        return JSONResponse({"error": "prompt is required"}, status_code=400)
    
    if num_images < 1 or num_images > 4:
        return JSONResponse({"error": "num_images must be between 1 and 4"}, status_code=400)
    if num_inference_steps < 1 or num_inference_steps > 50:
        return JSONResponse({"error": "num_inference_steps must be between 1 and 50"}, status_code=400)

    try:
        remote_url = get_qwen_image_url()
        headers = {"Content-Type": "application/json"}
        api_key = os.getenv("HF_API_KEY", "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        # Qwen-Image-Fast payload format:
        # [prompt: str, style_index: int, enable_safety_checker: bool, aspect_ratio: str, num_images: int, num_steps: int, extra_flag: bool]
        payload = {
            "data": [
                prompt.strip(),
                int(style_index),
                bool(enable_safety_checker),
                aspect_ratio,
                int(num_images),
                int(num_inference_steps),
                True
            ]
        }

        resp = requests.post(remote_url, json=payload, headers=headers, timeout=DEFAULT_TIMEOUT_SECONDS)
        if resp.status_code != 200:
            try:
                error_data = resp.json()
                error_msg = error_data.get("error", f"Upstream error (status {resp.status_code})")
            except Exception:
                error_msg = f"Upstream error (status {resp.status_code})"
            raise HTTPException(status_code=resp.status_code, detail=error_msg)

        # Extract event_id
        try:
            response_data = resp.json()
            event_id = None
            if isinstance(response_data, dict) and "event_id" in response_data:
                event_id = response_data["event_id"]
            elif isinstance(response_data, dict) and "data" in response_data:
                data = response_data["data"]
                if isinstance(data, list) and data and isinstance(data[0], dict):
                    event_id = data[0].get("event_id")
            elif isinstance(response_data, str):
                event_id = response_data
            elif isinstance(response_data, list) and response_data:
                first = response_data[0]
                if isinstance(first, dict):
                    event_id = first.get("event_id")
                elif isinstance(first, str):
                    event_id = first
            if not event_id:
                return JSONResponse({"error": "No event ID received", "response": response_data}, status_code=500)
        except Exception as e:
            return JSONResponse({"error": f"Failed to parse initial response: {str(e)}", "raw": resp.text[:1000]}, status_code=500)

        # Poll SSE at .../gradio_api/call/infer/{event_id}
        try:
            result_url = f"{remote_url.rstrip('/')}/{event_id}"
            sse_headers = dict(headers)
            sse_headers["Accept"] = "text/event-stream"

            max_attempts = 30
            attempt = 0
            while attempt < max_attempts:
                try:
                    result_resp = requests.get(
                        result_url,
                        headers={"Accept": "text/event-stream"},
                        timeout=(10, 60),
                        stream=True
                    )
                    
                    print(f"DEBUG: Attempt {attempt + 1}, Status: {result_resp.status_code}")
                    
                    if result_resp.status_code == 200:
                        # Handle streaming response
                        response_text = ""
                        current_event = None
                        for raw_line in result_resp.iter_lines(decode_unicode=True):
                            if not raw_line:
                                continue
                            line = raw_line.strip()
                            response_text += line + "\n"

                            # Track event type (e.g., heartbeat, complete, error)
                            if line.startswith("event: "):
                                current_event = line.split(": ", 1)[1].strip()
                                print(f"DEBUG: Received event: {current_event}")
                                continue

                            # Look for data lines in Server-Sent Events format
                            if line.startswith("data: "):
                                data_part = line[6:]
                                try:
                                    parsed = json.loads(data_part)
                                except json.JSONDecodeError:
                                    if data_part.startswith('"') and data_part.endswith('"'):
                                        parsed = data_part.strip('"')
                                    else:
                                        continue

                                # If server indicates an error via SSE
                                if isinstance(parsed, str) and parsed.startswith("404"):
                                    return JSONResponse({"error": parsed, "polling_url": result_url}, status_code=502)

                                # On complete event, treat this as final payload
                                if current_event == "complete":
                                    if isinstance(parsed, list):
                                        image_urls = []
                                        files_meta = []
                                        for item in parsed:
                                            if isinstance(item, dict) and item.get("url"):
                                                image_urls.append(item["url"])
                                                files_meta.append(item)
                                        if image_urls:
                                            return JSONResponse({"images": image_urls, "files": files_meta})
                                    elif isinstance(parsed, dict):
                                        if parsed.get("data") or parsed.get("images"):
                                            return JSONResponse(parsed)
                                    # If complete without recognizable payload, keep listening briefly
                                    continue

                                # Non-complete data that already contains useful payload
                                if isinstance(parsed, dict) and (parsed.get("data") or parsed.get("images")):
                                    return JSONResponse(parsed)

                        # If stream ended without data, retry briefly
                        attempt += 1
                        time.sleep(1)
                        continue
                    elif result_resp.status_code == 202:
                        attempt += 1
                        time.sleep(1)
                        continue
                    else:
                        return JSONResponse({"error": f"Fetch results failed: {result_resp.status_code}", "text": result_resp.text[:500]}, status_code=result_resp.status_code)
                except requests.exceptions.Timeout:
                    attempt += 1
                    time.sleep(1)
                    continue
            return JSONResponse({"error": "Timeout waiting for results", "event_id": event_id}, status_code=408)
        except Exception as e:
            return JSONResponse({"error": f"Failed to poll results: {str(e)}", "event_id": event_id}, status_code=500)

    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse({"error": f"Image generation error: {str(e)}"}, status_code=500)


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
    