from flask import Flask, render_template, request, jsonify
import os
import random
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'demo-secret-key'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def mock_predict_single_text(text, max_len=768, threshold=0.5):
    """Mock prediction function for demo purposes"""
    # Generate a realistic probability based on text characteristics
    # This is just for demonstration - not real AI detection
    
    # Simple heuristics for demo
    text_lower = text.lower()
    
    # Factors that might indicate AI-generated text
    ai_indicators = [
        'artificial intelligence', 'machine learning', 'neural network',
        'algorithm', 'data science', 'automation', 'digital transformation',
        'blockchain', 'cloud computing', 'internet of things', 'iot',
        'big data', 'analytics', 'optimization', 'efficiency',
        'innovation', 'technology', 'digital', 'automated', 'systematic'
    ]
    
    # Factors that might indicate human-written text
    human_indicators = [
        'i think', 'in my opinion', 'personally', 'i believe',
        'however', 'nevertheless', 'on the other hand', 'but',
        'actually', 'really', 'very', 'quite', 'rather',
        'you know', 'i mean', 'like', 'sort of', 'kind of',
        'um', 'uh', 'well', 'so', 'basically'
    ]
    
    # Count indicators
    ai_score = sum(1 for indicator in ai_indicators if indicator in text_lower)
    human_score = sum(1 for indicator in human_indicators if indicator in text_lower)
    
    # Base probability
    base_prob = 0.3  # 30% base AI probability
    
    # Adjust based on indicators
    if ai_score > human_score:
        base_prob += 0.4
    elif human_score > ai_score:
        base_prob -= 0.2
    
    # Add some randomness for demo
    base_prob += random.uniform(-0.1, 0.1)
    
    # Clamp between 0 and 1
    probability = max(0.0, min(1.0, base_prob))
    
    label = 1 if probability >= threshold else 0
    return probability, label

def analyze_text_segments(text, segment_length=200, overlap=50):
    """Analyze text by breaking it into non-overlapping segments"""
    if len(text) <= segment_length:
        # For short texts, analyze the entire text
        prob, label = mock_predict_single_text(text)
        return [{
            'text': text,
            'start': 0,
            'end': len(text),
            'probability': prob,
            'is_ai': label == 1
        }]
    
    segments = []
    start = 0
    
    while start < len(text):
        end = min(start + segment_length, len(text))
        
        # Adjust end to not break words
        if end < len(text):
            # Find the last space before the end
            last_space = text.rfind(' ', start, end)
            if last_space > start:
                end = last_space
        
        # Extract the segment text
        segment_text = text[start:end].strip()
        
        if segment_text:
            prob, label = mock_predict_single_text(segment_text)
            segments.append({
                'text': segment_text,
                'start': start,
                'end': end,
                'probability': prob,
                'is_ai': label == 1
            })
        
        # Move to next segment (no overlap to avoid duplication)
        start = end
        if start >= len(text):
            break
    
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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        if 'file' in request.files:
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            text = extract_text_from_file(file_path)
            if text is None:
                return jsonify({'error': 'Could not read file content'}), 400
            
            # Clean up the file
            os.remove(file_path)
        else:
            text = request.form.get('text', '').strip()
            if not text:
                return jsonify({'error': 'No text provided'}), 400
        
        # Analyze the text
        segments = analyze_text_segments(text)
        
        # Calculate overall statistics
        total_length = len(text)
        ai_segments = [s for s in segments if s['is_ai']]
        human_segments = [s for s in segments if not s['is_ai']]
        
        # Calculate percentages based on character count
        ai_char_count = sum(len(s['text']) for s in ai_segments)
        human_char_count = sum(len(s['text']) for s in human_segments)
        
        # Ensure percentages are valid
        ai_percentage = (ai_char_count / total_length) * 100 if total_length > 0 else 0
        human_percentage = (human_char_count / total_length) * 100 if total_length > 0 else 0
        
        # Clamp percentages to valid range
        ai_percentage = max(0, min(100, ai_percentage))
        human_percentage = max(0, min(100, human_percentage))
        
        # Calculate average probabilities
        avg_ai_prob = sum(s['probability'] for s in segments) / len(segments) if segments else 0
        
        result = {
            'segments': segments,
            'statistics': {
                'total_length': total_length,
                'ai_percentage': round(ai_percentage, 2),
                'human_percentage': round(human_percentage, 2),
                'avg_ai_probability': round(avg_ai_prob * 100, 2),
                'total_segments': len(segments),
                'ai_segments': len(ai_segments),
                'human_segments': len(human_segments)
            },
            'overall_assessment': 'AI Generated' if avg_ai_prob > 0.5 else 'Human Written'
        }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("🤖 AI Text Detector - DEMO MODE")
    print("=" * 40)
    print("⚠️  This is a demo version using mock AI detection")
    print("   For real AI detection, install dependencies and use app.py")
    print("=" * 40)
    app.run(debug=True, host='0.0.0.0', port=5000) 