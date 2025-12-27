document.addEventListener('DOMContentLoaded', function() {
    const humanizerForm = document.getElementById('humanizerForm');
    const textInput = document.getElementById('textInput');
    const charCounter = document.getElementById('charCounter');
    const inputLoadingOverlay = document.getElementById('inputLoadingOverlay');
    const resultsSection = document.getElementById('resultsSection');
    const resultText = document.getElementById('resultText');
    const errorSection = document.getElementById('errorSection');
    const errorMessage = document.getElementById('errorMessage');
    const submitBtn = humanizerForm ? humanizerForm.querySelector('button[type="submit"]') : null;

    const MAX_CHARS = 5000;

    // Character counter
    if (textInput && charCounter) {
        textInput.addEventListener('input', function() {
            const current = this.value.length;
            if (current > MAX_CHARS) {
                this.value = this.value.substring(0, MAX_CHARS);
            }
            charCounter.textContent = `${this.value.length.toLocaleString()} / ${MAX_CHARS.toLocaleString()}`;
        });
    }

    // Form submission
    if (humanizerForm) {
        humanizerForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const text = textInput.value.trim();
            if (!text) {
                showError('Please enter text to humanize.');
                return;
            }

            if (text.length < 10) {
                showError('Text is too short. Please enter at least 10 characters.');
                return;
            }

            const intensity = document.querySelector('input[name="intensity"]:checked').value;
            
            showLoading();
            
            try {
                const formData = new FormData();
                formData.append('text', text);
                formData.append('intensity', intensity);

                const response = await fetch('/humanize-text', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.detail || 'Failed to humanize text');
                }

                displayResults(data);

            } catch (err) {
                console.error(err);
                showError(err.message || 'An error occurred. Please try again.');
            } finally {
                hideLoading();
            }
        });
    }

    function displayResults(data) {
        resultText.value = data.humanized_text;
        
        // Update metrics
        const metrics = data.metrics || {};
        document.getElementById('metricScore').textContent = metrics.readability_score || '-';
        document.getElementById('metricGrade').textContent = metrics.grade_level || '-';
        document.getElementById('metricWords').textContent = metrics.word_count || '-';
        document.getElementById('metricSentences').textContent = metrics.sentence_count || '-';
        
        resultsSection.classList.remove('d-none');
        resultsSection.scrollIntoView({ behavior: 'smooth' });
    }

    function showLoading() {
        hideError();
        resultsSection.classList.add('d-none');
        if (inputLoadingOverlay) inputLoadingOverlay.classList.remove('d-none');
        if (submitBtn) submitBtn.disabled = true;
        if (textInput) textInput.readOnly = true;
    }

    function hideLoading() {
        if (inputLoadingOverlay) inputLoadingOverlay.classList.add('d-none');
        if (submitBtn) submitBtn.disabled = false;
        if (textInput) textInput.readOnly = false;
    }

    function showError(msg) {
        errorMessage.textContent = msg;
        errorSection.classList.remove('d-none');
    }

    function hideError() {
        errorSection.classList.add('d-none');
    }

    // Copy functionality
    window.copyToClipboard = function() {
        if (resultText && resultText.value) {
            navigator.clipboard.writeText(resultText.value).then(() => {
                const btn = document.querySelector('button[onclick="copyToClipboard()"]');
                const originalHtml = btn.innerHTML;
                btn.innerHTML = '<i class="fas fa-check me-1"></i>Copied!';
                btn.classList.remove('btn-light', 'text-success');
                btn.classList.add('btn-success', 'text-white');
                
                setTimeout(() => {
                    btn.innerHTML = originalHtml;
                    btn.classList.remove('btn-success', 'text-white');
                    btn.classList.add('btn-light', 'text-success');
                }, 2000);
            });
        }
    };
});

