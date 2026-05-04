// Main lesson controller — tabs, exercises, quiz logic, completion
window._currentExercise = null;
window._currentSolution = null;
let _hintIndex = {};
let _quizAnswered = {};
let _exercisePassed = {};
let _lessonCompleted = (typeof CURRENT_STATUS !== 'undefined' && CURRENT_STATUS === 'completed');

// ---------------------------------------------------------------------------
// Tab switching
// ---------------------------------------------------------------------------
function switchTab(tabName) {
  document.querySelectorAll('.tab-content').forEach(el => { el.style.display = 'none'; });
  document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('tab-btn--active'));
  const content = document.getElementById('tab-' + tabName);
  if (content) content.style.display = 'block';
  const btn = document.querySelector(`[data-tab="${tabName}"]`);
  if (btn) btn.classList.add('tab-btn--active');
  // Refresh CodeMirror when its tab becomes visible
  if ((tabName === 'exercises' || tabName === 'playground') && editor) {
    setTimeout(() => editor.refresh(), 50);
  }
}

// ---------------------------------------------------------------------------
// Exercise loading and evaluation
// ---------------------------------------------------------------------------
function loadExerciseById(exerciseId) {
  const ex = LESSON_DATA.exercises.find(e => e.id === exerciseId);
  if (ex) loadExercise(ex.id, ex.starter_code, ex.tests, ex.solution);
}

function showHintById(exerciseId) {
  const ex = LESSON_DATA.exercises.find(e => e.id === exerciseId);
  if (ex) showHint(exerciseId, ex.hints);
}

function loadExercise(exerciseId, starterCodeStr, tests, solution) {
  window._currentExercise = { id: exerciseId, tests: tests };
  window._currentSolution = solution;
  starterCode = starterCodeStr;
  setCode(starterCodeStr);
  clearOutput();
  // Show solution button
  const solBtn = document.getElementById('show-solution-btn');
  if (solBtn) solBtn.style.display = 'inline-flex';
  // Show exercise mode bar
  const modeBar = document.getElementById('exercise-mode-bar');
  const modeLabel = document.getElementById('exercise-mode-label');
  if (modeBar) modeBar.style.display = 'flex';
  if (modeLabel) {
    const card = document.getElementById('ex-card-' + exerciseId);
    const title = card ? card.querySelector('.exercise-title').textContent : exerciseId;
    modeLabel.textContent = '💻 Exercise: ' + title;
  }
  // Switch to exercises tab if not already there, then scroll to exercise
  switchTab('exercises');
  const card = document.getElementById('ex-card-' + exerciseId);
  if (card) card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  // Reset test indicators for this exercise
  resetTestUI(exerciseId, tests);
  showToast('Exercise loaded into editor — click Run Code to test!', 'info');
}

function clearExerciseMode() {
  window._currentExercise = null;
  window._currentSolution = null;
  const modeBar = document.getElementById('exercise-mode-bar');
  if (modeBar) modeBar.style.display = 'none';
  const solBtn = document.getElementById('show-solution-btn');
  if (solBtn) solBtn.style.display = 'none';
  setCode('# Write your Python code here\n');
  clearOutput();
}

function showSolution() {
  if (!window._currentSolution) return;
  if (!confirm('Show the solution? Try to solve it yourself first!')) return;
  setCode(window._currentSolution);
  showToast('Solution loaded. Study it, then try writing it yourself!', 'warning');
}

function resetTestUI(exerciseId, tests) {
  tests.forEach((t, i) => {
    const el = document.getElementById(`test-${exerciseId}-${i}`);
    if (el) {
      el.className = 'test-item test-item--pending';
      const icon = el.querySelector('.test-icon');
      if (icon) icon.textContent = '○';
    }
  });
}

async function evaluateTests(exercise, serverTestResults) {
  const { id: exerciseId, tests } = exercise;
  let allPassed = true;

  for (let i = 0; i < tests.length; i++) {
    const el = document.getElementById(`test-${exerciseId}-${i}`);
    const passed = serverTestResults[i] ? serverTestResults[i].passed : false;

    if (el) {
      el.className = 'test-item test-item--' + (passed ? 'pass' : 'fail');
      const icon = el.querySelector('.test-icon');
      if (icon) icon.textContent = passed ? '✓' : '✗';
    }
    if (!passed) allPassed = false;
  }

  // Log exercise attempt
  const code = getCode();
  fetch('/api/progress/exercise', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lesson_id: LESSON_ID, exercise_id: exerciseId, code, passed: allPassed })
  });

  if (allPassed) {
    _exercisePassed[exerciseId] = true;
    const badge = document.getElementById('ex-badge-' + exerciseId);
    if (badge) {
      badge.textContent = '✅ Passed';
      badge.className = 'exercise-badge exercise-badge--passed';
    }
    showToast('✅ Exercise passed! Great job!', 'success');
    // Mark lesson in progress
    fetch('/api/progress/lesson', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lesson_id: LESSON_ID, status: 'in_progress', xp: 0 })
    });
    checkLessonComplete();
  } else {
    showToast('Not quite — check the failed tests and try again.', 'warning');
  }
}

// ---------------------------------------------------------------------------
// Quiz logic
// ---------------------------------------------------------------------------
function submitQuiz(questionId, selectedIndex, correctIndex, explanation) {
  const isCorrect = selectedIndex === correctIndex;
  _quizAnswered[questionId] = { selected: selectedIndex, correct: isCorrect };

  const qEl = document.getElementById('quiz-q-' + questionId);
  if (!qEl) return;
  const options = qEl.querySelectorAll('.quiz-option');
  options.forEach((btn, idx) => {
    btn.disabled = true;
    if (idx === correctIndex) btn.classList.add('quiz-option--correct');
    else if (idx === selectedIndex && !isCorrect) btn.classList.add('quiz-option--wrong');
  });

  const expEl = document.getElementById('quiz-exp-' + questionId);
  if (expEl) expEl.style.display = 'block';

  // Log quiz answer
  fetch('/api/progress/quiz', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lesson_id: LESSON_ID, question_id: questionId, selected_option: selectedIndex, is_correct: isCorrect })
  });

  if (isCorrect) showToast('✅ Correct!', 'success');
  else showToast('❌ Not quite — see the explanation below.', 'warning');

  // Check if all quiz questions answered
  const allQuestions = document.querySelectorAll('.quiz-question');
  const answeredCount = Object.keys(_quizAnswered).length;
  if (answeredCount >= allQuestions.length) {
    const row = document.getElementById('quiz-complete-row');
    if (row) row.style.display = 'block';
    checkLessonComplete();
  }
}

// ---------------------------------------------------------------------------
// Lesson completion
// ---------------------------------------------------------------------------
function checkLessonComplete() {
  const exercises = LESSON_DATA.exercises || [];
  const quizQuestions = LESSON_DATA.quiz || [];

  const allExercisesPassed = exercises.every(ex =>
    _exercisePassed[ex.id] || PASSED_EXERCISES[ex.id]
  );
  const allQuizAnswered = quizQuestions.every(q =>
    _quizAnswered[q.id] !== undefined || ANSWERED_QUIZ[q.id] !== undefined
  );

  if (allExercisesPassed && allQuizAnswered) {
    markLessonComplete();
    return;
  }

  // Tell the user exactly what is still missing
  const missing = [];
  if (!allExercisesPassed) {
    const unpassed = exercises.filter(ex => !_exercisePassed[ex.id] && !PASSED_EXERCISES[ex.id]);
    missing.push(`Complete ${unpassed.length} exercise${unpassed.length > 1 ? 's' : ''} in the Exercises tab`);
  }
  if (!allQuizAnswered) {
    missing.push('Answer all questions in the Quiz tab');
  }
  showToast('Not done yet: ' + missing.join(' and ') + '.', 'warning');
}

async function markLessonComplete() {
  if (_lessonCompleted) return;
  _lessonCompleted = true;
  const xp = 50;
  const res = await fetch('/api/progress/lesson', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lesson_id: LESSON_ID, status: 'completed', xp })
  });
  if (!res.ok) return;

  // Check for new badges
  const badgeRes = await fetch('/api/badges/check', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
  const badgeData = await badgeRes.json();
  if (badgeData.new_badges && badgeData.new_badges.length > 0) {
    badgeData.new_badges.forEach(b => {
      showToast(`${b.icon} Badge unlocked: ${b.name}!`, 'badge');
    });
  }

  // Update status badge in header
  const statusBadge = document.getElementById('lesson-status-badge');
  if (statusBadge) {
    statusBadge.textContent = '✅ Completed';
    statusBadge.className = 'lesson-status-badge lesson-status--completed';
  }

  // Fire confetti
  confetti({ particleCount: 120, spread: 80, origin: { y: 0.5 } });

  // Show completion modal
  const modal = document.getElementById('completion-modal');
  const xpEl = document.getElementById('modal-xp');
  if (modal) {
    if (xpEl) xpEl.textContent = `+${xp} XP earned!`;
    modal.style.display = 'flex';
  }

  showToast(`🎉 Lesson complete! +${xp} XP`, 'xp');
  updateProgressBar();
}

function closeModal() {
  const modal = document.getElementById('completion-modal');
  if (modal) modal.style.display = 'none';
}

// ---------------------------------------------------------------------------
// Hints
// ---------------------------------------------------------------------------
function showHint(exerciseId, hints) {
  if (!_hintIndex[exerciseId]) _hintIndex[exerciseId] = 0;
  const idx = _hintIndex[exerciseId];
  const hintEl = document.getElementById('hint-text-' + exerciseId);
  const btn = document.getElementById('ex-card-' + exerciseId).querySelector('.hint-btn');
  if (!hintEl) return;

  hintEl.style.display = 'block';
  hintEl.textContent = `Hint ${idx + 1}/${hints.length}: ${hints[idx]}`;
  _hintIndex[exerciseId]++;

  if (_hintIndex[exerciseId] >= hints.length) {
    if (btn) btn.textContent = '💡 No more hints';
    if (btn) btn.disabled = true;
  } else {
    if (btn) btn.textContent = `💡 Next Hint (${_hintIndex[exerciseId] + 1}/${hints.length})`;
  }
}

// ---------------------------------------------------------------------------
// Progress bar update
// ---------------------------------------------------------------------------
async function updateProgressBar() {
  const res = await fetch('/api/stats');
  const data = await res.json();
  const fill = document.querySelector('.global-progress-fill');
  const label = document.querySelector('.global-progress-label');
  if (fill) fill.style.width = data.overall_pct + '%';
  if (label) label.textContent = data.overall_pct + '% complete';
}

// ---------------------------------------------------------------------------
// Initialisation
// ---------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  // Pre-populate from server-side data
  if (typeof PASSED_EXERCISES === 'object') {
    Object.assign(_exercisePassed, PASSED_EXERCISES);
  }
  if (typeof ANSWERED_QUIZ === 'object') {
    Object.assign(_quizAnswered, ANSWERED_QUIZ);
  }

  // Check if quiz is already fully answered (coming back to a completed lesson)
  if (typeof LESSON_DATA !== 'undefined') {
    const allQuestions = LESSON_DATA.quiz || [];
    const answeredCount = Object.keys(ANSWERED_QUIZ || {}).length;
    if (answeredCount >= allQuestions.length && allQuestions.length > 0) {
      const row = document.getElementById('quiz-complete-row');
      if (row) row.style.display = 'block';
    }
  }

  // Keyboard shortcut: Ctrl+Enter to run
  document.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      runCode();
    }
  });

  // Close modal on overlay click
  const modal = document.getElementById('completion-modal');
  if (modal) modal.addEventListener('click', e => { if (e.target === modal) closeModal(); });
});
