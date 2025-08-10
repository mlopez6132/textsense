# AI Text Detector Web Application

A modern web application that analyzes text documents to detect AI-generated content with detailed highlighting and percentage analysis.

## Features

- **Text Analysis**: Paste text directly into the web interface
- **File Upload**: Upload text files (.txt, .md, .doc, .docx) for analysis
- **AI Detection**: Uses advanced transformer models to detect AI-generated content
- **Detailed Highlighting**: Highlights AI-generated portions with probability percentages
- **Statistics Dashboard**: Shows overall AI vs human content percentages
- **Responsive Design**: Works on desktop and mobile devices
- **Real-time Analysis**: Fast processing with loading indicators

## Screenshots

The application features a modern, gradient-based design with:
- Clean, intuitive interface
- Color-coded highlighting (red for AI, green for human)
- Interactive tooltips showing probability percentages
- Responsive statistics cards
- Smooth animations and transitions

## Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package installer)

### Setup Instructions

1. **Clone or download the project files**

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Download the AI detection model**:
   The application uses the `desklib/ai-text-detector-v1.01` model. You'll need to download this model or have it available in your project directory.

4. **Run the application**:
   ```bash
   python app.py
   ```

5. **Access the web interface**:
   Open your browser and go to `http://localhost:5000`

## Usage

### Text Input
1. Click on the "Text Input" tab
2. Paste or type your text in the textarea
3. Click "Analyze Text"
4. View the results with highlighted segments

### File Upload
1. Click on the "File Upload" tab
2. Select a supported file (.txt, .md, .doc, .docx)
3. Click "Upload & Analyze"
4. View the analysis results

### Understanding Results

- **Overall Assessment**: Shows whether the entire document is classified as AI-generated or human-written
- **AI Percentage**: Percentage of text identified as AI-generated
- **Human Percentage**: Percentage of text identified as human-written
- **Average AI Probability**: Average confidence score across all segments
- **Highlighted Text**: 
  - Red highlighting = AI-generated content
  - Green highlighting = Human-written content
  - Hover over highlights to see probability percentages

## Technical Details

### Architecture
- **Backend**: Flask web framework (Render relay can run FastAPI)
- **Frontend**: HTML5, CSS3, JavaScript (ES6+)
- **AI Model**: Transformer-based text classification
- **Styling**: Bootstrap 5 + custom CSS

### AI Detection Method
The application uses a sophisticated approach:
1. Breaks text into overlapping segments (200 characters with 50-character overlap)
2. Analyzes each segment using the AI detection model
3. Combines results to provide overall assessment
4. Highlights individual segments based on their classification

### File Support
- **Text files** (.txt): Direct text content
- **Markdown** (.md): Markdown-formatted text
- **Word documents** (.doc, .docx): Microsoft Word documents

## Configuration

### Model Settings
You can modify the AI detection parameters in `app.py`:
- `segment_length`: Length of text segments (default: 200)
- `overlap`: Overlap between segments (default: 50)
- `threshold`: Classification threshold (default: 0.5)

### Web Server Settings
Modify the Flask app configuration in `app.py`:
- `SECRET_KEY`: Change for production use
- `MAX_CONTENT_LENGTH`: Maximum file upload size
- Port and host settings in the `app.run()` call

## Deployment

Render (relay): the app can run a lightweight FastAPI relay that forwards `/analyze` to a GPU-backed Hugging Face Space. Start command:

```
uvicorn relay_fastapi:app --host 0.0.0.0 --port $PORT
```

Set environment variables on Render:
- `HF_INFERENCE_URL`: your Space `/analyze` endpoint, e.g. `https://<org>-<space>.hf.space/analyze`
- `HF_API_KEY` (optional, if the Space is private)

## Troubleshooting

### Common Issues

1. **Model not found error**:
   - Ensure the AI model is downloaded and available
   - Check the model directory path in `app.py`

2. **Memory issues with large files**:
   - Reduce `segment_length` in the configuration
   - Increase system memory or use smaller files

3. **Slow processing**:
   - The first analysis may be slow as the model loads
   - Subsequent analyses will be faster
   - Consider using GPU if available

### Performance Tips

- Use GPU acceleration if available (CUDA-compatible)
- Limit file sizes for faster processing
- Close other applications to free up memory

## Development

### Project Structure
```
ai-text-police/
├── app.py                 # Main Flask application
├── test-detector.py       # Original test script
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── templates/
│   └── index.html        # Main web template
├── static/
│   ├── css/
│   │   └── style.css     # Custom styles
│   └── js/
│       └── script.js     # Frontend JavaScript
└── uploads/              # Temporary file storage
```

### Adding Features
- Modify `app.py` for backend functionality
- Update `templates/index.html` for UI changes
- Edit `static/css/style.css` for styling
- Modify `static/js/script.js` for frontend behavior

## License

This project is for educational and research purposes. Please ensure you have proper licenses for any AI models used.

## Contributing

Feel free to submit issues, feature requests, or pull requests to improve the application.

## Support

For technical support or questions, please check the troubleshooting section or create an issue in the project repository. 