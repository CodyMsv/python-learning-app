// Server-side Python runner — replaces Pyodide
const pyState = {
  ready: true,
  capturedOutput: '',
  capturedStderr: ''
};

function appendOutput(text, type) {
  const out = document.getElementById('output');
  if (!out) return;
  const placeholder = out.querySelector('.output-placeholder');
  if (placeholder) placeholder.remove();
  const span = document.createElement('span');
  span.className = 'output-' + type;
  span.textContent = text;
  out.appendChild(span);
  out.scrollTop = out.scrollHeight;
  if (type === 'stdout') pyState.capturedOutput += text;
  if (type === 'stderr') pyState.capturedStderr += text;
}

function clearOutput() {
  const out = document.getElementById('output');
  if (!out) return;
  out.innerHTML = '<span class="output-placeholder">Run your code to see output here...</span>';
  pyState.capturedOutput = '';
  pyState.capturedStderr = '';
}

function setStatus(state) {
  const dot = document.getElementById('status-dot');
  const label = document.getElementById('status-label');
  if (!dot || !label) return;
  dot.className = 'status-dot status-dot--' + state;
  if (state === 'ready') { label.textContent = 'Python Ready'; }
  else if (state === 'running') { label.textContent = 'Running...'; }
  else if (state === 'error') { label.textContent = 'Error'; }
}

async function runCode() {
  const code = getCode();
  if (!code.trim()) return;

  const runBtn = document.getElementById('run-btn');
  if (runBtn) { runBtn.disabled = true; runBtn.textContent = '⏳ Running...'; }
  setStatus('running');
  clearOutput();
  appendOutput('>>> Running...\n', 'info');

  const tests = window._currentExercise ? window._currentExercise.tests : [];

  try {
    const resp = await fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, tests })
    });
    const result = await resp.json();

    // Clear the "Running..." line
    clearOutput();

    if (result.stdout) appendOutput(result.stdout, 'stdout');
    if (result.stderr) appendOutput(result.stderr, 'stderr');
    if (!result.stdout && !result.stderr) appendOutput('(no output)\n', 'info');

    if (window._currentExercise) {
      evaluateTests(window._currentExercise, result.tests || []);
    }
  } catch (e) {
    clearOutput();
    appendOutput('Network error: ' + e.message + '\n', 'stderr');
  }

  if (runBtn) {
    runBtn.disabled = false;
    runBtn.innerHTML = '▶ Run Code <kbd>Ctrl+Enter</kbd>';
  }
  setStatus('ready');
}

document.addEventListener('DOMContentLoaded', () => {
  setStatus('ready');
  // Hide loading overlay immediately (no Pyodide to load)
  const overlay = document.getElementById('py-loading-overlay');
  if (overlay) overlay.style.display = 'none';
  const runBtn = document.getElementById('run-btn');
  if (runBtn) runBtn.disabled = false;
});
