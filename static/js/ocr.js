(function () {
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('fileInput');
  const imageUrlInput = document.getElementById('imageUrl');
  const previewImg = document.getElementById('preview');
  const extractBtn = document.getElementById('extractBtn');
  const clearBtn = document.getElementById('clearBtn');
  const loading = document.getElementById('loading');
  const analyzing = document.getElementById('analyzing');
  const analysisSection = document.getElementById('analysisSection');
  const outputControls = document.getElementById('outputControls');
  const output = document.getElementById('ocrOutput');
  const copyBtn = document.getElementById('copyBtn');
  const downloadBtn = document.getElementById('downloadBtn');

  let currentFile = null;

  function showPreviewFromFile(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
      previewImg.src = e.target.result;
      analysisSection.style.display = 'block';
      
      // Smooth scroll to analysis section
      setTimeout(() => {
        analysisSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }, 100);
    };
    reader.readAsDataURL(file);
  }

  function showPreviewFromUrl(url) {
    previewImg.src = url;
    analysisSection.style.display = 'block';
    
    // Smooth scroll to analysis section
    setTimeout(() => {
      analysisSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, 100);
  }

  function clearAll() {
    currentFile = null;
    fileInput.value = '';
    imageUrlInput.value = '';
    previewImg.src = '';
    analysisSection.style.display = 'none';
    output.value = '';
    outputControls.style.display = 'none';
    analyzing.style.display = 'none';
  }

  function setLoading(isLoading) {
    if (isLoading) {
      loading.style.display = 'inline-block';
      loading.classList.add('show');
    } else {
      loading.style.display = 'none';
      loading.classList.remove('show');
    }
    extractBtn.disabled = isLoading;
  }

  function setAnalyzing(isAnalyzing) {
    if (isAnalyzing) {
      analyzing.style.display = 'flex';
      extractBtn.disabled = true;
      clearBtn.disabled = true;
    } else {
      analyzing.style.display = 'none';
      extractBtn.disabled = false;
      clearBtn.disabled = false;
    }
  }

  dropzone.addEventListener('click', () => fileInput.click());
  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      currentFile = e.dataTransfer.files[0];
      showPreviewFromFile(currentFile);
    }
  });

  // Paste image handler
  document.addEventListener('paste', async (e) => {
    const items = e.clipboardData && e.clipboardData.items;
    if (!items) return;
    for (const item of items) {
      if (item.type.indexOf('image') !== -1) {
        const file = item.getAsFile();
        if (file) {
          currentFile = file;
          showPreviewFromFile(currentFile);
        }
        break;
      }
    }
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files && fileInput.files[0]) {
      currentFile = fileInput.files[0];
      showPreviewFromFile(currentFile);
    }
  });

  clearBtn.addEventListener('click', clearAll);

  copyBtn.addEventListener('click', async () => {
    if (!output.value) return;
    try {
      await navigator.clipboard.writeText(output.value);
      copyBtn.textContent = 'Copied!';
      setTimeout(() => (copyBtn.textContent = 'Copy'), 1200);
    } catch {}
  });

  downloadBtn.addEventListener('click', () => {
    if (!output.value) return;
    const blob = new Blob([output.value], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'ocr.txt';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  });

  // Handle URL input
  imageUrlInput.addEventListener('input', () => {
    const urlVal = imageUrlInput.value.trim();
    if (urlVal && urlVal.match(/\.(jpeg|jpg|gif|png|webp)$/i)) {
      currentFile = null; // Clear file if URL is provided
      showPreviewFromUrl(urlVal);
    }
  });

  extractBtn.addEventListener('click', async () => {
    output.value = '';
    outputControls.style.display = 'none';
    
    const hasFile = !!currentFile;
    const urlVal = imageUrlInput.value.trim();
    if (!hasFile && !urlVal) {
      alert('Please upload/paste an image or enter an image URL.');
      return;
    }

    setAnalyzing(true);
    try {
      const form = new FormData();
      if (hasFile) {
        form.append('image', currentFile);
      } else {
        form.append('image_url', urlVal);
      }
      
      // Add selected language
      const languageSelect = document.getElementById('languageSelect');
      form.append('language', languageSelect.value);

      const resp = await fetch('/ocr', {
        method: 'POST',
        body: form,
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || 'OCR failed');
      
      output.value = data.text || '';
      
      // Show output controls if text was extracted
      if (data.text && data.text.trim()) {
        outputControls.style.display = 'flex';
      }
      
    } catch (err) {
      output.value = `Error: ${err.message || err}`;
    } finally {
      setAnalyzing(false);
    }
  });
})();


