// Text-to-Speech JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const textInput = document.getElementById('textInput');
    const charCount = document.getElementById('charCount');
    const voiceSelect = document.getElementById('voiceSelect');
    const emotionStyleInput = document.getElementById('emotionStyleInput');
    const emotionCharCount = document.getElementById('emotionCharCount');
    const generateSpeechBtn = document.getElementById('generateSpeechBtn');
    const clearBtn = document.getElementById('clearBtn');
    const generatingSpeech = document.getElementById('generatingSpeech');
    const audioPreviewSection = document.getElementById('audioPreviewSection');
    const generatedAudio = document.getElementById('generatedAudio');
    const downloadAudioBtn = document.getElementById('downloadAudioBtn');
    const playAgainBtn = document.getElementById('playAgainBtn');

    let currentAudioUrl = null;
    let currentAudioBlob = null;

    // Character count functionality
    function updateCharCount() {
        const text = textInput.value;
        const count = text.length;
        const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;

        // Show both character and word count
        charCount.textContent = `${count} characters (${wordCount} words)`;

        // Change color and add warnings based on character limit
        if (count > 22500) {
            charCount.className = 'text-danger fw-bold';
            charCount.textContent += ' ⚠️ Very long text - generation may take several minutes';
        } else if (count > 20000) {
            charCount.className = 'text-warning fw-bold';
            charCount.textContent += ' ⚠️ Long text - will be processed in chunks';
        } else if (count > 15000) {
            charCount.className = 'text-info';
            charCount.textContent += ' 📝 Long-form content supported';
        } else if (count > 5000) {
            charCount.className = 'text-success';
            charCount.textContent += ' ✅ Good length for detailed content';
        } else {
            charCount.className = 'text-muted';
        }
    }

    textInput.addEventListener('input', updateCharCount);
    textInput.addEventListener('keyup', updateCharCount);
    updateCharCount(); // Initial count

    // Emotion style character count functionality
    function updateEmotionCharCount() {
        const emotionText = emotionStyleInput.value;
        const emotionCount = emotionText.length;
        emotionCharCount.textContent = `${emotionCount} characters`;

        // Change color based on character limit
        if (emotionCount > 180) {
            emotionCharCount.className = 'text-danger';
        } else if (emotionCount > 150) {
            emotionCharCount.className = 'text-warning';
        } else {
            emotionCharCount.className = 'text-muted';
        }
    }

    emotionStyleInput.addEventListener('input', updateEmotionCharCount);
    emotionStyleInput.addEventListener('keyup', updateEmotionCharCount);
    updateEmotionCharCount(); // Initial count

    // Clear functionality
    function clearAll() {
        textInput.value = '';
        updateCharCount();
        voiceSelect.selectedIndex = 0;
        emotionStyleInput.value = '';
        updateEmotionCharCount();
        hideAudioPreview();
        clearAudioData();
    }

    function clearAudioData() {
        if (currentAudioUrl) {
            URL.revokeObjectURL(currentAudioUrl);
            currentAudioUrl = null;
        }
        currentAudioBlob = null;
        generatedAudio.src = '';
    }

    function hideAudioPreview() {
        audioPreviewSection.style.display = 'none';
        generatedAudio.pause();
    }

    clearBtn.addEventListener('click', clearAll);

    // Generate speech functionality
    generateSpeechBtn.addEventListener('click', async () => {
        const text = textInput.value.trim();
        const voice = voiceSelect.value;
        const emotionStyle = emotionStyleInput.value.trim();

        if (!text) {
            alert('Please enter some text to convert to speech.');
            return;
        }

        if (text.length > 25000) {
            alert('Text is too long. Please limit to 25,000 characters.');
            return;
        }

        if (emotionStyle.length > 200) {
            alert('Emotion style prompt is too long. Please limit to 200 characters.');
            return;
        }

        // Show loading state
        generatingSpeech.style.display = 'block';
        generateSpeechBtn.disabled = true;
        hideAudioPreview();
        clearAudioData();

        try {
            const formData = new FormData();
            formData.append('text', text);
            formData.append('voice', voice);
            formData.append('emotion_style', emotionStyle);

            const response = await fetch('/generate-speech', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
            }

            // Get the audio blob
            currentAudioBlob = await response.blob();

            // Create object URL for the audio
            currentAudioUrl = URL.createObjectURL(currentAudioBlob);

            // Set audio source and show preview
            generatedAudio.src = currentAudioUrl;
            audioPreviewSection.style.display = 'block';

            // Auto-play the audio (optional)
            generatedAudio.play().catch(e => {
                console.log('Auto-play prevented by browser:', e);
            });

        } catch (error) {
            console.error('Speech generation error:', error);
            alert(`Failed to generate speech: ${error.message}`);
        } finally {
            generatingSpeech.style.display = 'none';
            generateSpeechBtn.disabled = false;
        }
    });

    // Download audio functionality
    downloadAudioBtn.addEventListener('click', () => {
        if (!currentAudioBlob) {
            alert('No audio available to download.');
            return;
        }

        const url = URL.createObjectURL(currentAudioBlob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `textsense-speech-${Date.now()}.mp3`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    });

    // Play again functionality
    playAgainBtn.addEventListener('click', () => {
        if (generatedAudio.src) {
            generatedAudio.currentTime = 0;
            generatedAudio.play().catch(e => {
                console.log('Play prevented by browser:', e);
            });
        }
    });

    // Voice preview functionality (optional enhancement)
    voiceSelect.addEventListener('change', () => {
        // Could add voice preview samples here in the future
        console.log('Voice changed to:', voiceSelect.value);
    });

    emotionStyleInput.addEventListener('change', () => {
        // Could add emotion style preview here in the future
        console.log('Emotion style changed to:', emotionStyleInput.value);
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        // Ctrl+Enter or Cmd+Enter to generate speech
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            generateSpeechBtn.click();
        }
        // Escape to clear
        if (e.key === 'Escape') {
            clearBtn.click();
        }
    });

    // Prevent accidental navigation away with unsaved audio
    window.addEventListener('beforeunload', (e) => {
        if (currentAudioBlob && !generatedAudio.paused) {
            e.preventDefault();
            e.returnValue = 'You have generated audio that may be lost if you leave this page.';
        }
    });

    // Clean up on page unload
    window.addEventListener('unload', clearAudioData);

    // Example text suggestions (optional)
    const exampleTexts = [
        "Hello! Welcome to TextSense, your AI-powered text analysis platform.",
        "The quick brown fox jumps over the lazy dog. This is a test of the text-to-speech system.",
        "Today is a beautiful day filled with possibilities and new opportunities.",
        "Thank you for using our text-to-speech service. We hope you enjoy the natural-sounding voices!"
    ];

    // Add example text buttons (optional enhancement)
    function addExampleTexts() {
        const examplesSection = document.createElement('div');
        examplesSection.className = 'mt-3';
        examplesSection.innerHTML = `
            <small class="text-muted">Try these examples:</small>
            <div class="d-flex flex-wrap gap-1 mt-2">
                ${exampleTexts.map((text, index) => `
                    <button class="btn btn-outline-secondary btn-sm example-btn" data-text="${text}">
                        Example ${index + 1}
                    </button>
                `).join('')}
            </div>
        `;

        // Insert after the textarea
        textInput.parentNode.appendChild(examplesSection);

        // Add event listeners
        document.querySelectorAll('.example-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                textInput.value = btn.dataset.text;
                updateCharCount();
            });
        });
    }

    // Uncomment to add example texts
    // addExampleTexts();

});
