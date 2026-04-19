from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
import hashlib
import os
from datetime import datetime, date

app = Flask(__name__)
app.secret_key = 'attendance_system_secret_2024'
DB_PATH = 'attendance.db'


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.executescript('''
        CREATE TABLE IF NOT EXISTS lecturers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            password TEXT NOT NULL,
            department TEXT
        );

        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_number TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            password TEXT NOT NULL,
            program TEXT
        );

        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            lecturer_id INTEGER,
            FOREIGN KEY(lecturer_id) REFERENCES lecturers(id)
        );

        CREATE TABLE IF NOT EXISTS enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            course_id INTEGER,
            UNIQUE(student_id, course_id),
            FOREIGN KEY(student_id) REFERENCES students(id),
            FOREIGN KEY(course_id) REFERENCES courses(id)
        );

        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            course_id INTEGER,
            date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'present',
            marked_by INTEGER,
            marked_at TEXT,
            UNIQUE(student_id, course_id, date),
            FOREIGN KEY(student_id) REFERENCES students(id),
            FOREIGN KEY(course_id) REFERENCES courses(id)
        );
    ''')

    def pw(plain): return hashlib.sha256(plain.encode()).hexdigest()

    lecturers = [
        ('STAFF001', 'Dr. Sarah Nakamura', pw('staff001'), 'Computer Science'),
        ('STAFF002', 'Prof. James Okafor', pw('staff002'), 'Mathematics'),
        ('STAFF003', 'Ms. Amina Dlamini', pw('staff003'), 'Business Studies'),
    ]
    c.executemany(
        'INSERT OR IGNORE INTO lecturers (staff_id, name, password, department) VALUES (?,?,?,?)',
        lecturers
    )

    # Students
    students = [
        ('STU2024001', 'Alice Mwangi', pw('stu2024001'), 'BSc Computer Science'),
        ('STU2024002', 'Boniface Khumalo', pw('stu2024002'), 'BSc Computer Science'),
        ('STU2024003', 'Charity Ndlovu', pw('stu2024003'), 'BSc Mathematics'),
        ('STU2024004', 'David Amara', pw('stu2024004'), 'BSc Computer Science'),
        ('STU2024005', 'Emma Tjikuzu', pw('stu2024005'), 'BComm Business'),
        ('STU2024006', 'Felix Hamutenya', pw('stu2024006'), 'BSc Mathematics'),
        ('STU2024007', 'Grace Iipinge', pw('stu2024007'), 'BComm Business'),
        ('STU2024008', 'Henry Shilongo', pw('stu2024008'), 'BSc Computer Science'),
    ]
    c.executemany(
        'INSERT OR IGNORE INTO students (student_number, name, password, program) VALUES (?,?,?,?)',
        students
    )

    # Courses
    courses = [
        ('CS101', 'Introduction to Programming', 1),
        ('CS201', 'Data Structures & Algorithms', 1),
        ('MATH101', 'Calculus I', 2),
        ('MATH201', 'Linear Algebra', 2),
        ('BUS101', 'Business Management', 3),
    ]
    c.executemany(
        'INSERT OR IGNORE INTO courses (code, name, lecturer_id) VALUES (?,?,?)',
        courses
    )

    enrollments = [
        (1,1),(1,2),(2,1),(2,2),(3,3),(3,4),(4,1),(4,2),(5,5),(6,3),(6,4),(7,5),(8,1),(8,2)
    ]
    c.executemany('INSERT OR IGNORE INTO enrollments (student_id, course_id) VALUES (?,?)', enrollments)

    conn.commit()
    conn.close()

def hash_pw(plain): return hashlib.sha256(plain.encode()).hexdigest()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/api/login/lecturer', methods=['POST'])
def login_lecturer():
    data = request.json
    db = get_db()
    row = db.execute(
        'SELECT * FROM lecturers WHERE staff_id=? AND password=?',
        (data['staff_id'], hash_pw(data['password']))
    ).fetchone()
    db.close()
    if row:
        session['user_type'] = 'lecturer'
        session['user_id'] = row['id']
        session['user_name'] = row['name']
        return jsonify({'ok': True, 'name': row['name']})
    return jsonify({'ok': False, 'error': 'Invalid Staff ID or password'}), 401

@app.route('/api/login/student', methods=['POST'])
def login_student():
    data = request.json
    db = get_db()
    row = db.execute(
        'SELECT * FROM students WHERE student_number=? AND password=?',
        (data['student_number'], hash_pw(data['password']))
    ).fetchone()
    db.close()
    if row:
        session['user_type'] = 'student'
        session['user_id'] = row['id']
        session['user_name'] = row['name']
        return jsonify({'ok': True, 'name': row['name']})
    return jsonify({'ok': False, 'error': 'Invalid Student Number or password'}), 401

@app.route('/api/lecturer/courses')
def lecturer_courses():
    if session.get('user_type') != 'lecturer':
        return jsonify({'error': 'Unauthorized'}), 403
    db = get_db()
    courses = db.execute(
        'SELECT * FROM courses WHERE lecturer_id=?', (session['user_id'],)
    ).fetchall()
    db.close()
    return jsonify([dict(c) for c in courses])

@app.route('/api/lecturer/course/<int:course_id>/students')
def course_students(course_id):
    if session.get('user_type') != 'lecturer':
        return jsonify({'error': 'Unauthorized'}), 403
    today = request.args.get('date', date.today().isoformat())
    db = get_db()
    students = db.execute('''
        SELECT s.id, s.student_number, s.name, s.program,
               a.status
        FROM enrollments e
        JOIN students s ON e.student_id = s.id
        LEFT JOIN attendance a ON a.student_id = s.id AND a.course_id = ? AND a.date = ?
        WHERE e.course_id = ?
        ORDER BY s.name
    ''', (course_id, today, course_id)).fetchall()
    db.close()
    return jsonify([dict(s) for s in students])

@app.route('/api/lecturer/mark', methods=['POST'])
def mark_attendance():
    if session.get('user_type') != 'lecturer':
        return jsonify({'error': 'Unauthorized'}), 403
    data = request.json
    course_id = data['course_id']
    attendance_date = data.get('date', date.today().isoformat())
    records = data['records']  # [{student_id, status}]
    now = datetime.now().isoformat(sep=' ', timespec='seconds')
    db = get_db()
    for r in records:
        db.execute('''
            INSERT INTO attendance (student_id, course_id, date, status, marked_by, marked_at)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(student_id, course_id, date) DO UPDATE SET status=excluded.status, marked_at=excluded.marked_at
        ''', (r['student_id'], course_id, attendance_date, r['status'], session['user_id'], now))
    db.commit()
    db.close()
    return jsonify({'ok': True, 'message': f'Attendance saved for {len(records)} students.'})

@app.route('/api/lecturer/course/<int:course_id>/report')
def course_report(course_id):
    if session.get('user_type') != 'lecturer':
        return jsonify({'error': 'Unauthorized'}), 403
    db = get_db()
    course = db.execute('SELECT * FROM courses WHERE id=?', (course_id,)).fetchone()
    if not course or course['lecturer_id'] != session['user_id']:
        db.close()
        return jsonify({'error': 'Not found'}), 404

    students = db.execute('''
        SELECT s.id, s.student_number, s.name, s.program
        FROM enrollments e
        JOIN students s ON e.student_id = s.id
        WHERE e.course_id = ?
        ORDER BY s.name
    ''', (course_id,)).fetchall()

    dates = db.execute('''
        SELECT DISTINCT date FROM attendance WHERE course_id=? ORDER BY date
    ''', (course_id,)).fetchall()
    dates = [d['date'] for d in dates]

    report = []
    for st in students:
        att = db.execute('''
            SELECT date, status FROM attendance WHERE student_id=? AND course_id=?
        ''', (st['id'], course_id)).fetchall()
        att_map = {a['date']: a['status'] for a in att}
        total = len(dates)
        present = sum(1 for d in dates if att_map.get(d) == 'present')
        pct = round(present / total * 100) if total else 0
        report.append({
            'student_number': st['student_number'],
            'name': st['name'],
            'program': st['program'],
            'dates': att_map,
            'total': total,
            'present': present,
            'percentage': pct
        })

    db.close()
    return jsonify({'course': dict(course), 'dates': dates, 'report': report})

@app.route('/api/student/courses')
def student_courses():
    if session.get('user_type') != 'student':
        return jsonify({'error': 'Unauthorized'}), 403
    db = get_db()
    courses = db.execute('''
        SELECT c.id, c.code, c.name, l.name as lecturer_name, l.department
        FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        JOIN lecturers l ON c.lecturer_id = l.id
        WHERE e.student_id = ?
        ORDER BY c.code
    ''', (session['user_id'],)).fetchall()
    db.close()
    return jsonify([dict(c) for c in courses])

@app.route('/api/student/attendance/<int:course_id>')
def student_attendance(course_id):
    if session.get('user_type') != 'student':
        return jsonify({'error': 'Unauthorized'}), 403
    db = get_db()
    records = db.execute('''
        SELECT a.date, a.status, a.marked_at
        FROM attendance a
        WHERE a.student_id=? AND a.course_id=?
        ORDER BY a.date DESC
    ''', (session['user_id'], course_id)).fetchall()

    total_sessions = db.execute('''
        SELECT COUNT(DISTINCT date) as cnt FROM attendance WHERE course_id=?
    ''', (course_id,)).fetchone()['cnt']

    present = sum(1 for r in records if r['status'] == 'present')
    pct = round(present / total_sessions * 100) if total_sessions else 0

    db.close()
    return jsonify({
        'records': [dict(r) for r in records],
        'total_sessions': total_sessions,
        'present': present,
        'percentage': pct
    })

@app.route('/api/student/summary')
def student_summary():
    if session.get('user_type') != 'student':
        return jsonify({'error': 'Unauthorized'}), 403
    db = get_db()
    courses = db.execute('''
        SELECT c.id, c.code, c.name
        FROM enrollments e JOIN courses c ON e.course_id = c.id
        WHERE e.student_id = ?
    ''', (session['user_id'],)).fetchall()

    summary = []
    for course in courses:
        total = db.execute(
            'SELECT COUNT(DISTINCT date) as cnt FROM attendance WHERE course_id=?',
            (course['id'],)
        ).fetchone()['cnt']
        present = db.execute(
            'SELECT COUNT(*) as cnt FROM attendance WHERE student_id=? AND course_id=? AND status=?',
            (session['user_id'], course['id'], 'present')
        ).fetchone()['cnt']
        pct = round(present / total * 100) if total else 0
        summary.append({
            'course_id': course['id'],
            'code': course['code'],
            'name': course['name'],
            'total': total,
            'present': present,
            'percentage': pct
        })
    db.close()
    return jsonify(summary)

if __name__ == '__main__':
    init_db()
    print("\n✅ Digital Attendance System Started!")
    print("━" * 45)
    print("🌐 Open: http://localhost:5000")
    print("━" * 45)
    print("\n📋 Test Credentials:")
    print("  LECTURER  → Staff ID: STAFF001  | Password: staff001")
    print("  STUDENT   → Student#: STU2024001 | Password: stu2024001")
    print("━" * 45)
    app.run(debug=True, port=5000)
