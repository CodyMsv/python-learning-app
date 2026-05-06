// CodeMirror 5 editor setup
let editor = null;
let starterCode = '# Write your Python code here\n';

function initEditor(initialCode) {
  const wrapper = document.getElementById('editor-wrapper');
  if (!wrapper) return;
  starterCode = initialCode || starterCode;
  editor = CodeMirror(wrapper, {
    value: starterCode,
    mode: 'python',
    theme: 'dracula',
    lineNumbers: true,
    indentUnit: 4,
    tabSize: 4,
    indentWithTabs: false,
    lineWrapping: true,
    autofocus: false,
    extraKeys: {
      'Ctrl-Enter': () => runCode(),
      'Tab': cm => {
        if (cm.somethingSelected()) cm.indentSelection('add');
        else cm.replaceSelection('    ', 'end');
      }
    }
  });
  // Make editor fill container
  editor.setSize('100%', '100%');
}

function getCode() {
  return editor ? editor.getValue() : '';
}

function setCode(code) {
  if (editor) {
    editor.setValue(code);
    editor.clearHistory();
  }
}

function resetEditor() {
  setCode(starterCode);
  clearOutput();
}

function copyEditorCode() {
  const code = getCode();
  navigator.clipboard.writeText(code).then(() => showToast('📋 Code copied!', 'info'));
}

function copyCode(btn) {
  const pre = btn.closest('.code-block-wrap').querySelector('pre code');
  if (pre) {
    navigator.clipboard.writeText(pre.textContent).then(() => {
      btn.textContent = '✓';
      setTimeout(() => { btn.textContent = '📋'; }, 1500);
    });
  }
}

function tryInEditor(btn) {
  const pre = btn.closest('.code-block-wrap').querySelector('pre code');
  if (pre) {
    setCode(pre.textContent.trimEnd());
    switchTab('playground');
    showToast('▶ Code loaded into editor — click Run to execute!', 'info');
  }
}

function toggleSidebar() {
  const sidebar = document.getElementById('lesson-sidebar');
  const openBtn = document.getElementById('sidebar-open-btn');
  if (!sidebar) return;
  const isOpen = sidebar.classList.contains('open');
  if (isOpen) {
    sidebar.classList.remove('open');
    sidebar.style.transform = '';
    if (openBtn) openBtn.style.display = 'flex';
  } else {
    sidebar.classList.add('open');
    sidebar.style.transform = 'translateX(0)';
    if (openBtn) openBtn.style.display = 'none';
  }
}

function toggleSidebarModule(modId) {
  const lessons = document.getElementById('sidebar-lessons-' + modId);
  const arrow = document.getElementById('arrow-' + modId);
  if (!lessons) return;
  const isOpen = lessons.style.display !== 'none';
  lessons.style.display = isOpen ? 'none' : 'flex';
  lessons.style.flexDirection = 'column';
  if (arrow) arrow.style.transform = isOpen ? '' : 'rotate(90deg)';
}

document.addEventListener('DOMContentLoaded', () => {
  // Open the sidebar module containing the active lesson
  const activeLesson = document.querySelector('.sidebar-lesson--active');
  if (activeLesson) {
    const moduleDiv = activeLesson.closest('[id^="sidebar-lessons-"]');
    if (moduleDiv) {
      moduleDiv.style.display = 'flex';
      moduleDiv.style.flexDirection = 'column';
      const modId = moduleDiv.id.replace('sidebar-lessons-', '');
      const arrow = document.getElementById('arrow-' + modId);
      if (arrow) arrow.style.transform = 'rotate(90deg)';
    }
  }
  // Init editor with default starter code
  initEditor('# Write your Python code here\nprint("Hello, Python!")\n');
});
