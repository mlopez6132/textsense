# TextSense - AI-Powered Text Analysis Platform

A comprehensive web application that provides multiple AI-powered text analysis tools including AI detection, OCR, audio transcription, image generation, and text-to-speech capabilities.

## Features

### 🔍 **AI Text Detection**
- **Text Analysis**: Paste text directly into the web interface
- **File Upload**: Upload text files (.txt, .md, .doc, .docx) for analysis
- **AI Detection**: Uses advanced transformer models to detect AI-generated content
- **Detailed Highlighting**: Highlights AI-generated portions with probability percentages
- **Statistics Dashboard**: Shows overall AI vs human content percentages

### 📷 **OCR (Optical Character Recognition)**
- **Image Upload**: Upload images containing text
- **URL Support**: Process images from URLs
- **Multi-language Support**: Extract text in various languages
- **Real-time Processing**: Fast text extraction with loading indicators

### 🎵 **Audio Transcription**
- **Audio Upload**: Upload audio files (MP3, WAV)
- **URL Support**: Process audio from URLs
- **Multiple Formats**: Support for various audio formats
- **Language Detection**: Automatic language detection and transcription

### 🎨 **AI Image Generation**
- **Text-to-Image**: Generate images from text prompts
- **Customizable Settings**: Adjust aspect ratio, number of images, safety settings
- **Prompt Optimization**: Automatic prompt enhancement
- **Safety Features**: Built-in content safety checks

### 🔊 **Text-to-Speech**
- **Multiple Voices**: Choose from various AI voices
- **Customizable Settings**: Adjust voice parameters and vibe
- **High Quality**: Generate natural-sounding speech
- **Download Support**: Download generated audio files

### 🎨 **Modern UI/UX**
- **Responsive Design**: Works seamlessly on desktop and mobile
- **Clean Interface**: Intuitive, gradient-based design
- **Real-time Feedback**: Loading indicators and progress updates
- **Accessibility**: WCAG compliant design

## Architecture

### **Backend**: FastAPI with Relay Pattern
- **Main Application**: `src/app.py` - FastAPI server
- **Hugging Face Integration**: Connects to HF Spaces for AI processing
- **Rate Limiting**: Built-in rate limiting for API protection
- **Caching**: Intelligent caching for improved performance

### **Frontend**: Modern Web Technologies
- **HTML5/CSS3**: Semantic markup with modern styling
- **JavaScript (ES6+)**: Interactive client-side functionality
- **Bootstrap 5**: Responsive framework
- **Custom CSS**: Gradient-based design system

### **AI Services**: Hugging Face Spaces
- **AI Detection**: Custom transformer models
- **OCR Processing**: Advanced text extraction
- **Audio Processing**: Speech recognition and generation
- **Image Generation**: State-of-the-art text-to-image models

## Installation & Setup

### Prerequisites
- Python 3.10+
- pip (Python package installer)

### Local Development

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd textsense
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:
   ```bash
   export HF_INFERENCE_URL="https://your-space.hf.space/analyze"
   export HF_OCR_URL="https://your-ocr-space.hf.space/extract"
   export OPENAI_SPEECH_API_KEY="your-openai-key"
   export FLUX_API_KEY="your-flux-key"
   ```

4. **Run the application**:
   ```bash
   uvicorn src.app:app --host 0.0.0.0 --port 8000
   ```

5. **Access the web interface**:
   Open your browser and go to `http://localhost:8000`

## Deployment

### Render.com Deployment

The application can also be deployed on Render.com:

1. **Connect your GitHub repository** to Render
2. **Set environment variables**:
   - `HF_INFERENCE_URL`: Your Hugging Face Space `/analyze` endpoint
   - `HF_OCR_URL`: Your OCR Space endpoint
   - `OPENAI_SPEECH_API_KEY`: OpenAI API key for speech generation
   - `FLUX_API_KEY`: Flux API key for image generation
   - `RECAPTCHA_SITE_KEY` & `RECAPTCHA_SECRET_KEY`: For contact form
   - `CONTACT_EMAIL`: Contact email address

3. **Deploy**: Render will automatically build and deploy using `render.yaml`

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `HF_INFERENCE_URL` | Hugging Face Space for AI detection | Yes |
| `HF_OCR_URL` | Hugging Face Space for OCR | Yes |
| `OPENAI_SPEECH_API_KEY` | OpenAI API key for TTS | Yes |
| `FLUX_API_KEY` | Flux API key for image generation | Yes |
| `RECAPTCHA_SITE_KEY` | reCAPTCHA site key | No |
| `RECAPTCHA_SECRET_KEY` | reCAPTCHA secret key | No |
| `CONTACT_EMAIL` | Contact email address | No |

## Usage

### AI Text Detection
1. Navigate to the AI Detector page
2. Paste text or upload a file
3. Click "Analyze Text"
4. View highlighted results with AI probability percentages

### OCR Processing
1. Go to the OCR page
2. Upload an image or provide an image URL
3. Select language (optional)
4. Click "Extract Text"
5. View extracted text results

### Audio Transcription
1. Visit the Audio-to-Text page
2. Upload an audio file or provide URL
3. Select audio type and language
4. Click "Transcribe"
5. View transcribed text

### Image Generation
1. Go to the Generate Image page
2. Enter your text prompt
3. Adjust settings (aspect ratio, number of images)
4. Click "Generate Images"
5. Download generated images

### Text-to-Speech
1. Navigate to the Text-to-Speech page
2. Enter your text
3. Select voice and settings
4. Click "Generate Speech"
5. Play or download the audio

## Project Structure

```
textsense/
├── src/                     # Main application source code
│   ├── app.py              # Main FastAPI application
│   ├── modules/            # Utility modules
│   │   ├── audio_transcription.py    # Audio processing module
│   │   ├── image_generation.py       # Image generation module
│   │   ├── speech_generation.py      # Speech generation module
│   │   └── text_humanizer.py         # Text humanization module
│   ├── templates/          # HTML templates
│   │   ├── index.html      # Homepage
│   │   ├── ai-detector.html     # AI detection page
│   │   ├── ocr.html             # OCR page
│   │   ├── audio-text.html      # Audio transcription page
│   │   ├── generate-image.html  # Image generation page
│   │   ├── text-to-speech.html  # TTS page
│   │   └── static/              # Static assets
│   │       ├── css/             # Stylesheets
│   │       ├── js/              # JavaScript files
│   │       └── images/          # Images and icons
│   └── services/           # Microservices
│       ├── textsense-inference/     # AI detection service
│       └── textsense-ocr/           # OCR service
├── requirements.txt         # Python dependencies
├── runtime.txt             # Python version specification
├── render.yaml             # Render deployment config
└── README.md               # Project documentation
```

## API Endpoints

### Core Endpoints
- `POST /analyze` - AI text detection
- `POST /ocr` - OCR text extraction
- `POST /audio-transcribe` - Audio transcription
- `POST /generate-image` - Image generation
- `POST /generate-speech` - Text-to-speech

### Utility Endpoints
- `GET /healthz` - Health check
- `GET /ping` - Ping endpoint
- `POST /contact` - Contact form submission

## Rate Limiting

The application includes built-in rate limiting:
- AI Detection: 20 requests/minute
- OCR: 15 requests/minute
- Audio Transcription: 10 requests/minute
- Image Generation: 5 requests/minute
- Speech Generation: 8 requests/minute
- Contact Form: 5 requests/minute

## Security Features

- **Rate Limiting**: Prevents API abuse
- **File Size Limits**: Prevents large file uploads
- **Content Validation**: Validates uploaded content
- **CORS Protection**: Secure cross-origin requests
- **Security Headers**: Comprehensive security headers
- **reCAPTCHA**: Spam protection for contact forms

## Performance Optimizations

- **Caching**: Intelligent caching for AI detection results
- **Connection Pooling**: HTTP connection reuse
- **Streaming**: Efficient file processing
- **CDN Headers**: Optimized static asset delivery
- **Compression**: Gzip compression for responses

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is for educational and research purposes. Please ensure you have proper licenses for any AI models and services used.

## Support

For technical support or questions:
- Check the troubleshooting section
- Create an issue in the project repository
- Contact via the built-in contact form

## Changelog

### Latest Updates
- ✅ Comprehensive AI text analysis platform
- ✅ Multi-modal AI capabilities (text, image, audio)
- ✅ Modern FastAPI backend with relay pattern
- ✅ Responsive web interface
- ✅ Production-ready deployment configuration
- ✅ Built-in security and rate limiting
- ✅ Performance optimizations and caching 