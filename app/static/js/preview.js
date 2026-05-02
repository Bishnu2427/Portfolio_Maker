// ============================================================
//  PortfolioForge — Preview Page
// ============================================================

let previewPort = null;

document.addEventListener('DOMContentLoaded', () => {
  loadPortfolio();
});

async function loadPortfolio() {
  try {
    const res = await fetch(`/api/portfolio/${PORTFOLIO_ID}`);
    const data = await res.json();
    if (data.error) { showError(data.error); return; }

    previewPort = data.port;

    if (previewPort) {
      const url = `http://localhost:${previewPort}`;
      document.getElementById('preview-url-text').textContent = url;
      loadIframe(url);
    } else {
      showError('Preview server not running. Please regenerate your portfolio.');
    }

    if (data.status === 'deployed' && data.pages_url) {
      showDeployResult(data.github_url, data.pages_url);
    }
  } catch (err) {
    showError('Failed to load portfolio details.');
  }
}

function loadIframe(url) {
  const iframe = document.getElementById('preview-iframe');
  const loading = document.getElementById('iframe-loading');

  iframe.onload = () => { loading.style.display = 'none'; };
  iframe.src = url;

  // Fallback: hide loading after 6s
  setTimeout(() => { loading.style.display = 'none'; }, 6000);
}

// ---- Device Views ----
function setDevice(mode) {
  const iframe = document.getElementById('preview-iframe');
  document.querySelectorAll('.device-btn').forEach(b => b.classList.remove('active'));
  event.currentTarget.classList.add('active');

  iframe.classList.remove('tablet-view', 'mobile-view');
  if (mode === 'tablet') iframe.classList.add('tablet-view');
  else if (mode === 'mobile') iframe.classList.add('mobile-view');
}

// ---- Modification ----
function setModPrompt(text) {
  document.getElementById('mod-prompt').value = text;
  document.getElementById('mod-prompt').focus();
}

async function applyModification() {
  const prompt = document.getElementById('mod-prompt').value.trim();
  if (!prompt) { showToast('Please describe what you want to change', 'warning'); return; }

  const btn = document.getElementById('apply-btn');
  btn.disabled = true;
  btn.textContent = 'Applying changes…';

  try {
    const res = await fetch('/api/process/modify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ portfolio_id: PORTFOLIO_ID, prompt }),
    });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error);

    showToast('Changes applied!', 'success');
    document.getElementById('mod-prompt').value = '';
    setTimeout(refreshPreview, 500);
  } catch (err) {
    showToast(err.message || 'Failed to apply changes', 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `
      <svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16"><path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"/></svg>
      Apply Changes`;
  }
}

// ---- Refresh ----
function refreshPreview() {
  const iframe = document.getElementById('preview-iframe');
  const loading = document.getElementById('iframe-loading');
  loading.style.display = 'flex';
  iframe.src = iframe.src;
}

function openInNewTab() {
  if (previewPort) {
    window.open(`http://localhost:${previewPort}`, '_blank');
  }
}

// ---- Deploy ----
async function deployToGitHub() {
  const token = document.getElementById('github-token').value.trim();
  const repo = document.getElementById('repo-name').value.trim();

  if (!token) { showToast('Please enter your GitHub token', 'warning'); return; }
  if (!repo) { showToast('Please enter a repository name', 'warning'); return; }

  const btn = document.getElementById('deploy-btn');
  btn.disabled = true;
  btn.textContent = 'Deploying…';

  try {
    const res = await fetch('/api/deploy/github', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ portfolio_id: PORTFOLIO_ID, github_token: token, repo_name: repo }),
    });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error);

    showDeployResult(data.repo_url, data.pages_url);
    document.getElementById('portfolio-status').className = 'status-badge status-deployed';
    document.getElementById('portfolio-status').textContent = 'Deployed';
    showToast('Deployed to GitHub Pages!', 'success');
  } catch (err) {
    showToast(err.message || 'Deployment failed', 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `
      <svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16"><path fill-rule="evenodd" d="M10 0C4.477 0 0 4.484 0 10.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0110 4.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.203 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0020 10.017C20 4.484 15.522 0 10 0z" clip-rule="evenodd"/></svg>
      Deploy to GitHub Pages`;
  }
}

function showDeployResult(repoUrl, pagesUrl) {
  const result = document.getElementById('deploy-result');
  const urls = document.getElementById('deploy-urls');
  urls.innerHTML = `
    <a href="${repoUrl}" target="_blank">View Repository →</a>
    <a href="${pagesUrl}" target="_blank">Live Site: ${pagesUrl} →</a>
  `;
  result.style.display = 'block';
}

// ---- Toast ----
function showToast(msg, type = 'info') {
  const colors = { success: '#10b981', error: '#ef4444', warning: '#f59e0b', info: '#06b6d4' };
  const toast = document.createElement('div');
  toast.style.cssText = `
    position:fixed;bottom:24px;right:24px;z-index:9999;
    background:${colors[type] || colors.info};color:#fff;
    padding:12px 20px;border-radius:8px;font-size:.9rem;
    font-weight:600;box-shadow:0 4px 20px rgba(0,0,0,.4);
    font-family:'Inter',sans-serif;
  `;
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

function showError(msg) {
  document.getElementById('iframe-loading').innerHTML = `
    <div style="text-align:center;color:#9a9ab0;">
      <div style="font-size:2rem;margin-bottom:12px">⚠️</div>
      <p>${msg}</p>
      <a href="/create" style="color:#7c3aed;text-decoration:none;margin-top:12px;display:inline-block">← Create New Portfolio</a>
    </div>
  `;
}
