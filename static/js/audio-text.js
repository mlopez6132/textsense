// Audio-to-Text Transcription JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const audioDropzone = document.getElementById('audioDropzone');
    const audioFileInput = document.getElementById('audioFileInput');
    const audioUrl = document.getElementById('audioUrl');
    const audioPreview = document.getElementById('audioPreview');
    const audioInfo = document.getElementById('audioInfo');
    const audioAnalysisSection = document.getElementById('audioAnalysisSection');
    const transcribeBtn = document.getElementById('transcribeBtn');
    const clearAudioBtn = document.getElementById('clearAudioBtn');
    const transcribing = document.getElementById('transcribing');
    const transcriptionOutput = document.getElementById('transcriptionOutput');
    const transcriptionControls = document.getElementById('transcriptionControls');
    const copyTranscriptionBtn = document.getElementById('copyTranscriptionBtn');
    const downloadTranscriptionBtn = document.getElementById('downloadTranscriptionBtn');
    const audioTypeSelect = document.getElementById('audioType');
    const languageCodeInput = document.getElementById('languageCode');

    let currentAudioFile = null;
    let currentTranscriptionData = null;

    // File handling
    function handleAudioFile(file) {
        if (!file || !file.type.startsWith('audio/')) {
            return;
        }

        // Check if file format is supported (MP3 or WAV only)
        const fileName = file.name.toLowerCase();
        const isMp3 = fileName.endsWith('.mp3') || file.type.includes('mpeg');
        const isWav = fileName.endsWith('.wav') || file.type.includes('wav');
        
        if (!isMp3 && !isWav) {
            alert('Only MP3 and WAV files are supported. Please select a different file.');
            return;
        }

        currentAudioFile = file;
        const url = URL.createObjectURL(file);
        audioPreview.src = url;
        
        // Format file size
        const sizeInMB = (file.size / (1024 * 1024)).toFixed(2);
        audioInfo.textContent = `${file.name} (${sizeInMB} MB)`;
        
        audioAnalysisSection.style.display = 'block';
        clearResults();
    }

    function handleAudioUrl(url) {
        if (!url || !isValidUrl(url)) {
            return;
        }

        currentAudioFile = null;
        audioPreview.src = url;
        audioInfo.textContent = `Audio from URL: ${url}`;
        audioAnalysisSection.style.display = 'block';
        clearResults();
    }

    function isValidUrl(string) {
        try {
            new URL(string);
            return true;
        } catch (_) {
            return false;
        }
    }

    function clearResults() {
        transcriptionOutput.value = '';
        transcriptionControls.style.display = 'none';
        currentTranscriptionData = null;
    }

    function clearAll() {
        currentAudioFile = null;
        audioPreview.src = '';
        audioUrl.value = '';
        audioInfo.textContent = 'No audio loaded';
        audioAnalysisSection.style.display = 'none';
        clearResults();
    }

    // Drag and drop functionality
    audioDropzone.addEventListener('click', () => audioFileInput.click());
    audioDropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        audioDropzone.classList.add('dragover');
    });
    audioDropzone.addEventListener('dragleave', () => {
        audioDropzone.classList.remove('dragover');
    });
    audioDropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        audioDropzone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleAudioFile(files[0]);
        }
    });

    // File input change
    audioFileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleAudioFile(e.target.files[0]);
        }
    });

    // URL input handling
    audioUrl.addEventListener('blur', () => {
        const url = audioUrl.value.trim();
        if (url) {
            handleAudioUrl(url);
        }
    });

    audioUrl.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            const url = audioUrl.value.trim();
            if (url) {
                handleAudioUrl(url);
            }
        }
    });

    // Clear button
    clearAudioBtn.addEventListener('click', clearAll);

    // Transcribe button
    transcribeBtn.addEventListener('click', async () => {
        if (!currentAudioFile && !audioUrl.value.trim()) {
            alert('Please upload an MP3/WAV file or enter a valid audio URL.');
            return;
        }

        // Show loading state
        transcribing.style.display = 'block';
        transcribeBtn.disabled = true;

        try {
            const formData = new FormData();
            
            if (currentAudioFile) {
                formData.append('audio', currentAudioFile);
            } else {
                formData.append('audio_url', audioUrl.value.trim());
            }

            // Include audio type and optional language code
            const audioType = (audioTypeSelect?.value || 'general').trim();
            formData.append('audio_type', audioType);
            const languageCode = (languageCodeInput?.value || '').trim();
            if (languageCode) {
                formData.append('language', languageCode);
            }


            const response = await fetch('/audio-transcribe', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Transcription failed');
            }

            // Display results
            currentTranscriptionData = data;
            transcriptionOutput.value = data.text || '';
            transcriptionControls.style.display = 'block';

        } catch (error) {
            console.error('Transcription error:', error);
            alert(`Transcription failed: ${error.message}`);
        } finally {
            transcribing.style.display = 'none';
            transcribeBtn.disabled = false;
        }
    });

    // Copy transcription
    copyTranscriptionBtn.addEventListener('click', async () => {
        try {
            await navigator.clipboard.writeText(transcriptionOutput.value);
        } catch (error) {
            console.error('Copy error:', error);
        }
    });

    // Download transcription
    downloadTranscriptionBtn.addEventListener('click', () => {
        const text = transcriptionOutput.value;
        if (!text) {
            return;
        }

        const blob = new Blob([text], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'textsense-transcription.txt';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    });



});
