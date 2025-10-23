// Text-to-Speech JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const textInput = document.getElementById('textInput');
    const charCount = document.getElementById('charCount');
    const voiceSelect = document.getElementById('voiceSelect');
    const vibeSelect = document.getElementById('vibeSelect');
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

        // Change color based on character limit (999 max)
        if (count > 999) {
            charCount.className = 'text-danger fw-bold';
            charCount.textContent += ' ⚠️ Exceeds limit';
        } else if (count > 900) {
            charCount.className = 'text-warning fw-bold';
            charCount.textContent += ' ⚠️ Near limit';
        } else {
            charCount.className = 'text-muted';
        }
    }

    textInput.addEventListener('input', updateCharCount);
    textInput.addEventListener('keyup', updateCharCount);
    updateCharCount(); // Initial count

    // Clear functionality
    function clearAll() {
        textInput.value = '';
        updateCharCount();
        voiceSelect.selectedIndex = 0;
        vibeSelect.selectedIndex = 0;
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
        console.log('Generate speech button clicked');
        const text = textInput.value.trim();
        const voice = voiceSelect.value;
        const vibe = vibeSelect.value;

        console.log('Form data:', { text: text.substring(0, 50), voice, vibe: vibe.substring(0, 50) });

        if (!text) {
            alert('Please enter some text to convert to speech.');
            return;
        }

        if (text.length > 999) {
            alert('Text is too long. Please limit to 999 characters.');
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
            formData.append('vibe', vibe);

            const response = await fetch('/generate-speech', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                try {
                    const errorData = await response.json().catch(() => ({}));
                    errorMessage = errorData.detail || errorMessage;
                } catch (e) {
                    // If JSON parsing fails, try to get text
                    try {
                        const errorText = await response.text();
                        errorMessage = errorText || errorMessage;
                    } catch (e2) {
                        // Use default error message
                    }
                }
                throw new Error(errorMessage);
            }

            // Get the audio blob
            currentAudioBlob = await response.blob();
            console.log('Audio blob received:', currentAudioBlob.size, 'bytes, type:', currentAudioBlob.type);

            // Create object URL for the audio
            currentAudioUrl = URL.createObjectURL(currentAudioBlob);
            console.log('Audio URL created:', currentAudioUrl);

            // Set audio source and show preview
            generatedAudio.src = currentAudioUrl;
            audioPreviewSection.style.display = 'block';
            console.log('Audio preview section shown');

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

    // Voice and vibe change listeners
    voiceSelect.addEventListener('change', () => {
        console.log('Voice changed to:', voiceSelect.value);
    });

    vibeSelect.addEventListener('change', () => {
        console.log('Vibe changed to:', vibeSelect.options[vibeSelect.selectedIndex].text);
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
