import json
import sqlite3
import subprocess
from datetime import datetime, date
from pathlib import Path
from flask import Flask, render_template, jsonify, request, abort

BASE_DIR = Path(__file__).resolve().parent
CONTENT_DIR = BASE_DIR / 'content'
DB_PATH = BASE_DIR / 'data' / 'progress.db'

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS progress (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                lesson_id       TEXT NOT NULL UNIQUE,
                status          TEXT NOT NULL DEFAULT 'not_started',
                started_at      TIMESTAMP,
                completed_at    TIMESTAMP,
                time_spent_sec  INTEGER DEFAULT 0,
                xp_earned       INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS exercise_attempts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                lesson_id       TEXT NOT NULL,
                exercise_id     TEXT NOT NULL,
                code            TEXT,
                passed          INTEGER NOT NULL DEFAULT 0,
                attempt_number  INTEGER DEFAULT 1,
                attempted_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS quiz_answers (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                lesson_id       TEXT NOT NULL,
                question_id     TEXT NOT NULL,
                selected_option INTEGER,
                is_correct      INTEGER NOT NULL DEFAULT 0,
                answered_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(lesson_id, question_id)
            );

            CREATE TABLE IF NOT EXISTS badges (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                badge_id        TEXT NOT NULL UNIQUE,
                earned_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS user_settings (
                key             TEXT PRIMARY KEY,
                value           TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_progress_lesson_id ON progress(lesson_id);
            CREATE INDEX IF NOT EXISTS idx_exercise_lesson_id ON exercise_attempts(lesson_id);
            CREATE INDEX IF NOT EXISTS idx_quiz_lesson_id ON quiz_answers(lesson_id);
        """)
        # Seed default settings if not present
        conn.execute("INSERT OR IGNORE INTO user_settings VALUES ('theme', 'dark')")
        conn.execute("INSERT OR IGNORE INTO user_settings VALUES ('font_size', '14')")
        conn.execute("INSERT OR IGNORE INTO user_settings VALUES ('last_activity', '')")
        conn.execute("INSERT OR IGNORE INTO user_settings VALUES ('streak_days', '0')")
        conn.execute("INSERT OR IGNORE INTO user_settings VALUES ('last_lesson', '')")
        conn.commit()


# ---------------------------------------------------------------------------
# Content helpers
# ---------------------------------------------------------------------------

def load_curriculum():
    path = CONTENT_DIR / 'curriculum.json'
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def load_lesson(lesson_id: str):
    # lesson_id format: "module1_lesson2"
    parts = lesson_id.split('_')
    if len(parts) != 2:
        return None
    module_part, lesson_part = parts
    path = CONTENT_DIR / module_part / f'{lesson_part}.json'
    if not path.exists():
        return None
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def get_all_lesson_ids(curriculum):
    ids = []
    for mod in curriculum.get('modules', []):
        for lesson in mod.get('lessons', []):
            ids.append(lesson['id'])
    return ids


def get_adjacent_lessons(curriculum, lesson_id):
    all_ids = get_all_lesson_ids(curriculum)
    idx = all_ids.index(lesson_id) if lesson_id in all_ids else -1
    prev_id = all_ids[idx - 1] if idx > 0 else None
    next_id = all_ids[idx + 1] if idx < len(all_ids) - 1 else None
    return prev_id, next_id


# ---------------------------------------------------------------------------
# Progress helpers
# ---------------------------------------------------------------------------

def get_progress_map(conn):
    rows = conn.execute("SELECT lesson_id, status, xp_earned FROM progress").fetchall()
    return {r['lesson_id']: {'status': r['status'], 'xp': r['xp_earned']} for r in rows}


def update_streak(conn):
    today = date.today().isoformat()
    row = conn.execute("SELECT value FROM user_settings WHERE key='last_activity'").fetchone()
    last = row['value'] if row else ''
    if last == today:
        return
    if last:
        from datetime import timedelta
        last_date = date.fromisoformat(last)
        diff = (date.today() - last_date).days
        streak_row = conn.execute("SELECT value FROM user_settings WHERE key='streak_days'").fetchone()
        streak = int(streak_row['value']) if streak_row else 0
        if diff == 1:
            streak += 1
        elif diff > 1:
            streak = 1
    else:
        streak = 1
    conn.execute("INSERT OR REPLACE INTO user_settings VALUES ('streak_days', ?)", (str(streak),))
    conn.execute("INSERT OR REPLACE INTO user_settings VALUES ('last_activity', ?)", (today,))
    conn.commit()


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    curriculum = load_curriculum()
    with get_db() as conn:
        progress_map = get_progress_map(conn)
        row = conn.execute(
            "SELECT lesson_id FROM progress WHERE status != 'not_started' ORDER BY COALESCE(completed_at, started_at) DESC LIMIT 1"
        ).fetchone()
    last_lesson = row['lesson_id'] if row else ''
    # Annotate modules with progress
    for mod in curriculum['modules']:
        total = len(mod['lessons'])
        done = sum(1 for l in mod['lessons'] if progress_map.get(l['id'], {}).get('status') == 'completed')
        mod['progress_pct'] = int(done / total * 100) if total else 0
        mod['lessons_done'] = done
        for lesson in mod['lessons']:
            lesson['status'] = progress_map.get(lesson['id'], {}).get('status', 'not_started')
    total_lessons = sum(len(m['lessons']) for m in curriculum['modules'])
    total_done = sum(1 for p in progress_map.values() if p['status'] == 'completed')
    overall_pct = int(total_done / total_lessons * 100) if total_lessons else 0
    return render_template('index.html',
                           curriculum=curriculum,
                           total_lessons=total_lessons,
                           total_done=total_done,
                           overall_pct=overall_pct,
                           last_lesson=last_lesson)


@app.route('/lesson/<lesson_id>')
def lesson_page(lesson_id):
    curriculum = load_curriculum()
    lesson = load_lesson(lesson_id)
    if lesson is None:
        abort(404)
    prev_id, next_id = get_adjacent_lessons(curriculum, lesson_id)
    with get_db() as conn:
        progress_map = get_progress_map(conn)
        update_streak(conn)
        conn.commit()
        last_row = conn.execute(
            "SELECT lesson_id FROM progress WHERE status != 'not_started' ORDER BY COALESCE(completed_at, started_at) DESC LIMIT 1"
        ).fetchone()
        last_lesson = last_row['lesson_id'] if last_row else lesson_id
        ex_rows = conn.execute(
            "SELECT exercise_id, passed FROM exercise_attempts WHERE lesson_id=? ORDER BY attempted_at DESC",
            (lesson_id,)
        ).fetchall()
        quiz_rows = conn.execute(
            "SELECT question_id, selected_option, is_correct FROM quiz_answers WHERE lesson_id=?",
            (lesson_id,)
        ).fetchall()
    # Passed exercises (latest attempt per exercise)
    passed_exercises = {}
    for row in ex_rows:
        if row['exercise_id'] not in passed_exercises:
            passed_exercises[row['exercise_id']] = bool(row['passed'])
    answered_quiz = {r['question_id']: {'selected': r['selected_option'], 'correct': bool(r['is_correct'])} for r in quiz_rows}
    # Sidebar data
    for mod in curriculum['modules']:
        for l in mod['lessons']:
            l['status'] = progress_map.get(l['id'], {}).get('status', 'not_started')
    current_status = progress_map.get(lesson_id, {}).get('status', 'not_started')
    # Find current module title
    current_module_title = ''
    for mod in curriculum['modules']:
        for l in mod['lessons']:
            if l['id'] == lesson_id:
                current_module_title = mod['title']
    return render_template('lesson.html',
                           lesson=lesson,
                           curriculum=curriculum,
                           lesson_id=lesson_id,
                           prev_id=prev_id,
                           next_id=next_id,
                           passed_exercises=passed_exercises,
                           answered_quiz=answered_quiz,
                           current_status=current_status,
                           current_module_title=current_module_title,
                           progress_map=progress_map,
                           last_lesson=last_lesson)


@app.route('/dashboard')
def dashboard():
    curriculum = load_curriculum()
    with get_db() as conn:
        progress_map = get_progress_map(conn)
        badges = [r['badge_id'] for r in conn.execute("SELECT badge_id FROM badges ORDER BY earned_at DESC").fetchall()]
        settings = {r['key']: r['value'] for r in conn.execute("SELECT key, value FROM user_settings").fetchall()}
        recent = conn.execute(
            "SELECT lesson_id, completed_at FROM progress WHERE status='completed' ORDER BY completed_at DESC LIMIT 10"
        ).fetchall()
    total_xp = sum(p['xp'] for p in progress_map.values())
    total_done = sum(1 for p in progress_map.values() if p['status'] == 'completed')
    total_lessons = sum(len(m['lessons']) for m in curriculum['modules'])
    level = max(1, total_xp // 100 + 1)
    for mod in curriculum['modules']:
        total = len(mod['lessons'])
        done = sum(1 for l in mod['lessons'] if progress_map.get(l['id'], {}).get('status') == 'completed')
        mod['progress_pct'] = int(done / total * 100) if total else 0
        mod['lessons_done'] = done
    return render_template('dashboard.html',
                           curriculum=curriculum,
                           total_xp=total_xp,
                           level=level,
                           total_done=total_done,
                           total_lessons=total_lessons,
                           badges=badges,
                           settings=settings,
                           recent=list(recent),
                           streak=int(settings.get('streak_days', 0)))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.route('/api/curriculum')
def api_curriculum():
    return jsonify(load_curriculum())


@app.route('/api/lesson/<lesson_id>')
def api_lesson(lesson_id):
    lesson = load_lesson(lesson_id)
    if lesson is None:
        return jsonify({'error': 'not found'}), 404
    return jsonify(lesson)


@app.route('/api/run', methods=['POST'])
def api_run():
    data = request.get_json(force=True) or {}
    code = data.get('code', '')
    tests = data.get('tests', [])
    if not code.strip():
        return jsonify({'stdout': '', 'stderr': '', 'tests': []})
    payload = json.dumps({'code': code, 'tests': tests})
    try:
        result = subprocess.run(
            ['python3', str(BASE_DIR / 'runner.py'), payload],
            capture_output=True, text=True, timeout=10
        )
        if result.stdout:
            return jsonify(json.loads(result.stdout))
        return jsonify({'stdout': '', 'stderr': result.stderr or 'Runner error', 'tests': []})
    except subprocess.TimeoutExpired:
        return jsonify({'stdout': '', 'stderr': 'TimeoutError: Code ran for too long (10 second limit)\n', 'tests': []})
    except Exception as e:
        return jsonify({'stdout': '', 'stderr': str(e), 'tests': []})


@app.route('/api/progress')
def api_progress():
    with get_db() as conn:
        progress = [dict(r) for r in conn.execute("SELECT * FROM progress").fetchall()]
        attempts = [dict(r) for r in conn.execute("SELECT * FROM exercise_attempts ORDER BY attempted_at DESC LIMIT 200").fetchall()]
        quiz = [dict(r) for r in conn.execute("SELECT * FROM quiz_answers").fetchall()]
    return jsonify({'progress': progress, 'attempts': attempts, 'quiz': quiz})


@app.route('/api/stats')
def api_stats():
    curriculum = load_curriculum()
    with get_db() as conn:
        progress_map = get_progress_map(conn)
        badges = [r['badge_id'] for r in conn.execute("SELECT badge_id FROM badges").fetchall()]
        settings = {r['key']: r['value'] for r in conn.execute("SELECT key, value FROM user_settings").fetchall()}
    total_xp = sum(p['xp'] for p in progress_map.values())
    total_done = sum(1 for p in progress_map.values() if p['status'] == 'completed')
    total_lessons = sum(len(m['lessons']) for m in curriculum['modules'])
    level = max(1, total_xp // 100 + 1)
    module_stats = []
    for mod in curriculum['modules']:
        total = len(mod['lessons'])
        done = sum(1 for l in mod['lessons'] if progress_map.get(l['id'], {}).get('status') == 'completed')
        module_stats.append({'id': mod['id'], 'title': mod['title'], 'done': done, 'total': total,
                              'pct': int(done / total * 100) if total else 0})
    return jsonify({
        'total_xp': total_xp,
        'level': level,
        'total_done': total_done,
        'total_lessons': total_lessons,
        'overall_pct': int(total_done / total_lessons * 100) if total_lessons else 0,
        'modules': module_stats,
        'badges': badges,
        'streak': int(settings.get('streak_days', 0))
    })


@app.route('/api/progress/lesson', methods=['POST'])
def api_progress_lesson():
    data = request.get_json(force=True)
    lesson_id = data.get('lesson_id', '').strip()
    status = data.get('status', 'in_progress')
    xp = data.get('xp', 0)
    if not lesson_id:
        return jsonify({'error': 'missing lesson_id'}), 400
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        existing = conn.execute("SELECT id, status FROM progress WHERE lesson_id=?", (lesson_id,)).fetchone()
        if existing is None:
            conn.execute(
                "INSERT INTO progress (lesson_id, status, started_at, xp_earned) VALUES (?,?,?,?)",
                (lesson_id, status, now, xp)
            )
        else:
            if status == 'completed' and existing['status'] != 'completed':
                conn.execute(
                    "UPDATE progress SET status=?, completed_at=?, xp_earned=? WHERE lesson_id=?",
                    (status, now, xp, lesson_id)
                )
            elif status == 'in_progress' and existing['status'] == 'not_started':
                conn.execute("UPDATE progress SET status=?, started_at=? WHERE lesson_id=?",
                             (status, now, lesson_id))
        conn.commit()
        # Check badge conditions
        _check_badges(conn, lesson_id)
    return jsonify({'ok': True})


@app.route('/api/progress/exercise', methods=['POST'])
def api_progress_exercise():
    data = request.get_json(force=True)
    lesson_id = data.get('lesson_id', '').strip()
    exercise_id = data.get('exercise_id', '').strip()
    code = data.get('code', '')
    passed = 1 if data.get('passed') else 0
    if not lesson_id or not exercise_id:
        return jsonify({'error': 'missing fields'}), 400
    with get_db() as conn:
        count = conn.execute(
            "SELECT COUNT(*) as c FROM exercise_attempts WHERE lesson_id=? AND exercise_id=?",
            (lesson_id, exercise_id)
        ).fetchone()['c']
        conn.execute(
            "INSERT INTO exercise_attempts (lesson_id, exercise_id, code, passed, attempt_number) VALUES (?,?,?,?,?)",
            (lesson_id, exercise_id, code, passed, count + 1)
        )
        conn.commit()
    return jsonify({'ok': True})


@app.route('/api/progress/quiz', methods=['POST'])
def api_progress_quiz():
    data = request.get_json(force=True)
    lesson_id = data.get('lesson_id', '').strip()
    question_id = data.get('question_id', '').strip()
    selected = data.get('selected_option')
    is_correct = 1 if data.get('is_correct') else 0
    if not lesson_id or not question_id:
        return jsonify({'error': 'missing fields'}), 400
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO quiz_answers (lesson_id, question_id, selected_option, is_correct) VALUES (?,?,?,?)",
            (lesson_id, question_id, selected, is_correct)
        )
        conn.commit()
    return jsonify({'ok': True})


@app.route('/api/settings', methods=['POST'])
def api_settings():
    data = request.get_json(force=True)
    key = data.get('key', '').strip()
    value = str(data.get('value', ''))
    if not key:
        return jsonify({'error': 'missing key'}), 400
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO user_settings VALUES (?,?)", (key, value))
        conn.commit()
    return jsonify({'ok': True})


@app.route('/api/reset', methods=['POST'])
def api_reset():
    with get_db() as conn:
        conn.execute("DELETE FROM progress")
        conn.execute("DELETE FROM exercise_attempts")
        conn.execute("DELETE FROM quiz_answers")
        conn.execute("DELETE FROM badges")
        conn.execute("INSERT OR REPLACE INTO user_settings VALUES ('streak_days', '0')")
        conn.execute("INSERT OR REPLACE INTO user_settings VALUES ('last_activity', '')")
        conn.commit()
    return jsonify({'ok': True})


# ---------------------------------------------------------------------------
# Badge logic
# ---------------------------------------------------------------------------

BADGE_DEFS = {
    'first_lesson': {'name': 'First Steps', 'desc': 'Complete your first lesson', 'icon': '🎯'},
    'module1_complete': {'name': 'Python Starter', 'desc': 'Complete Module 1', 'icon': '🐍'},
    'module2_complete': {'name': 'Data Wrangler', 'desc': 'Complete Module 2', 'icon': '📦'},
    'module3_complete': {'name': 'Flow Master', 'desc': 'Complete Module 3', 'icon': '🔀'},
    'module4_complete': {'name': 'Collector', 'desc': 'Complete Module 4', 'icon': '🗂️'},
    'module5_complete': {'name': 'Functionista', 'desc': 'Complete Module 5', 'icon': '⚙️'},
    'module6_complete': {'name': 'String Wizard', 'desc': 'Complete Module 6', 'icon': '✍️'},
    'module7_complete': {'name': 'Error Handler', 'desc': 'Complete Module 7', 'icon': '🛡️'},
    'module8_complete': {'name': 'Object Master', 'desc': 'Complete Module 8', 'icon': '🏗️'},
    'module9_complete': {'name': 'Library Pro', 'desc': 'Complete Module 9', 'icon': '📚'},
    'graduate': {'name': 'Python Graduate', 'desc': 'Complete all 10 modules', 'icon': '🎓'},
    'xp_500': {'name': 'XP Hunter', 'desc': 'Earn 500 XP', 'icon': '⭐'},
    'xp_1000': {'name': 'XP Champion', 'desc': 'Earn 1000 XP', 'icon': '🌟'},
}


def _check_badges(conn, lesson_id=None):
    existing = {r['badge_id'] for r in conn.execute("SELECT badge_id FROM badges").fetchall()}
    progress_map = get_progress_map(conn)
    curriculum = load_curriculum()
    new_badges = []

    total_done = sum(1 for p in progress_map.values() if p['status'] == 'completed')
    total_xp = sum(p['xp'] for p in progress_map.values())

    if total_done >= 1 and 'first_lesson' not in existing:
        new_badges.append('first_lesson')

    for mod in curriculum['modules']:
        badge_id = f"{mod['id']}_complete"
        if badge_id not in existing:
            all_done = all(progress_map.get(l['id'], {}).get('status') == 'completed' for l in mod['lessons'])
            if all_done:
                new_badges.append(badge_id)

    all_modules_done = all(
        all(progress_map.get(l['id'], {}).get('status') == 'completed' for l in mod['lessons'])
        for mod in curriculum['modules']
    )
    if all_modules_done and 'graduate' not in existing:
        new_badges.append('graduate')

    if total_xp >= 500 and 'xp_500' not in existing:
        new_badges.append('xp_500')
    if total_xp >= 1000 and 'xp_1000' not in existing:
        new_badges.append('xp_1000')

    for b in new_badges:
        conn.execute("INSERT OR IGNORE INTO badges (badge_id) VALUES (?)", (b,))
    if new_badges:
        conn.commit()

    return new_badges


@app.route('/api/badges/check', methods=['POST'])
def api_check_badges():
    with get_db() as conn:
        new_badges = _check_badges(conn)
    result = [{'id': b, **BADGE_DEFS.get(b, {'name': b, 'desc': '', 'icon': '🏆'})} for b in new_badges]
    return jsonify({'new_badges': result, 'all_defs': BADGE_DEFS})


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'not found'}), 404
    # Ignore favicon and static asset 404s silently
    if request.path in ('/favicon.ico',) or request.path.startswith('/static/'):
        return '', 404
    try:
        curriculum = load_curriculum()
        with get_db() as conn:
            progress_map = get_progress_map(conn)
        return render_template('index.html', curriculum=curriculum,
                               progress_map=progress_map,
                               first_lesson=curriculum['modules'][0]['lessons'][0],
                               resume_id=None), 404
    except Exception:
        return '<h1>Page not found</h1><p><a href="/">Go home</a></p>', 404


@app.errorhandler(500)
def server_error(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'internal server error', 'message': str(e)}), 500
    return '<h1>Something went wrong</h1><p><a href="/">Go home</a></p>', 500


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    init_db()
    curriculum = load_curriculum()
    total = sum(len(m['lessons']) for m in curriculum['modules'])
    print()
    print("=========================================")
    print("   Python Learning App is starting...")
    print("=========================================")
    print(f"  Database:  {DB_PATH}")
    print(f"  Lessons:   {total} lessons across {len(curriculum['modules'])} modules")
    print(f"  Server:    http://localhost:5000")
    print("=========================================")
    print("  Open your browser and go to:")
    print("    http://localhost:5000")
    print("  Press Ctrl+C here to stop the app.")
    print("=========================================")
    print()
    app.run(host='127.0.0.1', port=5000, debug=False)
#KIRRRRR