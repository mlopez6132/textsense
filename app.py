from flask import Flask, render_template, request, jsonify
import torch
import torch.nn as nn
from transformers import AutoTokenizer, AutoConfig, AutoModel, PreTrainedModel
import re
import os
from werkzeug.utils import secure_filename
from typing import List, Tuple

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Global variables for model, tokenizer, and nlp
model = None
tokenizer = None
device = None
nlp = None # spaCy model instance

# Inference tuning
DEFAULT_MAX_LEN = 256
DEFAULT_BATCH_SIZE = 16

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
        loss = None
        if labels is not None:
            loss_fct = nn.BCEWithLogitsLoss()
            loss = loss_fct(logits.view(-1), labels.float())
        output = {"logits": logits}
        if loss is not None:
            output["loss"] = loss
        return output

def load_models_and_tokenizer():
    """Load the AI detection model, tokenizer, and spaCy model"""
    global model, tokenizer, device, nlp
    
    # Load Hugging Face model
    if model is None:
        model_directory = "desklib/ai-text-detector-v1.01"
        try:
            print(f"Loading AI model: {model_directory}")
            tokenizer = AutoTokenizer.from_pretrained(model_directory)
            model = DesklibAIDetectionModel.from_pretrained(model_directory)
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            model.to(device)
            model.eval()
            print(f"✅ AI Model loaded successfully on {device}")
            # Warmup a tiny forward to avoid first-request latency
            try:
                with torch.no_grad():
                    warm_inputs = tokenizer(
                        "Hello.", truncation=True, max_length=8, return_tensors='pt'
                    )
                    warm_input_ids = warm_inputs['input_ids'].to(device)
                    warm_attention_mask = warm_inputs['attention_mask'].to(device)
                    if device.type == 'cuda':
                        with torch.cuda.amp.autocast():
                            _ = model(input_ids=warm_input_ids, attention_mask=warm_attention_mask)
                    else:
                        _ = model(input_ids=warm_input_ids, attention_mask=warm_attention_mask)
            except Exception as warm_e:
                print(f"⚠️ Warmup forward failed (continuing): {warm_e}")
        except Exception as e:
            print(f"❌ Error loading Hugging Face model: {e}")
            return False

    # Load spaCy model
    if nlp is None:
        try:
            import spacy
            print("Loading spaCy model...")
            nlp = spacy.load("en_core_web_sm")
            print("✅ spaCy model loaded successfully.")
        except ImportError:
            print("⚠️ spaCy not installed. Segmentation will use a simpler method.")
            nlp = 'failed' # Mark as failed to avoid retrying
        except OSError:
            print("⚠️ spaCy model 'en_core_web_sm' not found. Please run 'python -m spacy download en_core_web_sm'.")
            print("   Falling back to simple sentence splitting.")
            nlp = 'failed'

    return True

def predict_single_text(text, max_len=DEFAULT_MAX_LEN, threshold=0.5):
    """Predict if a single text is AI-generated"""
    if model is None or tokenizer is None:
        if not load_models_and_tokenizer():
            return 0.0, 0
    
    encoded = tokenizer(
        text,
        padding=True,
        truncation=True,
        max_length=max_len,
        return_tensors='pt'
    )
    input_ids = encoded['input_ids'].to(device)
    attention_mask = encoded['attention_mask'].to(device)

    with torch.no_grad():
        if device.type == 'cuda':
            with torch.cuda.amp.autocast():
                outputs = model(input_ids=input_ids, attention_mask=attention_mask)
        else:
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
        logits = outputs["logits"]
        probability = torch.sigmoid(logits).item()

    label = 1 if probability >= threshold else 0
    return probability, label


def predict_texts_batch(
    texts: List[str],
    max_len: int = DEFAULT_MAX_LEN,
    threshold: float = 0.5,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> List[Tuple[float, int]]:
    """Predict a list of texts using efficient batched inference.

    Returns list of (probability, label) tuples aligned with input order.
    """
    if model is None or tokenizer is None:
        if not load_models_and_tokenizer():
            return [(0.0, 0) for _ in texts]

    results: List[Tuple[float, int]] = []
    total = len(texts)
    if total == 0:
        return results

    with torch.no_grad():
        for start_idx in range(0, total, batch_size):
            end_idx = min(start_idx + batch_size, total)
            batch_texts = texts[start_idx:end_idx]
            encoded = tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=max_len,
                return_tensors='pt'
            )
            input_ids = encoded['input_ids'].to(device)
            attention_mask = encoded['attention_mask'].to(device)

            if device.type == 'cuda':
                with torch.cuda.amp.autocast():
                    outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            else:
                outputs = model(input_ids=input_ids, attention_mask=attention_mask)

            logits = outputs["logits"].squeeze(-1)
            probs = torch.sigmoid(logits).detach().cpu().tolist()

            # Ensure list
            if isinstance(probs, float):
                probs = [probs]

            for prob in probs:
                label = 1 if prob >= threshold else 0
                results.append((float(prob), label))

    return results

def analyze_text_segments(text):
    """
    Analyze text by breaking it into sentences.
    This function now pre-processes the text to improve segmentation accuracy.
    """
    global nlp
    
    cleaned_text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)
    cleaned_text = re.sub(r' +', ' ', cleaned_text)
    cleaned_text = cleaned_text.strip()

    if nlp is None:
        load_models_and_tokenizer()

    if nlp != 'failed':
        doc = nlp(cleaned_text)
        sentences = list(doc.sents)

        # Collect spans and texts first
        span_data = []  # List of (text, start, end)
        for sentence in sentences:
            start = sentence.start_char
            end = sentence.end_char
            while start < end and cleaned_text[start].isspace():
                start += 1
            while end > start and cleaned_text[end - 1].isspace():
                end -= 1
            sentence_text = cleaned_text[start:end]
            if not sentence_text:
                continue
            span_data.append((sentence_text, start, end))

        # Batched prediction
        probs_labels = predict_texts_batch([t for (t, _, _) in span_data])

        segments = []
        for (sentence_text, start, end), (prob, label) in zip(span_data, probs_labels):
            segments.append({
                'text': sentence_text,
                'start': start,
                'end': end,
                'probability': prob,
                'is_ai': label == 1
            })

        return segments, cleaned_text
        
    else:
        segments = analyze_text_simple_sentences(cleaned_text)
        return segments, cleaned_text


def analyze_text_simple_sentences(text):
    """Fallback method using simple sentence splitting on the cleaned text."""
    sentence_pattern = r'[^.!?]*[.!?]+(?:\s+|$)'
    matches = list(re.finditer(sentence_pattern, text))

    span_data = []  # List of (text, start, end)
    last_end = 0
    for match in matches:
        sentence_text = match.group().strip()
        if not sentence_text:
            last_end = match.end()
            continue

        # Compute precise trimmed indices relative to the full text
        raw_start = match.start()
        raw_end = match.end()
        trim_left = 0
        trim_right = 0
        while raw_start + trim_left < raw_end and text[raw_start + trim_left].isspace():
            trim_left += 1
        while raw_end - 1 - trim_right >= raw_start + trim_left and text[raw_end - 1 - trim_right].isspace():
            trim_right += 1
        sentence_start = raw_start + trim_left
        sentence_end = raw_end - trim_right

        span_data.append((sentence_text, sentence_start, sentence_end))
        last_end = sentence_end

    # Add trailing text without terminal punctuation as a final segment
    if last_end < len(text):
        trailing_start = last_end
        while trailing_start < len(text) and text[trailing_start].isspace():
            trailing_start += 1
        trailing_end = len(text)
        while trailing_end > trailing_start and text[trailing_end - 1].isspace():
            trailing_end -= 1
        trailing_text = text[trailing_start:trailing_end]
        if trailing_text:
            span_data.append((trailing_text, trailing_start, trailing_end))

    # Batched prediction over all spans
    probs_labels = predict_texts_batch([t for (t, _, _) in span_data])

    segments = []
    for (sentence_text, start, end), (prob, label) in zip(span_data, probs_labels):
        segments.append({
            'text': sentence_text,
            'start': start,
            'end': end,
            'probability': prob,
            'is_ai': label == 1
        })

    return segments

def extract_text_from_file(file_path):
    """Extract text from uploaded file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            with open(file_path, 'r', encoding='latin-1') as f:
                return f.read()
        except:
            return None
    except Exception as e:
        print(f"Error reading file: {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        text_to_process = ""
        if 'file' in request.files and request.files['file'].filename != '':
            file = request.files['file']
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            text_to_process = extract_text_from_file(file_path)
            os.remove(file_path)

            if text_to_process is None:
                return jsonify({'error': 'Could not read file content. The file might be corrupted or in an unsupported format.'}), 400
        else:
            text_to_process = request.form.get('text', '').strip()
        
        if not text_to_process:
            return jsonify({'error': 'No text or file provided.'}), 400
        # Enforce 50,000 character limit server-side
        if len(text_to_process) > 50000:
            return jsonify({'error': 'Text exceeds the 50,000 character limit.'}), 400
        
        segments, cleaned_text = analyze_text_segments(text_to_process)
        
        total_length = len(cleaned_text)
        
        ai_segments = [s for s in segments if s['is_ai']]
        
        ai_char_count = sum(len(s['text']) for s in ai_segments)
        
        ai_percentage = (ai_char_count / total_length) * 100 if total_length > 0 else 0
        human_percentage = 100 - ai_percentage
        
        avg_ai_prob = sum(s['probability'] for s in segments) / len(segments) if segments else 0
        
        result = {
            'cleaned_text': cleaned_text,
            'segments': segments,
            'statistics': {
                'total_length': total_length,
                'ai_percentage': round(ai_percentage, 2),
                'human_percentage': round(human_percentage, 2),
                'avg_ai_probability': round(avg_ai_prob * 100, 2),
                'total_segments': len(segments),
                'ai_segments_count': len(ai_segments),
            },
            'overall_assessment': 'Likely AI-Generated' if avg_ai_prob > 0.5 else 'Likely Human-Written'
        }
        
        return jsonify(result)
        
    except Exception as e:
        print(f"An error occurred in /analyze: {e}")
        return jsonify({'error': 'An internal server error occurred. Please try again.'}), 500

if __name__ == '__main__':
    load_models_and_tokenizer()
    app.run(debug=True, host='0.0.0.0', port=5000)
