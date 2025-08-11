import os
import io
from typing import Optional

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import requests

HF_INFERENCE_URL_ENV = "HF_INFERENCE_URL"
HF_INFERENCE_URL_DEFAULT = "https://mlopez6132-textsense-inference.hf.space/analyze"
DEFAULT_TIMEOUT_SECONDS = 120


def get_remote_url() -> str:
    remote = os.getenv(HF_INFERENCE_URL_ENV, HF_INFERENCE_URL_DEFAULT).strip()
    if not remote:
        raise RuntimeError(
            "No remote inference URL configured. Set HF_INFERENCE_URL to your Hugging Face Space /analyze endpoint."
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


@app.get("/healthz")
async def healthz():
    return {"ok": True}
    