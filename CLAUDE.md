# Python Learning App — Project Context

## What this is
An interactive Python learning web app. The user is a complete beginner learning Python by using this app. Claude built the entire app and continues to maintain and fix it. Make all technical decisions independently.

## How to run
```bash
cd /mnt/c/Users/progm/python-learning-app
python3 app.py
# Open http://localhost:5000 in browser
```
First time on a new machine: `bash setup.sh` (installs Flask via apt).

## Environment
- WSL2 Ubuntu 24.04 on Windows
- Python 3.12.3, Flask installed via `sudo apt-get` (no pip)
- SQLite progress DB at `data/progress.db` (auto-created on first run)
- launch.bat: double-click launcher for Windows (WSL distro name is `Ubuntu-24.04`)

## Architecture
- **Code execution**: server-side via `runner.py` called by subprocess from `/api/run`. Pyodide was removed — Edge blocked the CDN and WebAssembly failed.
- **Editor**: CodeMirror 5 (CDN)
- **Content**: 71 lesson JSON files in `content/module1/` through `content/module10/`
- **Progress**: SQLite via `app.py`

## Key files
| File | Purpose |
|---|---|
| `app.py` | Flask server — all routes, DB init, `/api/run` endpoint |
| `runner.py` | Runs user Python code, evaluates tests, returns JSON |
| `static/js/app.js` | Lesson tabs, exercise loading, quiz logic, XP/completion |
| `static/js/pyodide-runner.js` | Now posts to `/api/run` (not Pyodide) |
| `static/js/editor.js` | CodeMirror 5 setup |
| `templates/lesson.html` | 3-panel lesson layout |
| `content/curriculum.json` | Master lesson index |

## JS globals in lesson.html
```javascript
const LESSON_DATA = { /* full lesson JSON */ };
const LESSON_ID = "module1_lesson4";
const PASSED_EXERCISES = { "ex1": true };
const ANSWERED_QUIZ = { "q1": { selected: 2, correct: true } };
const CURRENT_STATUS = "completed" | "in_progress" | "not_started";
```

## runner.py test types
`runs_without_error`, `stdout_contains`, `stdout_equals`, `stdout_lines_gte`, `variable_exists`, `variable_equals`, `function_exists`, `function_returns`

Note: `variable_exists` and `variable_equals` accept both `"variable_name"` and `"variable"` as the key.

## Content standards (apply to all 71 lessons)
- Starter code = **comments only** — student writes all the code themselves, nothing pre-written
- Tests must not be overly strict — check for key values, not exact phrasing
- Add pedagogical notes wherever Python behavior would surprise a beginner (e.g. print() commas add spaces, sets are unordered, = is assignment not equality, float division, % is remainder)

## Bugs already fixed (don't revert)
- launch.bat WSL distro: `Ubuntu-24.04` (not `Ubuntu`)
- launch.bat: `pkill -f 'python3 app.py'` runs before start to avoid port conflict
- 404/500 error handlers: pass `curriculum` variable or use plain HTML fallback
- `onclick` in lesson.html: uses `loadExerciseById('ex1')` not inline JSON (HTML escaping bug)
- module3/lesson8.json: `range(1,20)` → `range(1,25)` (answer 21 was out of range)
- module6/lesson1.json: stray space before `print(csv_line)` caused IndentationError
- module2/lesson2.json: code_output last line corrected to `=-=-=-=-=-=`
- module1/lesson4.json: temperature exercise tests loosened; starter code is comments only
- XP spam: `markLessonComplete()` guarded by `_lessonCompleted` flag (set from `CURRENT_STATUS`)

## Working style
- Fix bugs immediately when the user reports them — no need to ask for confirmation
- User describes bugs in plain language, not error messages
- Keep responses short and direct
