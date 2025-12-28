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
        
        // Update detector scores
        const detectorScores = metrics.detector_scores || {};
        if (detectorScores && Object.keys(detectorScores).length > 0) {
            // Remove the _disclaimer key if present (it's metadata, not a score)
            const { _disclaimer, ...scores } = detectorScores;
            
            document.getElementById('detectorZeroGPT').textContent = scores.zerogpt || detectorScores.zerogpt || '-';
            document.getElementById('detectorQuillbot').textContent = scores.quillbot || detectorScores.quillbot || '-';
            document.getElementById('detectorGPTZero').textContent = scores.gptzero || detectorScores.gptzero || '-';
            document.getElementById('detectorOriginality').textContent = scores.originality || detectorScores.originality || '-';
            document.getElementById('detectorCopyleaks').textContent = scores.copyleaks || detectorScores.copyleaks || '-';
            document.getElementById('detectorTurnitin').textContent = scores.turnitin || detectorScores.turnitin || '-';
            
            // Show detector scores section
            const detectorSection = document.getElementById('detectorScoresSection');
            if (detectorSection) {
                detectorSection.style.display = 'block';
            }
            
            // Update colors based on scores
            updateDetectorColors(scores);
        }
        
        resultsSection.classList.remove('d-none');
        resultsSection.scrollIntoView({ behavior: 'smooth' });
    }
    
    function updateDetectorColors(scores) {
        // Helper function to parse percentage from score string
        const parsePercentage = (score) => {
            if (!score) return null;
            const match = score.match(/(\d+)%/);
            return match ? parseInt(match[1]) : null;
        };
        
        // Helper function to determine if score is good (green), medium (yellow), or bad (red)
        const getScoreColor = (score, detectorName) => {
            if (!score) return 'text-danger';
            
            const lower = score.toLowerCase();
            const percentage = parsePercentage(score);
            
            // For ZeroGPT: Low AI percentage is good (green), high AI percentage is bad (red)
            if (detectorName === 'zerogpt') {
                if (percentage !== null) {
                    if (percentage <= 10) return 'text-success'; // 0-10% AI is excellent
                    if (percentage <= 25) return 'text-warning'; // 11-25% AI is okay
                    return 'text-danger'; // >25% AI is bad
                }
                if (lower.includes('0%')) return 'text-success';
                return 'text-danger';
            }
            
            // For Quillbot: High human percentage is good (green), low human percentage is bad (red)
            if (detectorName === 'quillbot') {
                if (percentage !== null) {
                    if (percentage >= 80) return 'text-success'; // 80-100% Human is excellent
                    if (percentage >= 50) return 'text-warning'; // 50-79% Human is okay
                    return 'text-danger'; // <50% Human is bad
                }
                if (lower.includes('100% human') || lower.includes('human')) return 'text-success';
                return 'text-danger';
            }
            
            // For other detectors: Check for positive indicators
            if (lower.includes('0%') || 
                lower.includes('100% human') || 
                lower.includes('undetectable') || 
                lower.includes('bypassed') || 
                lower.includes('human content') || 
                lower.includes('original')) {
                return 'text-success';
            }
            
            // Medium scores
            if (lower.includes('low detection') || 
                lower.includes('mostly human') || 
                lower.includes('mostly original')) {
                return 'text-warning';
            }
            
            // Bad scores (detected, AI content, etc.)
            if (lower.includes('detected') || 
                lower.includes('ai detected') || 
                lower.includes('ai content') || 
                lower.includes('ai generated')) {
                return 'text-danger';
            }
            
            // Default to warning if unclear
            return 'text-warning';
        };
        
        const elements = {
            'detectorZeroGPT': { score: scores.zerogpt, name: 'zerogpt' },
            'detectorQuillbot': { score: scores.quillbot, name: 'quillbot' },
            'detectorGPTZero': { score: scores.gptzero, name: 'gptzero' },
            'detectorOriginality': { score: scores.originality, name: 'originality' },
            'detectorCopyleaks': { score: scores.copyleaks, name: 'copyleaks' },
            'detectorTurnitin': { score: scores.turnitin, name: 'turnitin' }
        };
        
        for (const [id, data] of Object.entries(elements)) {
            const element = document.getElementById(id);
            if (element) {
                // Remove all color classes
                element.classList.remove('text-success', 'text-warning', 'text-danger');
                // Add appropriate color class based on score
                const colorClass = getScoreColor(data.score, data.name);
                element.classList.add(colorClass);
            }
        }
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

