import os
import io
from typing import Optional

import numpy as np
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from PIL import Image
import requests
from paddleocr import PaddleOCR


OCR_LANG = os.getenv("OCR_LANG", "en")
PPOCR_HOME = os.getenv("PPOCR_HOME", "/tmp/.paddleocr")
os.makedirs(PPOCR_HOME, exist_ok=True)
os.environ.setdefault("PPOCR_HOME", PPOCR_HOME)

# PP-OCRv5 model configuration
USE_PP_OCRV5 = os.getenv("USE_PP_OCRV5", "true").lower() == "true"
ACTIVE_OCR_VERSION = "unknown"  # Will be set during OCR initialization


def load_ocr():
    global ACTIVE_OCR_VERSION
    try:
        if USE_PP_OCRV5:
            # Use PP-OCRv5 models as specified in the official documentation
            ocr = PaddleOCR(
                use_angle_cls=True,
                lang=OCR_LANG,
                text_detection_model_name="PP-OCRv5_server_det",
                text_recognition_model_name="PP-OCRv5_server_rec",
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=True,
                show_log=False
            )
            ACTIVE_OCR_VERSION = "PP-OCRv5"
        else:
            # Fallback to default models
            ocr = PaddleOCR(use_angle_cls=True, lang=OCR_LANG, show_log=False)
            ACTIVE_OCR_VERSION = "default"
    except Exception as e:
        # Final fallback for any initialization errors
        print(f"PP-OCRv5 initialization failed: {e}. Falling back to default models.")
        ocr = PaddleOCR(use_angle_cls=True, lang=OCR_LANG, show_log=False)
        ACTIVE_OCR_VERSION = "default-fallback"
    return ocr


ocr = load_ocr()

app = FastAPI(title=f"TextSense OCR (PaddleOCR {ACTIVE_OCR_VERSION})")


def read_image_from_upload(upload: UploadFile) -> Image.Image:
    bytes_data = upload.file.read()
    img = Image.open(io.BytesIO(bytes_data))  # type: ignore
    return img.convert("RGB")


def read_image_from_url(url: str) -> Image.Image:
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    img = Image.open(io.BytesIO(resp.content))  # type: ignore
    return img.convert("RGB")


@app.post("/extract")
async def extract(
    image: Optional[UploadFile] = File(None),
    image_url: Optional[str] = Form(None),
):
    try:
        img: Optional[Image.Image] = None
        if image is not None and image.filename:
            # Starlette's UploadFile is async; ensure we read content properly
            content = await image.read()
            img = Image.open(io.BytesIO(content)).convert("RGB")  # type: ignore
        elif image_url:
            url = image_url.strip()
            if not url:
                return JSONResponse({"error": "image_url is empty"}, status_code=400)
            try:
                r = requests.get(url, timeout=20, headers={'User-Agent': 'TextSense-OCR/1.0'})
                r.raise_for_status()
                img = Image.open(io.BytesIO(r.content)).convert("RGB")  # type: ignore
            except requests.exceptions.ConnectionError as ce:
                return JSONResponse({
                    "error": f"Network connection failed: {str(ce)}. The Space may have limited network access."
                }, status_code=400)
            except requests.exceptions.Timeout:
                return JSONResponse({"error": "Request timed out while fetching image"}, status_code=400)
        else:
            return JSONResponse({"error": "No image provided. Provide 'image' file or 'image_url'."}, status_code=400)
        # Run PaddleOCR on the image
        np_img = np.array(img)
        result = ocr.ocr(np_img, cls=True)
        lines = []
        if result and isinstance(result, list):
            # result is a list with one item per image; we process the first (single image)
            for line in result[0] or []:
                try:
                    text = line[1][0]
                    score = float(line[1][1])
                    if text and score >= 0.5:
                        lines.append(text)
                except Exception:
                    continue
        extracted = "\n".join(lines).strip()
        return JSONResponse({"text": extracted})
    except requests.HTTPError as he:
        return JSONResponse({"error": f"Failed to fetch image: {str(he)}"}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": f"OCR error: {str(e)}"}, status_code=500)


@app.get("/healthz")
async def healthz():
    return {"ok": True, "lang": OCR_LANG, "ocr_version": ACTIVE_OCR_VERSION}
