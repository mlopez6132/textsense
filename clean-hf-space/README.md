---
title: TextSense Audio-to-Text
emoji: 🎙️
colorFrom: blue
colorTo: purple
sdk: docker
sdk_version: "4.26.0"
app_file: app.py
pinned: false
---

# TextSense Audio-to-Text (OpenAI Whisper)

This service provides audio-to-text transcription using OpenAI's Whisper API with their state-of-the-art speech recognition model.

## Features

- **High Accuracy**: Uses OpenAI Whisper-1 model with state-of-the-art accuracy
- **Multilingual Support**: Supports transcription in 99+ languages with automatic language detection
- **Word-level Timestamps**: Optional word-level timestamps for precise timing
- **Multiple Formats**: Supports various audio and video formats
- **Large Files**: Handles files up to 25MB with OpenAI API
- **Real-time Processing**: Fast and efficient transcription processing

## Setup

### Environment Variables

Set your OpenAI API key:

```bash
export OPENAI_API_KEY="your_api_key_here"
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run the Service

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

## API Usage

### Transcribe Audio

**POST** `/transcribe`

#### Parameters:
- `audio` (file): Audio/video file to transcribe
- `audio_url` (string): URL to audio/video file (alternative to file upload)
- `include_word_timestamps` (boolean): Include word-level timestamps (default: false)

#### Response:
```json
{
  "text": "Full transcription text...",
  "chunks": [
    {
      "text": "Segment text...",
      "timestamp": [start_time, end_time],
      "words": [
        {
          "text": "word",
          "timestamp": [start_time, end_time]
        }
      ]
    }
  ],
  "engine": "openai_whisper",
  "model": "whisper-1",
  "language": "en"
}
```

### Health Check

**GET** `/healthz`

Returns service status and configuration.

## Supported Formats

### Audio Formats:
- MP3, MP4, M4A, M2A, MP2, AAC, WAV, FLAC, OGG, WMA, FLV, AVI, MOV, MPEG, MPG, 3GP, WMV, ASF, FLV, F4V, F4P, F4A, F4B

### File Size Limit:
- **Maximum**: 25MB per file (OpenAI API limitation)
- **Recommended**: Under 10MB for optimal performance

**Note**: For larger files, consider splitting them into smaller segments before uploading.

## OpenAI Pricing

Based on the [OpenAI pricing](https://openai.com/pricing):

- **Whisper API**: $0.006 per minute (approximately $0.36 per hour)
- **Pay-as-you-go**: No monthly fees, only pay for what you use
- **Free Tier**: Not available for Whisper API
- **Volume Discounts**: Available for high-volume usage

**Note**: OpenAI Whisper API has a 25MB file size limit per request.

## Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# Install ffmpeg for audio processing
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

Check out the configuration reference at https://huggingface.co/docs/hub/spaces-config-reference
