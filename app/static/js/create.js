// ============================================================
//  PortfolioForge — Create Page
// ============================================================

let currentStep = 1;
let portfolioId = null;

// ---- Step Navigation ----
function goStep(n) {
  if (n === 2 && !validateStep1()) return;
  document.getElementById(`step-${currentStep}`).classList.remove('active');
  document.getElementById(`stp-${currentStep}`).classList.remove('active');
  if (n > currentStep) document.getElementById(`stp-${currentStep}`).classList.add('done');
  currentStep = n;
  document.getElementById(`step-${n}`).classList.add('active');
  document.getElementById(`stp-${n}`).classList.add('active');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function validateStep1() {
  const cv = document.getElementById('cv-input').files[0];
  if (!cv) {
    showToast('Please upload your CV/Resume first', 'error');
    return false;
  }
  return true;
}

// ---- File Uploads ----
document.addEventListener('DOMContentLoaded', () => {
  setupDropZone('cv-drop-zone', 'cv-input', 'cv-name', null);
  setupDropZone('photo-drop-zone', 'photo-input', null, 'photo-preview');
  setupStyleSelector();
  setupToneSelector();
});

function setupDropZone(zoneId, inputId, nameId, previewId) {
  const zone = document.getElementById(zoneId);
  const input = document.getElementById(inputId);
  if (!zone || !input) return;

  zone.addEventListener('click', (e) => {
    if (e.target === zone || e.target.closest('.upload-icon') || e.target.closest('.upload-text')) {
      input.click();
    }
  });
  zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', (e) => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    const files = e.dataTransfer.files;
    if (files.length) {
      input.files = files;
      handleFileChange(input, nameId, previewId, zone);
    }
  });
  input.addEventListener('change', () => handleFileChange(input, nameId, previewId, zone));
}

function handleFileChange(input, nameId, previewId, zone) {
  const file = input.files[0];
  if (!file) return;
  zone.classList.add('has-file');

  if (nameId) {
    const nameEl = document.getElementById(nameId);
    nameEl.textContent = `✓ ${file.name} (${(file.size / 1024).toFixed(0)} KB)`;
    nameEl.style.display = 'block';
  }

  if (previewId) {
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = document.getElementById(previewId);
      const wrap = document.getElementById('photo-preview-wrap');
      const content = document.getElementById('photo-upload-content');
      img.src = e.target.result;
      wrap.style.display = 'block';
      content.style.display = 'none';
    };
    reader.readAsDataURL(file);
  }
}

// ---- Style Selector ----
function setupStyleSelector() {
  document.querySelectorAll('.style-opt').forEach(opt => {
    opt.addEventListener('click', () => {
      document.querySelectorAll('.style-opt').forEach(o => o.classList.remove('selected'));
      opt.classList.add('selected');
      opt.querySelector('input').checked = true;
    });
  });
  // Default select first
  const first = document.querySelector('.style-opt');
  if (first) first.classList.add('selected');
}

// ---- Tone Selector ----
function setupToneSelector() {
  document.querySelectorAll('.tone-opt').forEach(opt => {
    opt.addEventListener('click', () => {
      document.querySelectorAll('.tone-opt').forEach(o => o.classList.remove('selected'));
      opt.classList.add('selected');
      opt.querySelector('input').checked = true;
    });
  });
}

// ---- Example Chips ----
function addExample(text) {
  const ta = document.getElementById('prompt-input');
  const current = ta.value.trim();
  ta.value = current ? `${current}. ${text}` : text;
  ta.focus();
}

// ---- Form Submit ----
async function submitForm() {
  if (!validateStep1()) { goStep(1); return; }

  const form = document.getElementById('portfolio-form');
  const fd = new FormData(form);

  const tone = document.querySelector('input[name="tone"]:checked')?.value || 'professional';
  const existingPrompt = fd.get('prompt') || '';
  if (tone && tone !== 'professional') {
    fd.set('prompt', existingPrompt ? `${existingPrompt}. Tone: ${tone}` : `Tone: ${tone}`);
  }

  showProcessingOverlay();

  try {
    const res = await fetch('/api/process/upload', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error || 'Upload failed');
    portfolioId = data.portfolio_id;
    startGeneration(portfolioId);
  } catch (err) {
    hideProcessingOverlay();
    showToast(err.message, 'error');
  }
}

function startGeneration(id) {
  const source = new EventSource(`/api/process/generate/${id}`);

  source.onmessage = (e) => {
    const data = JSON.parse(e.data);

    if (data.error) {
      source.close();
      hideProcessingOverlay();
      showToast(data.error, 'error');
      return;
    }

    if (data.progress !== undefined) {
      updateProgress(data.progress, data.message, data.step);
    }

    if (data.done) {
      source.close();
      setTimeout(() => {
        window.location.href = data.redirect;
      }, 800);
    }
  };

  source.onerror = () => {
    source.close();
    hideProcessingOverlay();
    showToast('Generation failed. Please try again.', 'error');
  };
}

// ---- Processing Overlay ----
function showProcessingOverlay() {
  document.getElementById('processing-overlay').style.display = 'flex';
}

function hideProcessingOverlay() {
  document.getElementById('processing-overlay').style.display = 'none';
}

function updateProgress(pct, msg, step) {
  document.getElementById('progress-bar').style.width = `${pct}%`;
  document.getElementById('progress-pct').textContent = `${pct}%`;
  if (msg) document.getElementById('processing-msg').textContent = msg;

  // Mark steps
  const stepMap = { 1: 'ps-1', 2: 'ps-2', 3: 'ps-3', 4: 'ps-4', 5: 'ps-5', 6: 'ps-6' };
  for (let i = 1; i <= 6; i++) {
    const el = document.getElementById(`ps-${i}`);
    if (!el) continue;
    el.classList.remove('active', 'done');
    if (i < step) el.classList.add('done');
    else if (i === step) el.classList.add('active');
  }
}

// ---- Toast ----
function showToast(msg, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = msg;
  toast.style.cssText = `
    position: fixed; bottom: 24px; right: 24px; z-index: 9999;
    background: ${type === 'error' ? '#ef4444' : '#10b981'};
    color: #fff; padding: 12px 20px; border-radius: 8px;
    font-size: .9rem; font-weight: 600; box-shadow: 0 4px 20px rgba(0,0,0,.4);
    animation: slideIn .3s ease;
  `;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}
