// Image Generation JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Get DOM elements
    const promptInput = document.getElementById('promptInput');
    const negativePromptInput = document.getElementById('negativePromptInput');
    const aspectRatio = document.getElementById('aspectRatio');
    const numImages = document.getElementById('numImages');
    const inferenceSteps = document.getElementById('inferenceSteps');
    const stepsValue = document.getElementById('stepsValue');
    const safetyChecker = document.getElementById('safetyChecker');
    const promptOptimizer = document.getElementById('promptOptimizer');
    const generateBtn = document.getElementById('generateBtn');
    const clearBtn = document.getElementById('clearBtn');
    const generating = document.getElementById('generating');
    const generationProgress = document.getElementById('generationProgress');
    const resultsHeader = document.getElementById('resultsHeader');
    const imageResults = document.getElementById('imageResults');
    const downloadAllBtn = document.getElementById('downloadAllBtn');

    // Update steps value display
    inferenceSteps.addEventListener('input', function() {
        stepsValue.textContent = this.value;
    });

    // Generate button click handler
    generateBtn.addEventListener('click', async function() {
        const prompt = promptInput.value.trim();
        
        if (!prompt) {
            alert('Please enter a description for the image you want to generate.');
            promptInput.focus();
            return;
        }

        // Disable button and show loading
        generateBtn.disabled = true;
        generating.style.display = 'block';
        generationProgress.style.display = 'block';
        imageResults.innerHTML = '';
        resultsHeader.style.display = 'none';

        try {
            // Prepare form data
            const formData = new FormData();
            formData.append('prompt', prompt);
            formData.append('negative_prompt', negativePromptInput.value.trim());
            formData.append('aspect_ratio', aspectRatio.value);
            formData.append('num_images', numImages.value);
            formData.append('num_inference_steps', inferenceSteps.value);
            formData.append('enable_safety_checker', safetyChecker.checked);
            formData.append('enable_prompt_optimizer', promptOptimizer.checked);

            // Make API call
            const response = await fetch('/generate-image', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || `Server error: ${response.status}`);
            }

            // Display results
            displayImages(result);
            resultsHeader.style.display = 'flex';

        } catch (error) {
            console.error('Generation error:', error);
            alert(`Error generating image: ${error.message}`);
        } finally {
            // Re-enable button and hide loading
            generateBtn.disabled = false;
            generating.style.display = 'none';
            generationProgress.style.display = 'none';
        }
    });

    // Clear button click handler
    clearBtn.addEventListener('click', function() {
        promptInput.value = '';
        negativePromptInput.value = '';
        aspectRatio.value = '1:1';
        numImages.value = '1';
        inferenceSteps.value = '20';
        stepsValue.textContent = '20';
        safetyChecker.checked = true;
        promptOptimizer.checked = true;
        imageResults.innerHTML = '';
        resultsHeader.style.display = 'none';
        promptInput.focus();
    });

    // Download all button click handler
    downloadAllBtn.addEventListener('click', async function() {
        const images = imageResults.querySelectorAll('img');
        
        // Download images with a small delay to avoid overwhelming the browser
        for (let i = 0; i < images.length; i++) {
            const img = images[i];
            await downloadImage(img.src, `generated_image_${i + 1}.png`);
            // Small delay between downloads
            if (i < images.length - 1) {
                await new Promise(resolve => setTimeout(resolve, 500));
            }
        }
    });

    // Function to display generated images
    function displayImages(result) {
        imageResults.innerHTML = '';

        // Add prompt information section if enhancement was used
        if (result.enhanced_prompt && result.prompt_enhanced) {
            const promptInfoCard = document.createElement('div');
            promptInfoCard.className = 'col-12 mb-3';
            promptInfoCard.innerHTML = `
                <div class="card bg-light">
                    <div class="card-body">
                        <h6 class="card-title mb-2">
                            <i class="fas fa-magic text-primary me-2"></i>Prompt Enhancement Applied
                        </h6>
                        <div class="row">
                            <div class="col-md-6">
                                <small class="text-muted"><strong>Original:</strong></small>
                                <p class="small mb-2">${result.original_prompt}</p>
                            </div>
                            <div class="col-md-6">
                                <small class="text-muted"><strong>Enhanced:</strong></small>
                                <p class="small mb-0">${result.enhanced_prompt}</p>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            imageResults.appendChild(promptInfoCard);
        }

        // Handle different response formats
        let images = [];
        
        if (result.data && Array.isArray(result.data)) {
            // Qwen-Image response format
            images = result.data.filter(item => 
                item && typeof item === 'object' && item.url
            );
        } else if (result.images && Array.isArray(result.images)) {
            // Alternative format
            images = result.images;
        } else if (result.image_base64) {
            // Single image base64 format
            images = [{
                url: `data:image/png;base64,${result.image_base64}`,
                caption: 'Generated Image'
            }];
        }

        if (images.length === 0) {
            imageResults.innerHTML = `
                <div class="col-12">
                    <div class="alert alert-warning">
                        <i class="fas fa-exclamation-triangle me-2"></i>
                        No images were generated. Please try again with a different prompt.
                    </div>
                </div>
            `;
            return;
        }

        // Display each image
        images.forEach((imageData, index) => {
            const imageUrl = imageData.url || imageData;
            const caption = imageData.caption || `Generated Image ${index + 1}`;
            
            const colSize = images.length === 1 ? 'col-12' : 
                           images.length === 2 ? 'col-md-6' : 'col-md-6 col-lg-4';
            
            const imageCard = document.createElement('div');
            imageCard.className = `${colSize} mb-4`;
            imageCard.innerHTML = `
                <div class="card">
                    <div class="image-container" style="position: relative;">
                        <img src="${imageUrl}" class="card-img-top" alt="${caption}" 
                             style="width: 100%; height: auto; border-radius: 0.375rem 0.375rem 0 0;">
                        <div class="image-overlay" style="
                            position: absolute; 
                            top: 0; 
                            left: 0; 
                            right: 0; 
                            bottom: 0; 
                            background: rgba(0,0,0,0.7); 
                            display: none; 
                            align-items: center; 
                            justify-content: center;
                            border-radius: 0.375rem 0.375rem 0 0;
                        ">
                            <button class="btn btn-light btn-sm download-btn" data-image-url="${imageUrl}" data-filename="generated_image_${index + 1}.png">
                                <i class="fas fa-download me-1"></i>Download
                            </button>
                        </div>
                    </div>
                    <div class="card-body">
                        <p class="card-text small text-muted">${caption}</p>
                        <div class="d-flex justify-content-between">
                            <button class="btn btn-outline-primary btn-sm copy-prompt-btn">
                                <i class="fas fa-copy me-1"></i>Copy Prompt
                            </button>
                            <button class="btn btn-primary btn-sm download-single-btn" data-image-url="${imageUrl}" data-filename="generated_image_${index + 1}.png">
                                <i class="fas fa-download me-1"></i>Download
                            </button>
                        </div>
                    </div>
                </div>
            `;
            
            imageResults.appendChild(imageCard);

            // Add hover effect for overlay
            const imageContainer = imageCard.querySelector('.image-container');
            const overlay = imageCard.querySelector('.image-overlay');
            
            imageContainer.addEventListener('mouseenter', () => {
                overlay.style.display = 'flex';
            });
            
            imageContainer.addEventListener('mouseleave', () => {
                overlay.style.display = 'none';
            });

            // Add click handlers for download buttons
            const downloadBtns = imageCard.querySelectorAll('.download-btn, .download-single-btn');
            downloadBtns.forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    const imageUrl = btn.getAttribute('data-image-url');
                    const filename = btn.getAttribute('data-filename');
                    await downloadImage(imageUrl, filename);
                });
            });

            // Add click handler for copy prompt button
            const copyPromptBtn = imageCard.querySelector('.copy-prompt-btn');
            copyPromptBtn.addEventListener('click', () => {
                // Copy the original prompt, not the enhanced one
                const promptToCopy = result.original_prompt || promptInput.value;
                copyToClipboard(promptToCopy);
                // Visual feedback
                const originalText = copyPromptBtn.innerHTML;
                copyPromptBtn.innerHTML = '<i class="fas fa-check me-1"></i>Copied!';
                setTimeout(() => {
                    copyPromptBtn.innerHTML = originalText;
                }, 2000);
            });
        });
    }

    // Function to download image
    async function downloadImage(imageUrl, filename) {
        try {
            // Fetch the image as a blob
            const response = await fetch(imageUrl);
            if (!response.ok) throw new Error('Failed to fetch image');
            
            const blob = await response.blob();
            
            // Create a download link
            const link = document.createElement('a');
            const url = window.URL.createObjectURL(blob);
            link.href = url;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            
            // Clean up
            document.body.removeChild(link);
            window.URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Download failed:', error);
            alert('Download failed. Please try right-clicking the image and selecting "Save As".');
        }
    }

    // Function to copy text to clipboard
    function copyToClipboard(text) {
        navigator.clipboard.writeText(text).catch(err => {
            console.error('Failed to copy text: ', err);
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = text;
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
        });
    }

    // Add enter key support for prompt input
    promptInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            generateBtn.click();
        }
    });

    // Focus on prompt input when page loads
    promptInput.focus();

    // Add example prompts functionality
    const examplePrompts = [
        "a beautiful sunset over mountains, digital art style",
        "a cozy cabin in the forest, warm lighting, photorealistic",
        "futuristic city skyline at night, neon lights, cyberpunk style",
        "a magical forest with glowing mushrooms, fantasy art",
        "portrait of a wise old wizard, oil painting style",
        "a serene lake with mountains in the background, landscape photography",
        "a cute robot in a garden, cartoon illustration style"
    ];

    // Add example prompts to the page (optional feature)
    function addExamplePrompts() {
        const examplesContainer = document.createElement('div');
        examplesContainer.className = 'mb-3';
        examplesContainer.innerHTML = `
            <label class="form-label">
                <i class="fas fa-lightbulb me-2"></i>Example Prompts
            </label>
            <div class="d-flex flex-wrap gap-2">
                ${examplePrompts.map(prompt => `
                    <button type="button" class="btn btn-outline-secondary btn-sm example-prompt" data-prompt="${prompt}">
                        ${prompt.length > 30 ? prompt.substring(0, 30) + '...' : prompt}
                    </button>
                `).join('')}
            </div>
        `;

        // Insert after the prompt input
        promptInput.parentNode.insertBefore(examplesContainer, promptInput.parentNode.children[2]);

        // Add click handlers for example prompts
        examplesContainer.querySelectorAll('.example-prompt').forEach(btn => {
            btn.addEventListener('click', () => {
                promptInput.value = btn.getAttribute('data-prompt');
                promptInput.focus();
            });
        });
    }

    // Uncomment to add example prompts
    // addExamplePrompts();
});
