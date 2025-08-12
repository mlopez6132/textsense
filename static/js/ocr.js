(function () {
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('fileInput');
  const imageUrlInput = document.getElementById('imageUrl');
  const previewImg = document.getElementById('preview');
  const extractBtn = document.getElementById('extractBtn');
  const clearBtn = document.getElementById('clearBtn');
  const loading = document.getElementById('loading');
  const output = document.getElementById('ocrOutput');
  const copyBtn = document.getElementById('copyBtn');
  const downloadBtn = document.getElementById('downloadBtn');

  let currentFile = null;

  function showPreviewFromFile(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
      previewImg.src = e.target.result;
      previewImg.style.display = 'block';
    };
    reader.readAsDataURL(file);
  }

  function clearAll() {
    currentFile = null;
    fileInput.value = '';
    imageUrlInput.value = '';
    previewImg.src = '';
    previewImg.style.display = 'none';
    output.value = '';
  }

  function setLoading(isLoading) {
    if (isLoading) loading.classList.add('show');
    else loading.classList.remove('show');
    extractBtn.disabled = isLoading;
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

  extractBtn.addEventListener('click', async () => {
    output.value = '';
    setLoading(true);
    try {
      const form = new FormData();
      if (currentFile) {
        form.append('image', currentFile);
      } else if (imageUrlInput.value.trim()) {
        form.append('image_url', imageUrlInput.value.trim());
      } else {
        alert('Please upload/paste an image or enter an image URL.');
        return;
      }

      const resp = await fetch('/ocr', {
        method: 'POST',
        body: form,
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || 'OCR failed');
      output.value = data.text || '';
    } catch (err) {
      output.value = `Error: ${err.message || err}`;
    } finally {
      setLoading(false);
    }
  });
})();


