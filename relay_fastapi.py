import os
import io
from typing import Optional

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
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


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


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


