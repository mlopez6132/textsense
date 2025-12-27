// AI Text Detector - Frontend JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Form elements
    const textForm = document.getElementById('textForm');
    const fileForm = document.getElementById('fileForm');
    const textInput = document.getElementById('textInput');
    const charCounter = document.getElementById('charCounter');
    const fileInput = document.getElementById('fileInput');

    // Cache submit buttons
    const textSubmitBtn = textForm ? textForm.querySelector('button[type="submit"]') : null;
    const fileSubmitBtn = fileForm ? fileForm.querySelector('button[type="submit"]') : null;
    
    // Limits
    const MAX_CHARS = 50000;
    
    // UI elements
    const loadingSpinner = document.getElementById('loadingSpinner');
    const inputLoadingOverlay = document.getElementById('inputLoadingOverlay');
    const resultsSection = document.getElementById('resultsSection');
    const errorSection = document.getElementById('errorSection');
    const errorMessage = document.getElementById('errorMessage');
    
    // Results elements
    const overallAssessment = document.getElementById('overallAssessment');
    const aiPercentage = document.getElementById('aiPercentage');
    const humanPercentage = document.getElementById('humanPercentage');
    const avgProbability = document.getElementById('avgProbability');
    const totalSegments = document.getElementById('totalSegments');
    const totalLength = document.getElementById('totalLength');
    const highlightedText = document.getElementById('highlightedText');
    
    // Store original text for copy functionality
    let originalText = '';

    // Helper to toggle submit buttons
    function setSubmitting(isSubmitting) {
        if (textSubmitBtn) textSubmitBtn.disabled = isSubmitting;
        if (fileSubmitBtn) fileSubmitBtn.disabled = isSubmitting;
    }
    
    // Text form submission
    textForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const text = textInput.value.trim();
        
        if (!text) {
            showError('Please enter some text to analyze.');
            return;
        }
        if (text.length > MAX_CHARS) {
            showError(`Text is too long. Maximum ${MAX_CHARS.toLocaleString()} characters allowed.`);
            return;
        }
        
        analyzeText(text);
    });
    
    // File form submission
    fileForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const file = fileInput.files[0];
        
        if (!file) {
            showError('Please select a file to upload.');
            return;
        }
        
        // Check file size (16MB limit)
        if (file.size > 16 * 1024 * 1024) {
            showError('File size must be less than 16MB.');
            return;
        }
        
        // Check file type
        const allowedTypes = ['.txt', '.md', '.doc', '.docx'];
        const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
        
        if (!allowedTypes.includes(fileExtension)) {
            showError('Please upload a supported file type (.txt, .md, .doc, .docx).');
            return;
        }
        
        // Show loading while we validate content length client-side
        showLoading();
        try {
            const textContent = await file.text();
            if (textContent.length > MAX_CHARS) {
                hideLoading();
                showError(`File content is too long. Maximum ${MAX_CHARS.toLocaleString()} characters allowed.`);
                return;
            }
        } catch (err) {
            hideLoading();
            showError('Could not read file content. Please try a different file.');
            return;
        }
        
        // Proceed with upload and analysis
        analyzeFile(file);
    });
    
    // Analyze text via API
    function analyzeText(text) {
        showLoading();
        originalText = text;
        
        const formData = new FormData();
        formData.append('text', text);
        
        fetch('/analyze', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            hideLoading();
            if (data.error) {
                showError(data.error);
            } else {
                displayResults(data, text);
            }
        })
        .catch(error => {
            hideLoading();
            showError('An error occurred while analyzing the text. Please try again.');
            console.error('Error:', error);
        });
    }
    
    // Analyze file via API
    function analyzeFile(file) {
        // showLoading is already called in the submit handler (keep idempotent)
        const formData = new FormData();
        formData.append('file', file);
        
        fetch('/analyze', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            hideLoading();
            if (data.error) {
                showError(data.error);
            } else {
                // Read file content for display
                const reader = new FileReader();
                reader.onload = function(e) {
                    originalText = e.target.result;
                    displayResults(data, originalText);
                };
                reader.readAsText(file);
            }
        })
        .catch(error => {
            hideLoading();
            showError('An error occurred while analyzing the file. Please try again.');
            console.error('Error:', error);
        });
    }
    
    // Display analysis results
    function displayResults(data, originalSubmittedText) {
        // Validate response structure
        if (!data || typeof data !== 'object') {
            showError('Invalid response from server.');
            return;
        }
        
        // Update statistics with validation
        if (data.overall_assessment) {
            overallAssessment.textContent = data.overall_assessment;
        } else {
            overallAssessment.textContent = 'Analysis Complete';
        }
        
        if (data.statistics && typeof data.statistics.ai_percentage === 'number') {
            aiPercentage.textContent = Math.round(data.statistics.ai_percentage) + '%';
        } else {
            aiPercentage.textContent = '0%';
        }
        
        if (data.statistics && typeof data.statistics.human_percentage === 'number') {
            humanPercentage.textContent = Math.round(data.statistics.human_percentage) + '%';
        } else {
            humanPercentage.textContent = '0%';
        }
        
        // Create highlighted text
        const sourceText = data.cleaned_text || originalSubmittedText;
        originalText = sourceText;
        
        // Validate segments array
        const segments = Array.isArray(data.segments) ? data.segments : [];
        const highlightedContent = createHighlightedText(sourceText, segments);
        highlightedText.innerHTML = highlightedContent;
        
        // Add sentence-level statistics
        updateSentenceStats(segments);
        
        // Show results
        hideError();
        resultsSection.classList.remove('d-none');
        
        // Scroll to results
        resultsSection.scrollIntoView({ behavior: 'smooth' });
    }
    
    // Create highlighted text from segments with heatmap colors
    function createHighlightedText(text, segments) {
        if (segments.length === 0) {
            return escapeHtml(text);
        }
        
        // Sort segments by start position
        segments.sort((a, b) => a.start - b.start);
        
        let result = '';
        let lastEnd = 0;
        
        segments.forEach(segment => {
            // Validate segment indices
            if (typeof segment.start !== 'number' || typeof segment.end !== 'number' || 
                segment.start < 0 || segment.end > text.length || segment.start >= segment.end) {
                console.warn('Invalid segment:', segment);
                return; // Skip invalid segments
            }
            
            // Handle overlapping segments by adjusting start position
            const segmentStart = Math.max(segment.start, lastEnd);
            const segmentEnd = Math.min(segment.end, text.length);
            
            // Add text before this segment
            if (segmentStart > lastEnd) {
                result += escapeHtml(text.substring(lastEnd, segmentStart));
            }
            
            // Only add segment if it has valid content
            if (segmentEnd > segmentStart) {
                // Add highlighted segment - use the exact text from the original
                const originalSegmentText = text.substring(segmentStart, segmentEnd);
                const segmentText = escapeHtml(originalSegmentText);
                
                // Validate probability is a number between 0 and 1
                const probability = Math.max(0, Math.min(1, segment.probability || 0));
                const probabilityPercent = Math.round(probability * 100);
                
                // Create heatmap color based on AI probability
                const heatmapColor = getHeatmapColor(probability);
                const textColor = getContrastColor(probability);
                
                result += `<span class="heatmap-highlight" 
                               style="background-color: ${heatmapColor}; color: ${textColor};" 
                               data-probability="${probabilityPercent}% AI Probability">${segmentText}</span>`;
                
                lastEnd = segmentEnd;
            }
        });
        
        // Add remaining text
        if (lastEnd < text.length) {
            result += escapeHtml(text.substring(lastEnd));
        }
        
        return result;
    }
    
    // Generate heatmap color using 6 discrete ranges (Human → AI)
    // Range 1: Most AI-like (Deep Orange) to Range 6: Most Human-like (Deep Green)
    function getHeatmapColor(probability) {
        const palette = [
            '#2E7D32', // Range 6: Most Human-like (Deep Green)
            '#4DB6AC', // Range 5: Human-leaning (Teal Green)
            '#A7D8D8', // Range 4: Slightly Human-leaning (Light Teal)
            '#FFE082', // Range 3: Slightly AI-leaning (Light Yellow)
            '#FFB300', // Range 2: AI-leaning (Amber)
            '#E65100'  // Range 1: Most AI-like (Deep Orange)
        ];
        if (probability < 1/6) return palette[0];
        if (probability < 2/6) return palette[1];
        if (probability < 3/6) return palette[2];
        if (probability < 4/6) return palette[3];
        if (probability < 5/6) return palette[4];
        return palette[5];
    }
    
    // Get appropriate text color for contrast with background
    function getContrastColor(probability) {
        // White text on darker colors, black on lighter colors for readability
        if (probability < 1/6) return '#ffffff';  // Deep Green - white text
        if (probability < 2/6) return '#ffffff';  // Teal Green - white text
        if (probability < 3/6) return '#000000';  // Light Teal - black text
        if (probability < 4/6) return '#000000';  // Light Yellow - black text
        if (probability < 5/6) return '#000000';  // Amber - black text
        return '#ffffff';                         // Deep Orange - white text
    }
    
    // Update sentence-level statistics
    function updateSentenceStats(segments) {
        const totalSentences = segments.length;
        
        // Handle empty segments case
        if (totalSentences === 0) {
            const totalSentencesEl = document.getElementById('totalSentences');
            const aiSentencesEl = document.getElementById('aiSentences');
            const humanSentencesEl = document.getElementById('humanSentences');
            const avgProbabilityEl = document.getElementById('avgProbability');
            
            if (totalSentencesEl) totalSentencesEl.textContent = '0';
            if (aiSentencesEl) aiSentencesEl.textContent = '0';
            if (humanSentencesEl) humanSentencesEl.textContent = '0';
            if (avgProbabilityEl) avgProbabilityEl.textContent = '0%';
            return;
        }
        
        const aiSentences = segments.filter(s => s.is_ai).length;
        const humanSentences = totalSentences - aiSentences;
        
        // Calculate average probabilities
        const avgAiProb = segments.reduce((sum, s) => sum + s.probability, 0) / totalSentences;
        
        // Update the HTML elements
        const totalSentencesEl = document.getElementById('totalSentences');
        const aiSentencesEl = document.getElementById('aiSentences');
        const humanSentencesEl = document.getElementById('humanSentences');
        const avgProbabilityEl = document.getElementById('avgProbability');
        
        if (totalSentencesEl) totalSentencesEl.textContent = totalSentences;
        if (aiSentencesEl) aiSentencesEl.textContent = aiSentences;
        if (humanSentencesEl) humanSentencesEl.textContent = humanSentences;
        if (avgProbabilityEl) avgProbabilityEl.textContent = Math.round(avgAiProb * 100) + '%';
    }
    
    // Escape HTML to prevent XSS
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // Show loading spinner
    function showLoading() {
        hideError();
        resultsSection.classList.add('d-none');
        // Old global spinner hidden; show in-text overlay instead
        loadingSpinner.classList.add('d-none');
        if (inputLoadingOverlay) inputLoadingOverlay.classList.remove('d-none');
        setSubmitting(true);
    }
    
    // Hide loading spinner
    function hideLoading() {
        loadingSpinner.classList.add('d-none');
        if (inputLoadingOverlay) inputLoadingOverlay.classList.add('d-none');
        setSubmitting(false);
    }
    
    // Show error message
    function showError(message) {
        errorMessage.textContent = message;
        errorSection.classList.remove('d-none');
        hideLoading();
        resultsSection.classList.add('d-none');
    }
    
    // Hide error message
    function hideError() {
        errorSection.classList.add('d-none');
    }
    
    // Copy text to clipboard
    window.copyToClipboard = function() {
        if (originalText) {
            navigator.clipboard.writeText(originalText).then(function() {
                // Show success message
                const button = document.querySelector('button[onclick="copyToClipboard()"]');
                const originalText = button.innerHTML;
                button.innerHTML = '<i class="fas fa-check me-1"></i>Copied!';
                button.classList.remove('btn-outline-secondary');
                button.classList.add('btn-success');
                
                setTimeout(() => {
                    button.innerHTML = originalText;
                    button.classList.remove('btn-success');
                    button.classList.add('btn-outline-secondary');
                }, 2000);
            }).catch(function(err) {
                console.error('Could not copy text: ', err);
                showError('Failed to copy text to clipboard.');
            });
        }
    };

    // Download PDF report using jsPDF + html2canvas
    window.downloadPDF = function() {
        console.log('PDF download initiated...');
        
        try {
            const resultsContainer = document.getElementById('resultsSection');
            if (!resultsContainer || resultsContainer.classList.contains('d-none')) {
                showError('Please analyze some text first.');
                return;
            }

            // Resolve jsPDF constructor from UMD/non-UMD builds
            const JsPDFConstructor = (window.jspdf && window.jspdf.jsPDF) || window.jsPDF;
            if (!JsPDFConstructor) {
                showError('PDF library not loaded. Please refresh the page and try again.');
                return;
            }

            // Extract data for PDF
            const overallText = document.getElementById('overallAssessment')?.textContent || 'N/A';
            const aiPercent = document.getElementById('aiPercentage')?.textContent || '0%';
            const humanPercent = document.getElementById('humanPercentage')?.textContent || '0%';
            const totalSent = document.getElementById('totalSentences')?.textContent || '0';
            const aiSent = document.getElementById('aiSentences')?.textContent || '0';
            const humanSent = document.getElementById('humanSentences')?.textContent || '0';
            const avgProb = document.getElementById('avgProbability')?.textContent || '0%';
            const highlightedText = document.getElementById('highlightedText')?.textContent || 'No analysis available';

            console.log('Extracted data:', { overallText, aiPercent, humanPercent, totalSent, aiSent, humanSent, avgProb });

            // Initialize jsPDF
            const pdf = new JsPDFConstructor('p', 'mm', 'a4');
            pdf.setTextColor(0, 0, 0);
            
            // PDF page dimensions
            const pageWidth = pdf.internal.pageSize.getWidth();
            const pageHeight = pdf.internal.pageSize.getHeight();
            const margin = 20;
            const contentWidth = pageWidth - (margin * 2);
            let yPosition = margin;

            // Helper function to add text with word wrapping
            function addText(text, fontSize = 12, isBold = false, align = 'left') {
                if (isBold) {
                    pdf.setFont('helvetica', 'bold');
                } else {
                    pdf.setFont('helvetica', 'normal');
                }
                pdf.setFontSize(fontSize);
                
                const lines = pdf.splitTextToSize(text, contentWidth);
                lines.forEach(line => {
                    if (yPosition > pageHeight - margin) {
                        pdf.addPage();
                        yPosition = margin;
                    }
                    
                    let xPosition = margin;
                    if (align === 'center') {
                        xPosition = pageWidth / 2;
                        pdf.text(line, xPosition, yPosition, { align: 'center' });
                    } else {
                        pdf.text(line, xPosition, yPosition);
                    }
                    yPosition += fontSize * 0.5;
                });
                yPosition += 5; // Extra spacing after text block
            }

            // Helper function to add a box with text
            function addBox(x, y, width, height, text, bgColor = null) {
                if (bgColor) {
                    pdf.setFillColor(bgColor.r, bgColor.g, bgColor.b);
                    pdf.rect(x, y, width, height, 'F');
                }
                pdf.setDrawColor(200, 200, 200);
                pdf.rect(x, y, width, height);
                
                // Center text in box
                pdf.setFont('helvetica', 'bold');
                pdf.setFontSize(14);
                const textWidth = pdf.getTextWidth(text);
                const textX = x + (width - textWidth) / 2;
                const textY = y + height / 2 + 2;
                pdf.text(text, textX, textY);
            }

            // Title
            addText('TextSense Analysis Report', 24, true, 'center');
            yPosition += 10;

            // Overall Assessment
            addText('Overall Assessment', 16, true);
            addText(overallText, 14, false, 'center');
            yPosition += 10;

            // Statistics boxes
            const boxWidth = (contentWidth - 10) / 2;
            const boxHeight = 20;
            
            // AI Generated box
            addBox(margin, yPosition, boxWidth, boxHeight, aiPercent, {r: 255, g: 235, b: 238});
            pdf.setFont('helvetica', 'normal');
            pdf.setFontSize(10);
            pdf.text('AI Generated', margin + boxWidth/2, yPosition + boxHeight + 5, { align: 'center' });
            
            // Human Written box
            addBox(margin + boxWidth + 10, yPosition, boxWidth, boxHeight, humanPercent, {r: 232, g: 245, b: 233});
            pdf.text('Human Written', margin + boxWidth + 10 + boxWidth/2, yPosition + boxHeight + 5, { align: 'center' });
            
            yPosition += boxHeight + 15;

            // Detailed Statistics
            addText('Detailed Statistics', 14, true);
            yPosition += 5;
            
            const statBoxWidth = (contentWidth - 30) / 4;
            const statBoxHeight = 15;
            const stats = [
                { label: 'Total Sentences', value: totalSent },
                { label: 'AI Sentences', value: aiSent },
                { label: 'Human Sentences', value: humanSent },
                { label: 'Avg AI Probability', value: avgProb }
            ];
            
            stats.forEach((stat, index) => {
                const x = margin + (statBoxWidth + 10) * index;
                addBox(x, yPosition, statBoxWidth, statBoxHeight, stat.value);
                pdf.setFont('helvetica', 'normal');
                pdf.setFontSize(8);
                const labelLines = pdf.splitTextToSize(stat.label, statBoxWidth);
                labelLines.forEach((line, lineIndex) => {
                    pdf.text(line, x + statBoxWidth/2, yPosition + statBoxHeight + 5 + (lineIndex * 3), { align: 'center' });
                });
            });
            
            yPosition += statBoxHeight + 20;

            // Highlighted Analysis Section
            addText('Highlighted Analysis', 14, true);
            yPosition += 5;
            
            // Add border for analysis text
            const analysisHeight = Math.min(pageHeight - yPosition - margin, 80);
            pdf.setDrawColor(200, 200, 200);
            pdf.rect(margin, yPosition, contentWidth, analysisHeight);
            
            // Add the actual text content (without HTML highlighting for PDF)
            pdf.setFont('helvetica', 'normal');
            pdf.setFontSize(10);
            const analysisLines = pdf.splitTextToSize(highlightedText, contentWidth - 10);
            let textY = yPosition + 8;
            
            analysisLines.forEach(line => {
                if (textY > yPosition + analysisHeight - 5) {
                    // Text is too long for the box, truncate
                    pdf.text('... (content truncated)', margin + 5, textY);
                    return;
                }
                pdf.text(line, margin + 5, textY);
                textY += 4;
            });

            // Footer
            pdf.setFont('helvetica', 'normal');
            pdf.setFontSize(8);
            pdf.text('Generated by TextSense - AI Text Detection', pageWidth/2, pageHeight - 10, { align: 'center' });

            // Save the PDF
            pdf.save('textsense-analysis-report.pdf');
            console.log('PDF generated and saved successfully');

        } catch (error) {
            console.error('PDF generation error:', error);
            showError('Failed to generate PDF: ' + error.message);
        }
    }
    
    // File input change handler
    fileInput.addEventListener('change', function() {
        const file = this.files[0];
        if (file) {
            // Update file input label to show selected file
            const label = this.nextElementSibling;
            if (label && label.classList.contains('form-text')) {
                label.textContent = `Selected: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`;
            }
        }
    });
    
    // Text input character counter
    textInput.addEventListener('input', function() {
        const maxChars = MAX_CHARS;
        let charCount = this.value.length;
        if (charCount > maxChars) {
            this.value = this.value.substring(0, maxChars);
            charCount = maxChars;
            showError(`Text is too long. Maximum ${maxChars.toLocaleString()} characters allowed.`);
        }
        if (charCounter) {
            charCounter.textContent = `${charCount.toLocaleString()} / ${maxChars.toLocaleString()}`;
        }
    });
    
    // Tab switching animation
    const tabButtons = document.querySelectorAll('[data-bs-toggle="tab"]');
    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            // Clear forms when switching tabs
            textInput.value = '';
            fileInput.value = '';
            hideError();
            resultsSection.classList.add('d-none');
            
            // Reset file input label
            const label = fileInput.nextElementSibling;
            if (label && label.classList.contains('form-text')) {
                label.textContent = 'Supported formats: .txt, .md, .doc, .docx (Max 16MB)';
            }
        });
    });
    
    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + Enter to submit text form
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            if (document.activeElement === textInput) {
                textForm.dispatchEvent(new Event('submit'));
            }
        }
        
        // Escape to clear forms
        if (e.key === 'Escape') {
            textInput.value = '';
            fileInput.value = '';
            hideError();
            resultsSection.classList.add('d-none');
        }
    });
    
    // Auto-resize textarea
    textInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 400) + 'px';
    });
    
    // Floating tooltip so it isn't clipped by scroll container
    let floatingTooltipEl = null;
    function getOrCreateFloatingTooltip() {
        if (!floatingTooltipEl) {
            floatingTooltipEl = document.createElement('div');
            floatingTooltipEl.className = 'floating-prob-tooltip';
            document.body.appendChild(floatingTooltipEl);
        }
        return floatingTooltipEl;
    }

    function positionTooltipNearRect(tt, rect, label) {
        const padding = 8;
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        tt.textContent = label;
        tt.style.transform = 'translate(-9999px, -9999px)';
        tt.classList.add('visible');
        // Measure after content set
        const ttRect = tt.getBoundingClientRect();
        let x = rect.left + (rect.width - ttRect.width) / 2;
        let y = rect.top - ttRect.height - padding;
        // If above is out of view, place below
        if (y < padding) {
            y = rect.bottom + padding;
        }
        // Clamp horizontally
        if (x < padding) x = padding;
        if (x + ttRect.width > vw - padding) x = vw - padding - ttRect.width;
        // Clamp vertically
        if (y + ttRect.height > vh - padding) y = vh - padding - ttRect.height;
        tt.style.transform = `translate(${Math.round(x)}px, ${Math.round(y)}px)`;
    }

    function initializeTooltips() {
        const tt = getOrCreateFloatingTooltip();
        const highlights = document.querySelectorAll('.heatmap-highlight');
        const hide = () => { tt.classList.remove('visible'); };
        highlights.forEach(highlight => {
            const showHandler = () => {
                const label = highlight.getAttribute('data-probability') || '';
                const rect = highlight.getBoundingClientRect();
                positionTooltipNearRect(tt, rect, label);
            };
            highlight.addEventListener('mouseenter', showHandler);
            highlight.addEventListener('mousemove', showHandler);
            highlight.addEventListener('mouseleave', hide);
        });
        window.addEventListener('scroll', () => { if (tt.classList.contains('visible')) tt.classList.remove('visible'); }, true);
        window.addEventListener('resize', () => { if (tt.classList.contains('visible')) tt.classList.remove('visible'); });
    }
    
    // Call initialize tooltips after results are displayed
    const originalDisplayResults = displayResults;
    displayResults = function(data, textArg) {
        originalDisplayResults(data, textArg);
        setTimeout(initializeTooltips, 100);
    };
}); 