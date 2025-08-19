# TextSense Audio-to-Text (ElevenLabs)

This service provides audio-to-text transcription using ElevenLabs Speech-to-Text API with their state-of-the-art Scribe v1 model.

## Features

- **High Accuracy**: Uses ElevenLabs Scribe v1 model with state-of-the-art accuracy
- **99 Languages**: Supports transcription in 99 languages with automatic language detection
- **Word-level Timestamps**: Optional word-level timestamps for precise timing
- **Speaker Diarization**: Identifies different speakers in the audio
- **Multiple Formats**: Supports various audio and video formats
- **Large Files**: Handles files up to 3GB and 10 hours duration

## Setup

### Environment Variables

Set your ElevenLabs API key:

```bash
export ELEVENLABS_API_KEY="your_api_key_here"
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
  "engine": "elevenlabs",
  "model": "eleven_scribe_v1",
  "language": "en"
}
```

### Health Check

**GET** `/healthz`

Returns service status and configuration.

## Supported Formats

### Audio Formats:
- AAC, AIFF, OGG, MP3, OPUS, WAV, WebM, FLAC, M4A

### Video Formats:
- MP4, AVI, MKV, MOV, WMV, FLV, WebM, MPEG, 3GP

## ElevenLabs Pricing

Based on the [ElevenLabs pricing](https://elevenlabs.io/docs/capabilities/speech-to-text#pricing):

- **Free**: Not available for Speech-to-Text
- **Starter ($5/month)**: 12.5 hours included, $0.40/hour
- **Creator ($22/month)**: 62.8 hours included, $0.35/hour, $0.48/additional hour
- **Pro ($99/month)**: 300 hours included, $0.33/hour, $0.40/additional hour
- **Scale ($330/month)**: 1,100 hours included, $0.30/hour, $0.33/additional hour
- **Business ($1,320/month)**: 6,000 hours included, $0.22/hour

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