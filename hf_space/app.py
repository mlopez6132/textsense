import os
import re
from typing import List, Tuple

import torch
import torch.nn as nn
from transformers import AutoTokenizer, AutoConfig, AutoModel, PreTrainedModel
from fastapi import FastAPI, Form
from fastapi.responses import JSONResponse


MODEL_ID = os.getenv("MODEL_ID", "desklib/ai-text-detector-v1.01")
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
DEFAULT_MAX_LEN = int(os.getenv("MAX_LEN", "256"))
DEFAULT_BATCH_SIZE = int(os.getenv("BATCH_SIZE", "16"))


class DesklibAIDetectionModel(PreTrainedModel):
    config_class = AutoConfig

    def __init__(self, config):
        super().__init__(config)
        self.model = AutoModel.from_config(config)
        self.classifier = nn.Linear(config.hidden_size, 1)
        self.init_weights()

    def forward(self, input_ids, attention_mask=None, labels=None):
        outputs = self.model(input_ids, attention_mask=attention_mask)
        last_hidden_state = outputs[0]
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()
        sum_embeddings = torch.sum(last_hidden_state * input_mask_expanded, dim=1)
        sum_mask = torch.clamp(input_mask_expanded.sum(dim=1), min=1e-9)
        pooled_output = sum_embeddings / sum_mask
        logits = self.classifier(pooled_output)
        return {"logits": logits}


def load_model():
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model = DesklibAIDetectionModel.from_pretrained(MODEL_ID)
    model.to(DEVICE)
    model.eval()

    # Warmup
    with torch.no_grad():
        sample = tokenizer("Hello.", truncation=True, max_length=8, return_tensors="pt")
        input_ids = sample["input_ids"].to(DEVICE)
        attention_mask = sample["attention_mask"].to(DEVICE)
        if DEVICE.type == "cuda":
            with torch.cuda.amp.autocast():
                _ = model(input_ids=input_ids, attention_mask=attention_mask)
        else:
            _ = model(input_ids=input_ids, attention_mask=attention_mask)

    return tokenizer, model


tokenizer, model = load_model()

app = FastAPI(title="TextSense Inference (GPU)")


def simple_sentence_split(text: str) -> List[Tuple[str, int, int]]:
    pattern = r"[^.!?]*[.!?]+(?:\s+|$)"
    matches = list(re.finditer(pattern, text))
    spans: List[Tuple[str, int, int]] = []
    last_end = 0
    for m in matches:
        seg = m.group().strip()
        if not seg:
            last_end = m.end()
            continue
        raw_start = m.start()
        raw_end = m.end()
        trim_left = 0
        trim_right = 0
        while raw_start + trim_left < raw_end and text[raw_start + trim_left].isspace():
            trim_left += 1
        while raw_end - 1 - trim_right >= raw_start + trim_left and text[raw_end - 1 - trim_right].isspace():
            trim_right += 1
        sentence_start = raw_start + trim_left
        sentence_end = raw_end - trim_right
        spans.append((seg, sentence_start, sentence_end))
        last_end = sentence_end
    if last_end < len(text):
        trailing = text[last_end:].strip()
        if trailing:
            spans.append((trailing, last_end, len(text)))
    return spans


def predict_texts_batch(texts: List[str], max_len: int = DEFAULT_MAX_LEN, batch_size: int = DEFAULT_BATCH_SIZE):
    results: List[Tuple[float, int]] = []
    total = len(texts)
    if total == 0:
        return results
    with torch.no_grad():
        for start_idx in range(0, total, batch_size):
            end_idx = min(start_idx + batch_size, total)
            batch_texts = texts[start_idx:end_idx]
            enc = tokenizer(batch_texts, padding=True, truncation=True, max_length=max_len, return_tensors="pt")
            input_ids = enc["input_ids"].to(DEVICE)
            attention_mask = enc["attention_mask"].to(DEVICE)
            if DEVICE.type == "cuda":
                with torch.cuda.amp.autocast():
                    outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            else:
                outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            logits = outputs["logits"].squeeze(-1)
            probs = torch.sigmoid(logits).detach().cpu().tolist()
            if isinstance(probs, float):
                probs = [probs]
            for p in probs:
                results.append((float(p), 1 if p >= 0.5 else 0))
    return results


@app.post("/analyze")
async def analyze(text: str = Form(...)):
    cleaned = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    cleaned = re.sub(r" +", " ", cleaned).strip()
    spans = simple_sentence_split(cleaned)
    probs_labels = predict_texts_batch([t for (t, _, _) in spans])
    segments = []
    for (seg_text, start, end), (prob, label) in zip(spans, probs_labels):
        segments.append({
            "text": seg_text,
            "start": start,
            "end": end,
            "probability": prob,
            "is_ai": label == 1,
        })
    total_length = len(cleaned)
    ai_segments = [s for s in segments if s["is_ai"]]
    ai_chars = sum(len(s["text"]) for s in ai_segments)
    ai_percentage = (ai_chars / total_length) * 100 if total_length > 0 else 0
    human_percentage = 100 - ai_percentage
    avg_ai_prob = sum(s["probability"] for s in segments) / len(segments) if segments else 0
    result = {
        "cleaned_text": cleaned,
        "segments": segments,
        "statistics": {
            "total_length": total_length,
            "ai_percentage": round(ai_percentage, 2),
            "human_percentage": round(human_percentage, 2),
            "avg_ai_probability": round(avg_ai_prob * 100, 2),
            "total_segments": len(segments),
            "ai_segments_count": len(ai_segments),
        },
        "overall_assessment": "Likely AI-Generated" if avg_ai_prob > 0.5 else "Likely Human-Written",
    }
    return JSONResponse(result)


@app.get("/healthz")
async def healthz():
    return {"ok": True, "device": str(DEVICE)}


