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
    const includeTimestamps = document.getElementById('includeTimestamps');
    const timestampsSection = document.getElementById('timestampsSection');
    const timestampsOutput = document.getElementById('timestampsOutput');
    const downloadTimestampsBtn = document.getElementById('downloadTimestampsBtn');

    let currentAudioFile = null;
    let currentTranscriptionData = null;

    // File handling
    function handleAudioFile(file) {
        if (!file || !file.type.startsWith('audio/')) {
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
        timestampsSection.style.display = 'none';
        timestampsOutput.innerHTML = '';
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

            formData.append('return_timestamps', includeTimestamps.checked);

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

            // Display timestamps if available
            if (data.chunks && data.chunks.length > 0 && includeTimestamps.checked) {
                displayTimestamps(data.chunks);
                timestampsSection.style.display = 'block';
            } else {
                timestampsSection.style.display = 'none';
            }
        } catch (error) {
            console.error('Transcription error:', error);
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

    // Download timestamps
    downloadTimestampsBtn.addEventListener('click', () => {
        if (!currentTranscriptionData || !currentTranscriptionData.chunks) {
            return;
        }

        const blob = new Blob([JSON.stringify(currentTranscriptionData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'textsense-transcription-with-timestamps.json';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    });

    function displayTimestamps(chunks) {
        timestampsOutput.innerHTML = '';
        
        chunks.forEach((chunk, index) => {
            const chunkDiv = document.createElement('div');
            chunkDiv.className = 'timestamp-chunk p-3 mb-2 border rounded';
            
            const timeSpan = document.createElement('span');
            timeSpan.className = 'badge bg-primary me-2';
            const startTime = formatTime(chunk.timestamp[0]);
            const endTime = formatTime(chunk.timestamp[1]);
            timeSpan.textContent = `${startTime} - ${endTime}`;
            
            const textSpan = document.createElement('span');
            textSpan.textContent = chunk.text;
            
            chunkDiv.appendChild(timeSpan);
            chunkDiv.appendChild(textSpan);
            timestampsOutput.appendChild(chunkDiv);
        });
    }

    function formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        const millisecs = Math.floor((seconds % 1) * 1000);
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${millisecs.toString().padStart(3, '0')}`;
    }


});
