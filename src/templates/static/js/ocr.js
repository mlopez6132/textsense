(function () {
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('fileInput');
  const imageUrlInput = document.getElementById('imageUrl');
  const previewImg = document.getElementById('preview');
  const extractBtn = document.getElementById('extractBtn');
  const clearBtn = document.getElementById('clearBtn');
  const analyzing = document.getElementById('analyzing');
  const analysisSection = document.getElementById('analysisSection');
  const outputControls = document.getElementById('outputControls');
  const output = document.getElementById('ocrOutput');
  const copyBtn = document.getElementById('copyBtn');
  const downloadBtn = document.getElementById('downloadBtn');
  const errorSection = document.getElementById('errorSection');
  const errorMessage = document.getElementById('errorMessage');

  let currentFile = null;

  function showError(msg) {
    if (errorMessage) errorMessage.textContent = msg;
    if (errorSection) errorSection.classList.remove('d-none');
  }

  function hideError() {
    if (errorSection) errorSection.classList.add('d-none');
  }

  function showPreviewFromFile(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
      previewImg.src = e.target.result;
      analysisSection.style.display = 'block';

      setTimeout(() => {
        analysisSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }, 100);
    };
    reader.readAsDataURL(file);
  }

  function showPreviewFromUrl(url) {
    previewImg.src = url;
    analysisSection.style.display = 'block';

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
    hideError();
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
    } catch {
      showError('Failed to copy text to clipboard.');
    }
  });

  downloadBtn.addEventListener('click', () => {
    if (!output.value) return;
    const blob = new Blob([output.value], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'textsense-ocr.txt';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  });

  imageUrlInput.addEventListener('input', () => {
    const urlVal = imageUrlInput.value.trim();
    if (urlVal && urlVal.match(/\.(jpeg|jpg|gif|png|webp)$/i)) {
      currentFile = null;
      showPreviewFromUrl(urlVal);
    }
  });

  extractBtn.addEventListener('click', async () => {
    output.value = '';
    outputControls.style.display = 'none';

    const hasFile = !!currentFile;
    const urlVal = imageUrlInput.value.trim();
    if (!hasFile && !urlVal) {
      showError('Please upload/paste an image or enter an image URL.');
      return;
    }

    hideError();
    setAnalyzing(true);
    try {
      const form = new FormData();
      if (hasFile) {
        form.append('image', currentFile);
      } else {
        form.append('image_url', urlVal);
      }

      const languageSelect = document.getElementById('languageSelect');
      form.append('language', languageSelect.value);

      const resp = await fetch('/ocr', {
        method: 'POST',
        body: form,
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || 'OCR failed');

      output.value = data.text || '';

      if (data.text && data.text.trim()) {
        outputControls.style.display = 'flex';
      }

    } catch (err) {
      showError(err.message || 'OCR failed. Please try again.');
    } finally {
      setAnalyzing(false);
    }
  });
})();
