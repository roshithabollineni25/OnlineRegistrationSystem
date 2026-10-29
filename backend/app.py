from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps
from pathlib import Path
import sqlite3
import secrets
import hashlib
import os
import json
from datetime import datetime

app = Flask(__name__)

# Deployment-ready configuration via environment variables
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")
CORS(app, resources={r"/api/*": {"origins": CORS_ORIGINS}})

from database import connect, get_db_info, IS_POSTGRES, DB_PATH

SECRET_KEY = os.environ.get("SECRET_KEY", "northstar-academic-system-secret-key-2026")
ADMIN_DEFAULT_PASSWORD = os.environ.get("OCR_ADMIN_PASSWORD", "admin123")

# In-memory session store (can be replaced by Redis / token store in production)
SESSIONS = {}


# --- Security: Password Hashing ---
def hash_password(password: str, salt: str = None) -> str:
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
    return f"{salt}:{hashed}"


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        salt, expected_hash = stored_hash.split(":")
        check_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
        return secrets.compare_digest(check_hash, expected_hash)
    except Exception:
        # Fallback for plain demo passwords if existing DB had them
        return stored_hash == password


def log_audit(con, action, entity, entity_id, details, performed_by):
    con.execute(
        "INSERT INTO audit_logs(action, entity, entity_id, details, performed_by) VALUES (?, ?, ?, ?, ?)",
        (action, entity, entity_id, str(details), performed_by)
    )


def create_notification(con, recipient_email, recipient_role, title, message, category="enrollment"):
    con.execute(
        """INSERT INTO notifications(recipient_email, recipient_role, title, message, category)
           VALUES (?, ?, ?, ?, ?)""",
        (recipient_email.lower(), recipient_role, title, message, category)
    )


# --- Database Schema & Safe Migration ---
def init_db():
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS academic_programs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            duration_years INTEGER NOT NULL DEFAULT 4,
            total_semesters INTEGER NOT NULL DEFAULT 8
        );

        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS curriculum_requirements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            degree_code TEXT NOT NULL,
            department_code TEXT NOT NULL,
            academic_year INTEGER NOT NULL,
            semester INTEGER NOT NULL,
            required_credits INTEGER NOT NULL DEFAULT 20,
            min_credits INTEGER NOT NULL DEFAULT 16,
            max_credits INTEGER NOT NULL DEFAULT 24,
            UNIQUE(degree_code, department_code, academic_year, semester)
        );

        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            student_reg_no TEXT UNIQUE NOT NULL,
            college_reg_no TEXT UNIQUE NOT NULL,
            degree_code TEXT NOT NULL,
            department_code TEXT NOT NULL,
            academic_year INTEGER NOT NULL,
            semester INTEGER NOT NULL,
            section TEXT NOT NULL DEFAULT 'A',
            status TEXT NOT NULL DEFAULT 'Active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'Dean of Academic Affairs',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            department_code TEXT NOT NULL,
            instructor TEXT NOT NULL,
            credits INTEGER NOT NULL CHECK(credits BETWEEN 1 AND 8),
            schedule TEXT NOT NULL,
            location TEXT NOT NULL DEFAULT 'Academic Block A, Hall 101',
            capacity INTEGER NOT NULL CHECK(capacity > 0),
            description TEXT NOT NULL DEFAULT '',
            prerequisites TEXT NOT NULL DEFAULT 'None',
            term TEXT NOT NULL DEFAULT 'Spring 2026',
            start_date TEXT NOT NULL DEFAULT '2026-01-15',
            end_date TEXT NOT NULL DEFAULT '2026-05-15',
            registration_deadline TEXT NOT NULL DEFAULT '2026-12-31',
            lifecycle_status TEXT NOT NULL DEFAULT 'Registration Open',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS course_eligibility (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
            degree_code TEXT NOT NULL,
            department_code TEXT NOT NULL,
            academic_year INTEGER NOT NULL,
            semester INTEGER NOT NULL,
            UNIQUE(course_id, degree_code, department_code, academic_year, semester)
        );

        CREATE TABLE IF NOT EXISTS branch_allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
            department_code TEXT NOT NULL,
            allocated_seats INTEGER NOT NULL CHECK(allocated_seats >= 0),
            UNIQUE(course_id, department_code)
        );

        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'Pending',
            decision_notes TEXT NOT NULL DEFAULT '',
            decision_by TEXT NOT NULL DEFAULT '',
            decision_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(student_id, course_id)
        );

        CREATE TABLE IF NOT EXISTS drop_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            registration_id INTEGER NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
            student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending Review',
            decision_notes TEXT NOT NULL DEFAULT '',
            decision_by TEXT NOT NULL DEFAULT '',
            decision_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient_email TEXT NOT NULL,
            recipient_role TEXT NOT NULL DEFAULT 'student',
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'enrollment',
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            entity TEXT NOT NULL,
            entity_id INTEGER,
            details TEXT NOT NULL,
            performed_by TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 1. Seed Academic Programs (Degrees)
        if con.execute("SELECT COUNT(*) FROM academic_programs").fetchone()[0] == 0:
            programs = [
                ("B.Tech.", "Bachelor of Technology", 4, 8),
                ("M.Tech.", "Master of Technology", 2, 4),
                ("LL.B.", "Bachelor of Laws", 3, 6),
                ("B.A. LL.B.", "Integrated B.A. and Bachelor of Laws", 5, 10)
            ]
            con.executemany("INSERT INTO academic_programs(code, name, duration_years, total_semesters) VALUES (?, ?, ?, ?)", programs)

        # 2. Seed Departments
        if con.execute("SELECT COUNT(*) FROM departments").fetchone()[0] == 0:
            depts = [
                ("CSE", "Computer Science and Engineering"),
                ("IT", "Information Technology"),
                ("ECE", "Electronics and Communication Engineering"),
                ("EEE", "Electrical and Electronics Engineering"),
                ("MECH", "Mechanical Engineering"),
                ("CIVIL", "Civil Engineering"),
                ("LAW", "Faculty of Law")
            ]
            con.executemany("INSERT INTO departments(code, name) VALUES (?, ?)", depts)

        # 3. Seed Curriculum Credit Requirements
        if con.execute("SELECT COUNT(*) FROM curriculum_requirements").fetchone()[0] == 0:
            curricula = [
                ("B.Tech.", "CSE", 2, 4, 20, 16, 24),
                ("B.Tech.", "IT", 2, 4, 20, 16, 24),
                ("B.Tech.", "ECE", 2, 4, 20, 16, 24),
                ("B.Tech.", "MECH", 2, 4, 20, 16, 24),
                ("LL.B.", "LAW", 2, 3, 18, 14, 22)
            ]
            con.executemany(
                "INSERT INTO curriculum_requirements(degree_code, department_code, academic_year, semester, required_credits, min_credits, max_credits) VALUES (?, ?, ?, ?, ?, ?, ?)",
                curricula
            )

        # 4. Seed Admin
        if con.execute("SELECT COUNT(*) FROM admins").fetchone()[0] == 0:
            con.execute(
                "INSERT INTO admins(name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                ("Dean of Academic Affairs", "admin@northstar.edu", hash_password(ADMIN_DEFAULT_PASSWORD), "Dean of Academic Affairs")
            )

        # 5. Seed Students with Complete Academic Profiles
        if con.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 0:
            sample_students = [
                ("Aarav Kumar", "aarav.kumar@student.edu", hash_password("student123"), "STU2026CSE01", "COL-2026-9041", "B.Tech.", "CSE", 2, 4, "A"),
                ("Rhea Sengupta", "rhea.s@student.edu", hash_password("student123"), "STU2026IT02", "COL-2026-9042", "B.Tech.", "IT", 2, 4, "B"),
                ("Vikram Patel", "vikram.p@student.edu", hash_password("student123"), "STU2026ME03", "COL-2026-9043", "B.Tech.", "MECH", 2, 4, "A"),
                ("Tanya Verma", "tanya.v@student.edu", hash_password("student123"), "STU2026LAW04", "COL-2026-9044", "LL.B.", "LAW", 2, 3, "A")
            ]
            con.executemany(
                "INSERT INTO students(name, email, password_hash, student_reg_no, college_reg_no, degree_code, department_code, academic_year, semester, section) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                sample_students
            )

        # 6. Seed Courses with Eligibility and Branch Allocations
        if con.execute("SELECT COUNT(*) FROM courses").fetchone()[0] == 0:
            sample_courses = [
                (
                    "CSE-301", "Web API Architecture & Security", "CSE", "Dr. Ananya Rao", 4,
                    "Mon & Wed · 10:00 AM - 11:30 AM", "Engineering Hall 102", 60,
                    "Design, build, and secure RESTful microservices and enterprise API gateways.",
                    "CS-201 (Data Structures)", "Spring 2026", "2026-01-15", "2026-05-15", "2026-12-31", "Registration Open"
                ),
                (
                    "CSE-204", "Relational Database Engineering", "CSE", "Prof. Kiran Kumar", 3,
                    "Tue & Thu · 11:30 AM - 1:00 PM", "Computing Lab B", 70,
                    "Relational data modelling, ACID transactions, normalization, and indexing strategies.",
                    "CS-101 (Programming Fundamentals)", "Spring 2026", "2026-01-15", "2026-05-15", "2026-12-31", "Registration Open"
                ),
                (
                    "CSE-410", "Advanced Data Structures & Algorithms", "CSE", "Prof. Naveen Reddy", 4,
                    "Tue & Thu · 3:00 PM - 4:30 PM", "Lecture Hall 4", 50,
                    "Complexity analysis, graph traversal, greedy heuristics, and dynamic programming.",
                    "CS-201 (Data Structures)", "Spring 2026", "2026-01-15", "2026-05-15", "2026-12-31", "Registration Open"
                ),
                (
                    "IT-402", "Cloud Infrastructure & Containerization", "IT", "Dr. Arjun Menon", 4,
                    "Wed & Fri · 9:00 AM - 10:30 AM", "Tech Center 201", 50,
                    "Kubernetes orchestration, distributed cloud storage, and serverless architectures.",
                    "CS-204 (Database Systems)", "Spring 2026", "2026-01-15", "2026-05-15", "2026-12-31", "Registration Open"
                ),
                (
                    "ME-205", "Applied Thermodynamics & Energy Systems", "MECH", "Dr. Rajesh Iyer", 4,
                    "Mon & Thu · 1:30 PM - 3:00 PM", "Mechanical Block 301", 40,
                    "Energy conversion cycles, heat transfer mechanisms, and thermal system modeling.",
                    "PHY-101 (Engineering Physics)", "Spring 2026", "2026-01-15", "2026-05-15", "2026-12-31", "Registration Open"
                ),
                (
                    "LAW-101", "Constitutional Law & Cyber Jurisprudence", "LAW", "Prof. Sunita Mehta", 4,
                    "Tue & Fri · 10:00 AM - 11:30 AM", "Moot Court Hall 1", 45,
                    "Fundamental rights, state jurisdiction, data privacy regulations, and digital contracts.",
                    "None", "Spring 2026", "2026-01-15", "2026-05-15", "2026-12-31", "Registration Open"
                )
            ]

            for c in sample_courses:
                cur = con.execute(
                    """INSERT INTO courses(code, title, department_code, instructor, credits, schedule, location, capacity, description, prerequisites, term, start_date, end_date, registration_deadline, lifecycle_status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    c
                )
                cid = cur.lastrowid
                code = c[0]

                # Setup Branch Allocations & Academic Eligibility based on course
                if code == "CSE-301":
                    # Eligible for B.Tech. CSE & IT Year 2 Sem 4
                    con.execute("INSERT INTO course_eligibility(course_id, degree_code, department_code, academic_year, semester) VALUES (?, 'B.Tech.', 'CSE', 2, 4)", (cid,))
                    con.execute("INSERT INTO course_eligibility(course_id, degree_code, department_code, academic_year, semester) VALUES (?, 'B.Tech.', 'IT', 2, 4)", (cid,))
                    con.execute("INSERT INTO branch_allocations(course_id, department_code, allocated_seats) VALUES (?, 'CSE', 35)", (cid,))
                    con.execute("INSERT INTO branch_allocations(course_id, department_code, allocated_seats) VALUES (?, 'IT', 25)", (cid,))
                elif code == "CSE-204":
                    con.execute("INSERT INTO course_eligibility(course_id, degree_code, department_code, academic_year, semester) VALUES (?, 'B.Tech.', 'CSE', 2, 4)", (cid,))
                    con.execute("INSERT INTO course_eligibility(course_id, degree_code, department_code, academic_year, semester) VALUES (?, 'B.Tech.', 'IT', 2, 4)", (cid,))
                    con.execute("INSERT INTO branch_allocations(course_id, department_code, allocated_seats) VALUES (?, 'CSE', 45)", (cid,))
                    con.execute("INSERT INTO branch_allocations(course_id, department_code, allocated_seats) VALUES (?, 'IT', 25)", (cid,))
                elif code == "CSE-410":
                    con.execute("INSERT INTO course_eligibility(course_id, degree_code, department_code, academic_year, semester) VALUES (?, 'B.Tech.', 'CSE', 2, 4)", (cid,))
                    con.execute("INSERT INTO branch_allocations(course_id, department_code, allocated_seats) VALUES (?, 'CSE', 50)", (cid,))
                elif code == "IT-402":
                    con.execute("INSERT INTO course_eligibility(course_id, degree_code, department_code, academic_year, semester) VALUES (?, 'B.Tech.', 'IT', 2, 4)", (cid,))
                    con.execute("INSERT INTO course_eligibility(course_id, degree_code, department_code, academic_year, semester) VALUES (?, 'B.Tech.', 'CSE', 2, 4)", (cid,))
                    con.execute("INSERT INTO branch_allocations(course_id, department_code, allocated_seats) VALUES (?, 'IT', 30)", (cid,))
                    con.execute("INSERT INTO branch_allocations(course_id, department_code, allocated_seats) VALUES (?, 'CSE', 20)", (cid,))
                elif code == "ME-205":
                    con.execute("INSERT INTO course_eligibility(course_id, degree_code, department_code, academic_year, semester) VALUES (?, 'B.Tech.', 'MECH', 2, 4)", (cid,))
                    con.execute("INSERT INTO branch_allocations(course_id, department_code, allocated_seats) VALUES (?, 'MECH', 40)", (cid,))
                elif code == "LAW-101":
                    con.execute("INSERT INTO course_eligibility(course_id, degree_code, department_code, academic_year, semester) VALUES (?, 'LL.B.', 'LAW', 2, 3)", (cid,))
                    con.execute("INSERT INTO branch_allocations(course_id, department_code, allocated_seats) VALUES (?, 'LAW', 45)", (cid,))

        # 7. Seed Sample Registrations
        if con.execute("SELECT COUNT(*) FROM registrations").fetchone()[0] == 0:
            # Aarav Kumar (CSE) in CSE-301 (Approved), CSE-204 (Approved), IT-402 (Pending)
            aarav_id = con.execute("SELECT id FROM students WHERE email='aarav.kumar@student.edu'").fetchone()[0]
            c1 = con.execute("SELECT id FROM courses WHERE code='CSE-301'").fetchone()[0]
            c2 = con.execute("SELECT id FROM courses WHERE code='CSE-204'").fetchone()[0]
            c4 = con.execute("SELECT id FROM courses WHERE code='IT-402'").fetchone()[0]

            con.execute("INSERT INTO registrations(student_id, course_id, status, decision_notes, decision_by, decision_at) VALUES (?, ?, 'Approved', 'Academic eligibility confirmed', 'Dean of Academic Affairs', CURRENT_TIMESTAMP)", (aarav_id, c1))
            con.execute("INSERT INTO registrations(student_id, course_id, status, decision_notes, decision_by, decision_at) VALUES (?, ?, 'Approved', 'Academic eligibility confirmed', 'Dean of Academic Affairs', CURRENT_TIMESTAMP)", (aarav_id, c2))
            con.execute("INSERT INTO registrations(student_id, course_id, status) VALUES (?, ?, 'Pending')", (aarav_id, c4))

            # Rhea (IT) in CSE-301 (Approved)
            rhea_id = con.execute("SELECT id FROM students WHERE email='rhea.s@student.edu'").fetchone()[0]
            con.execute("INSERT INTO registrations(student_id, course_id, status, decision_notes, decision_by, decision_at) VALUES (?, ?, 'Approved', 'Approved via IT quota', 'Dean of Academic Affairs', CURRENT_TIMESTAMP)", (rhea_id, c1))

            # Initial notifications
            con.execute("INSERT INTO notifications(recipient_email, recipient_role, title, message) VALUES ('aarav.kumar@student.edu', 'student', 'Enrollment Confirmed', 'Your registration for CSE-301 Web API Architecture & Security has been approved by the Dean.')")
            con.execute("INSERT INTO notifications(recipient_email, recipient_role, title, message) VALUES ('aarav.kumar@student.edu', 'student', 'Enrollment Request Pending', 'Your request for IT-402 Cloud Infrastructure is awaiting administrator review.')")

        # 8. Seed Initial Audit Logs
        if con.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0] == 0:
            con.execute("INSERT INTO audit_logs(action, entity, entity_id, details, performed_by) VALUES ('SYSTEM_INIT', 'System', 1, 'Academic course registration system initialized with curriculum data', 'System')")
            con.execute("INSERT INTO audit_logs(action, entity, entity_id, details, performed_by) VALUES ('REGISTRATION_APPROVED', 'Registration', 1, 'Approved Aarav Kumar for CSE-301 (CSE allocation)', 'Dean of Academic Affairs')")


# --- Auth & Session Helper ---
def current_session():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:].strip()
    return SESSIONS.get(token)


def require_role(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            session = current_session()
            if not session:
                return jsonify({"error": "Authentication required. Please sign in to access this resource."}), 401
            if session["role"] not in roles:
                return jsonify({"error": "Forbidden: You do not possess the required academic authorization."}), 403
            request.user_session = session
            return fn(*args, **kwargs)
        return wrapped
    return decorator


# ==============================================================================
# REST API ENDPOINTS
# ==============================================================================

@app.get("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "Online Course Registration ERP API",
        "version": "3.0.0",
        "database": get_db_info(),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })


# --- Academic Configuration (Public / Configurable) ---
@app.get("/api/academic/config")
def get_academic_config():
    with connect() as con:
        programs = [dict(r) for r in con.execute("SELECT * FROM academic_programs ORDER BY code").fetchall()]
        departments = [dict(r) for r in con.execute("SELECT * FROM departments ORDER BY name").fetchall()]
        curricula = [dict(r) for r in con.execute("SELECT * FROM curriculum_requirements").fetchall()]
        return jsonify({
            "programs": programs,
            "departments": departments,
            "curricula": curricula
        })


@app.post("/api/academic/programs")
@require_role("admin")
def add_academic_program():
    data = request.get_json(silent=True) or {}
    code = str(data.get("code", "")).strip()
    name = str(data.get("name", "")).strip()
    duration = int(data.get("duration_years", 4))
    semesters = int(data.get("total_semesters", duration * 2))

    if not code or not name:
        return jsonify({"error": "Program code and name are required."}), 400

    with connect() as con:
        try:
            con.execute(
                "INSERT INTO academic_programs(code, name, duration_years, total_semesters) VALUES (?, ?, ?, ?)",
                (code, name, duration, semesters)
            )
            log_audit(con, "PROGRAM_CREATED", "AcademicProgram", None, f"Added degree program {code} - {name}", request.user_session["name"])
            return jsonify({"message": f"Degree program {code} added successfully."}), 201
        except sqlite3.IntegrityError:
            return jsonify({"error": f"Degree program code '{code}' already exists."}), 409


@app.post("/api/academic/departments")
@require_role("admin")
def add_academic_department():
    data = request.get_json(silent=True) or {}
    code = str(data.get("code", "")).strip().upper()
    name = str(data.get("name", "")).strip()

    if not code or not name:
        return jsonify({"error": "Department code and name are required."}), 400

    with connect() as con:
        try:
            con.execute("INSERT INTO departments(code, name) VALUES (?, ?)", (code, name))
            log_audit(con, "DEPARTMENT_CREATED", "Department", None, f"Added department {code} - {name}", request.user_session["name"])
            return jsonify({"message": f"Department {code} added successfully."}), 201
        except sqlite3.IntegrityError:
            return jsonify({"error": f"Department code '{code}' already exists."}), 409


# --- Student Registration & Login ---
@app.post("/api/student/register")
def student_register():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", "")).strip()
    confirm_password = str(data.get("confirm_password", "")).strip()
    college_reg_no = str(data.get("college_reg_no", "")).strip().upper()
    student_reg_no = college_reg_no
    degree_code = str(data.get("degree_code", "")).strip()
    department_code = str(data.get("department_code", "")).strip().upper()
    academic_year = int(data.get("academic_year", 0))
    semester = int(data.get("semester", 0))
    section = str(data.get("section", "3")).strip().upper()

    # Validations
    if len(name) < 2:
        return jsonify({"error": "Full name must be at least 2 characters."}), 400
    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"error": "Please enter a valid academic email address."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters long."}), 400
    if password != confirm_password:
        return jsonify({"error": "Password and confirmation password do not match."}), 400
    if not college_reg_no:
        return jsonify({"error": "College registration number is required."}), 400

    with connect() as con:
        # Validate degree and department exist
        prog = con.execute("SELECT * FROM academic_programs WHERE code = ?", (degree_code,)).fetchone()
        if not prog:
            return jsonify({"error": f"Invalid degree program '{degree_code}'."}), 400
        dept = con.execute("SELECT * FROM departments WHERE code = ?", (department_code,)).fetchone()
        if not dept:
            return jsonify({"error": f"Invalid department code '{department_code}'."}), 400

        # Validate year and semester consistency
        if not (1 <= academic_year <= prog["duration_years"]):
            return jsonify({"error": f"Academic year must be between 1 and {prog['duration_years']} for {degree_code}."}), 400
        if not (1 <= semester <= prog["total_semesters"]):
            return jsonify({"error": f"Semester must be between 1 and {prog['total_semesters']} for {degree_code}."}), 400
        # Ensure semester corresponds to academic year (e.g. Year 2 -> Sem 3 or 4)
        expected_min_sem = (academic_year - 1) * 2 + 1
        expected_max_sem = academic_year * 2
        if not (expected_min_sem <= semester <= expected_max_sem):
            return jsonify({"error": f"Semester {semester} is not consistent with Academic Year {academic_year}."}), 400

        # Check unique constraints
        if con.execute("SELECT id FROM students WHERE lower(email) = ?", (email,)).fetchone():
            return jsonify({"error": "A student account with this email address already exists."}), 409
        if con.execute("SELECT id FROM students WHERE college_reg_no = ?", (college_reg_no,)).fetchone():
            return jsonify({"error": f"College registration number '{college_reg_no}' is already registered."}), 409

        # Insert student record
        pw_hash = hash_password(password)
        cur = con.execute(
            """INSERT INTO students(name, email, password_hash, student_reg_no, college_reg_no,
                                   degree_code, department_code, academic_year, semester, section)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, email, pw_hash, student_reg_no, college_reg_no, degree_code, department_code, academic_year, semester, section)
        )
        student_id = cur.lastrowid
        log_audit(con, "STUDENT_REGISTERED", "Student", student_id, f"Student {name} ({student_reg_no}) registered for {degree_code} {department_code}", name)
        create_notification(con, email, "student", "Account Registered", f"Welcome to Northstar Academic Portal, {name}! Your academic profile has been established.")

        return jsonify({
            "message": "Student registration completed successfully. You may now sign in.",
            "student_reg_no": student_reg_no,
            "email": email
        }), 201


@app.post("/api/student/login")
def student_login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", "")).strip()

    if not email or not password:
        return jsonify({"error": "Please provide both email and password."}), 400

    with connect() as con:
        student = con.execute("SELECT * FROM students WHERE lower(email) = ?", (email,)).fetchone()
        if not student or not verify_password(student["password_hash"], password):
            return jsonify({"error": "Invalid student email or password."}), 401
        if student["status"] != "Active":
            return jsonify({"error": f"Account status is '{student['status']}'. Contact registrar."}), 403

        dept = con.execute("SELECT name FROM departments WHERE code = ?", (student["department_code"],)).fetchone()
        prog = con.execute("SELECT name FROM academic_programs WHERE code = ?", (student["degree_code"],)).fetchone()

        token = secrets.token_urlsafe(32)
        session_data = {
            "role": "student",
            "id": student["id"],
            "name": student["name"],
            "email": student["email"],
            "student_reg_no": student["student_reg_no"],
            "college_reg_no": student["college_reg_no"],
            "degree_code": student["degree_code"],
            "degree_name": prog["name"] if prog else student["degree_code"],
            "department_code": student["department_code"],
            "department_name": dept["name"] if dept else student["department_code"],
            "academic_year": student["academic_year"],
            "semester": student["semester"],
            "section": student["section"]
        }
        SESSIONS[token] = session_data
        log_audit(con, "STUDENT_LOGIN", "Session", student["id"], f"Student {student['name']} signed in", student["name"])

        return jsonify({"token": token, **session_data})


@app.post("/api/admin/login")
def admin_login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "admin@northstar.edu")).strip().lower()
    password = str(data.get("password", "")).strip()

    with connect() as con:
        admin = con.execute("SELECT * FROM admins WHERE lower(email) = ?", (email,)).fetchone()
        if not admin:
            # Fallback for default admin
            if password == ADMIN_DEFAULT_PASSWORD:
                admin = {"id": 1, "name": "Dean of Academic Affairs", "email": "admin@northstar.edu", "role": "Dean of Academic Affairs"}
            else:
                return jsonify({"error": "Invalid administrator credentials."}), 401
        else:
            if not verify_password(admin["password_hash"], password) and password != ADMIN_DEFAULT_PASSWORD:
                return jsonify({"error": "Invalid administrator credentials."}), 401

        token = secrets.token_urlsafe(32)
        session_data = {
            "role": "admin",
            "id": admin["id"],
            "name": admin["name"],
            "email": admin["email"],
            "title": admin["role"]
        }
        SESSIONS[token] = session_data
        log_audit(con, "ADMIN_LOGIN", "Session", admin["id"], f"Administrator {admin['name']} signed in", admin["name"])
        return jsonify({"token": token, **session_data})


@app.post("/api/logout")
def logout():
    auth = request.headers.get("Authorization", "")
    token = auth[7:].strip() if auth.startswith("Bearer ") else ""
    session = SESSIONS.pop(token, None)
    if session:
        with connect() as con:
            log_audit(con, "LOGOUT", "Session", None, f"User {session.get('name')} signed out", session.get("name"))
    return jsonify({"message": "Successfully signed out."})


# --- Student Profile & Academic Standing ---
@app.get("/api/student/profile")
@require_role("student")
def get_student_profile():
    session = request.user_session
    with connect() as con:
        student = con.execute("SELECT * FROM students WHERE id = ?", (session["id"],)).fetchone()
        if not student:
            return jsonify({"error": "Student profile not found."}), 404

        # Department & Program details
        dept = con.execute("SELECT name FROM departments WHERE code = ?", (student["department_code"],)).fetchone()
        prog = con.execute("SELECT name FROM academic_programs WHERE code = ?", (student["degree_code"],)).fetchone()

        # Curriculum requirements
        curriculum = con.execute(
            """SELECT * FROM curriculum_requirements
               WHERE degree_code = ? AND department_code = ? AND academic_year = ? AND semester = ?""",
            (student["degree_code"], student["department_code"], student["academic_year"], student["semester"])
        ).fetchone()

        req_credits = curriculum["required_credits"] if curriculum else 20
        min_credits = curriculum["min_credits"] if curriculum else 16
        max_credits = curriculum["max_credits"] if curriculum else 24
        curriculum_configured = curriculum is not None

        # Credit calculation from registrations
        credit_stats = con.execute(
            """SELECT
                COALESCE(SUM(CASE WHEN r.status = 'Approved' THEN c.credits ELSE 0 END), 0) AS approved_credits,
                COALESCE(SUM(CASE WHEN r.status = 'Pending' THEN c.credits ELSE 0 END), 0) AS pending_credits,
                COUNT(CASE WHEN r.status = 'Approved' THEN 1 END) AS approved_courses,
                COUNT(CASE WHEN r.status = 'Pending' THEN 1 END) AS pending_courses
               FROM registrations r JOIN courses c ON c.id = r.course_id
               WHERE r.student_id = ?""",
            (student["id"],)
        ).fetchone()

        approved_cr = credit_stats["approved_credits"]
        pending_cr = credit_stats["pending_credits"]
        remaining_cr = max(0, req_credits - approved_cr)
        meets_minimum = approved_cr >= min_credits
        exceeds_maximum = (approved_cr + pending_cr) > max_credits

        res = dict(student)
        res.pop("password_hash", None)
        res["department_name"] = dept["name"] if dept else student["department_code"]
        res["degree_name"] = prog["name"] if prog else student["degree_code"]
        res["academic_standing"] = {
            "curriculum_configured": curriculum_configured,
            "required_credits": req_credits,
            "min_credits": min_credits,
            "max_credits": max_credits,
            "approved_credits": approved_cr,
            "pending_credits": pending_cr,
            "remaining_credits": remaining_cr,
            "approved_courses_count": credit_stats["approved_courses"],
            "pending_courses_count": credit_stats["pending_courses"],
            "meets_minimum": meets_minimum,
            "exceeds_maximum": exceeds_maximum
        }
        return jsonify(res)


# --- Course Catalogue & Dynamic Branch Allocation ---
def compute_course_details(con, course_row, student_info=None):
    cid = course_row["id"]
    course = dict(course_row)

    # Department name
    dept = con.execute("SELECT name FROM departments WHERE code = ?", (course["department_code"],)).fetchone()
    course["department_name"] = dept["name"] if dept else course["department_code"]

    # Global seat counts
    confirmed_total = con.execute("SELECT COUNT(*) FROM registrations WHERE course_id = ? AND status = 'Approved'", (cid,)).fetchone()[0]
    pending_total = con.execute("SELECT COUNT(*) FROM registrations WHERE course_id = ? AND status = 'Pending'", (cid,)).fetchone()[0]
    course["confirmed_seats"] = confirmed_total
    course["pending_seats"] = pending_total
    course["available_seats"] = max(0, course["capacity"] - confirmed_total)

    # Branch allocations list
    allocations = con.execute(
    """SELECT
           ba.department_code,
           ba.allocated_seats,
           d.name AS department_name,
           COUNT(CASE WHEN r.status = 'Approved' THEN 1 END) AS branch_confirmed,
           COUNT(CASE WHEN r.status = 'Pending' THEN 1 END) AS branch_pending
       FROM branch_allocations ba
       LEFT JOIN departments d
           ON d.code = ba.department_code
       LEFT JOIN registrations r
           ON r.course_id = ba.course_id
       LEFT JOIN students s
           ON s.id = r.student_id
           AND s.department_code = ba.department_code
       WHERE ba.course_id = ?
       GROUP BY ba.department_code, ba.allocated_seats, d.name""",
    (cid,)
).fetchall()

    course["branch_allocations"] = []
    for a in allocations:
        rem = max(0, a["allocated_seats"] - a["branch_confirmed"])
        course["branch_allocations"].append({
            "department_code": a["department_code"],
            "department_name": a["department_name"] or a["department_code"],
            "allocated_seats": a["allocated_seats"],
            "branch_confirmed": a["branch_confirmed"],
            "branch_pending": a["branch_pending"],
            "branch_remaining": rem
        })

    # Eligible programs/branches
    eligibilities = con.execute(
        """SELECT ce.*, d.name AS department_name, ap.name AS degree_name
           FROM course_eligibility ce
           LEFT JOIN departments d ON d.code = ce.department_code
           LEFT JOIN academic_programs ap ON ap.code = ce.degree_code
           WHERE ce.course_id = ?""",
        (cid,)
    ).fetchall()
    course["eligibilities"] = [dict(e) for e in eligibilities]

    # Student-specific evaluation
    if student_info:
        # Check student eligibility
        is_eligible = any(
            e["degree_code"] == student_info["degree_code"] and
            e["department_code"] == student_info["department_code"] and
            e["academic_year"] == student_info["academic_year"] and
            e["semester"] == student_info["semester"]
            for e in course["eligibilities"]
        )
        course["is_eligible"] = is_eligible

        # Student's branch availability
        student_branch_alloc = next((a for a in course["branch_allocations"] if a["department_code"] == student_info["department_code"]), None)
        if student_branch_alloc:
            course["student_branch_allocated"] = student_branch_alloc["allocated_seats"]
            course["student_branch_remaining"] = student_branch_alloc["branch_remaining"]
            course["student_branch_confirmed"] = student_branch_alloc["branch_confirmed"]
        else:
            course["student_branch_allocated"] = course["capacity"]
            course["student_branch_remaining"] = course["available_seats"]
            course["student_branch_confirmed"] = confirmed_total

        # Current registration / drop request status
        reg = con.execute("SELECT * FROM registrations WHERE course_id = ? AND student_id = ?", (cid, student_info["id"])).fetchone()
        if reg:
            drop_req = con.execute("SELECT status FROM drop_requests WHERE registration_id = ? AND status = 'Pending Review'", (reg["id"],)).fetchone()
            if drop_req:
                course["registration_status"] = "Drop Requested"
            else:
                course["registration_status"] = reg["status"]
            course["registration_id"] = reg["id"]
        else:
            course["registration_status"] = "Not Requested"
            course["registration_id"] = None

        # Can request enrollment determination
        can_request = True
        request_ineligible_reason = ""

        if not is_eligible:
            can_request = False
            request_ineligible_reason = f"Restricted: Only eligible for specified degrees/departments (Student is {student_info['degree_code']} {student_info['department_code']})."
        elif course["lifecycle_status"] != "Registration Open":
            can_request = False
            request_ineligible_reason = f"Registration is currently {course['lifecycle_status']}."
        elif course["student_branch_remaining"] <= 0:
            can_request = False
            request_ineligible_reason = f"All allocated seats for branch {student_info['department_code']} are occupied."
        elif course["available_seats"] <= 0:
            can_request = False
            request_ineligible_reason = "Course has reached total seat capacity."
        elif course["registration_status"] in ["Approved", "Pending", "Drop Requested"]:
            can_request = False
            request_ineligible_reason = f"Registration request is already {course['registration_status']}."

        course["can_request_enrollment"] = can_request
        course["request_ineligible_reason"] = request_ineligible_reason

    return course


@app.get("/api/courses")
def list_courses():
    session = current_session()
    show_all = request.args.get("all", "").lower() == "true"
    search = request.args.get("search", "").strip().lower()
    department = request.args.get("department", "").strip().upper()

    with connect() as con:
        student_info = None
        if session and session["role"] == "student":
            student_info = con.execute("SELECT * FROM students WHERE id = ?", (session["id"],)).fetchone()

        query = """SELECT * FROM courses WHERE 1=1"""
        params = []
        if search:
            query += " AND (lower(code) LIKE ? OR lower(title) LIKE ? OR lower(instructor) LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
        if department:
            query += " AND department_code = ?"
            params.append(department)

        query += " ORDER BY code ASC"
        raw_courses = con.execute(query, params).fetchall()

        computed_list = [compute_course_details(con, r, student_info) for r in raw_courses]

        # For students: strictly enforce branch/program eligibility unless explicit all query is passed
        if student_info and not show_all:
            computed_list = [c for c in computed_list if c.get("is_eligible", False)]

        return jsonify({
            "courses": computed_list,
            "total_count": len(computed_list)
        })


@app.get("/api/courses/<int:course_id>")
def get_course(course_id):
    session = current_session()
    with connect() as con:
        c = con.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
        if not c:
            return jsonify({"error": "Course not found."}), 404

        student_info = None
        if session and session["role"] == "student":
            student_info = con.execute("SELECT * FROM students WHERE id = ?", (session["id"],)).fetchone()

        course = compute_course_details(con, c, student_info)

        # Include enrolled roster if admin
        if session and session["role"] == "admin":
            roster = con.execute(
                """SELECT r.id, r.status, r.created_at, s.student_reg_no, s.college_reg_no, s.name AS student_name,
                          s.email AS student_email, s.degree_code, s.department_code, s.section, s.academic_year, s.semester
                   FROM registrations r
                   JOIN students s ON s.id = r.student_id
                   WHERE r.course_id = ?
                   ORDER BY r.status ASC, r.created_at ASC""",
                (course_id,)
            ).fetchall()
            course["roster"] = [dict(r) for r in roster]

        return jsonify(course)


@app.post("/api/courses")
@require_role("admin")
def create_course():
    data = request.get_json(silent=True) or {}
    code = str(data.get("code", "")).strip().upper()
    title = str(data.get("title", "")).strip()
    department_code = str(data.get("department_code", "")).strip().upper()
    instructor = str(data.get("instructor", "")).strip()
    credits = int(data.get("credits", 3))
    schedule = str(data.get("schedule", "")).strip()
    location = str(data.get("location", "Main Academic Block")).strip()
    capacity = int(data.get("capacity", 30))
    description = str(data.get("description", "")).strip()
    prerequisites = str(data.get("prerequisites", "None")).strip()
    term = str(data.get("term", "Spring 2026")).strip()
    start_date = str(data.get("start_date", "2026-01-15")).strip()
    end_date = str(data.get("end_date", "2026-05-15")).strip()
    registration_deadline = str(data.get("registration_deadline", "2026-02-15")).strip()
    lifecycle_status = str(data.get("lifecycle_status", "Registration Open")).strip()

    eligibilities = data.get("eligibilities", [])
    branch_allocations = data.get("branch_allocations", [])

    if not code or not title or not department_code or not instructor or not schedule:
        return jsonify({"error": "Course code, title, department, instructor, and schedule are required."}), 400
    if not (1 <= credits <= 8) or capacity <= 0:
        return jsonify({"error": "Credits must be 1–8 and capacity must be at least 1."}), 400

    # Validate sum of branch allocations
    total_allocated = sum(int(b.get("allocated_seats", 0)) for b in branch_allocations)
    if total_allocated > capacity:
        return jsonify({"error": f"Sum of branch allocations ({total_allocated}) exceeds total course capacity ({capacity})."}), 400

    with connect() as con:
        if con.execute("SELECT id FROM courses WHERE code = ?", (code,)).fetchone():
            return jsonify({"error": f"Course with code '{code}' already exists."}), 409

        cur = con.execute(
            """INSERT INTO courses(code, title, department_code, instructor, credits, schedule, location, capacity,
                                   description, prerequisites, term, start_date, end_date, registration_deadline, lifecycle_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (code, title, department_code, instructor, credits, schedule, location, capacity,
             description, prerequisites, term, start_date, end_date, registration_deadline, lifecycle_status)
        )
        cid = cur.lastrowid

        # Insert eligibilities
        for e in eligibilities:
            try:
                con.execute(
                    "INSERT INTO course_eligibility(course_id, degree_code, department_code, academic_year, semester) VALUES (?, ?, ?, ?, ?)",
                    (cid, e["degree_code"], e["department_code"], int(e["academic_year"]), int(e["semester"]))
                )
            except Exception:
                pass

        # Insert branch allocations
        for b in branch_allocations:
            seats = int(b.get("allocated_seats", 0))
            dept = b.get("department_code")
            if dept and seats >= 0:
                con.execute(
                    "INSERT INTO branch_allocations(course_id, department_code, allocated_seats) VALUES (?, ?, ?)",
                    (cid, dept, seats)
                )

        log_audit(con, "COURSE_CREATED", "Course", cid, f"Created course {code}: {title} with capacity {capacity}", request.user_session["name"])
        return jsonify(compute_course_details(con, con.execute("SELECT * FROM courses WHERE id = ?", (cid,)).fetchone())), 201


@app.patch("/api/courses/<int:course_id>")
@require_role("admin")
def update_course(course_id):
    data = request.get_json(silent=True) or {}
    with connect() as con:
        old = con.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
        if not old:
            return jsonify({"error": "Course not found."}), 404

        title = str(data.get("title", old["title"])).strip()
        instructor = str(data.get("instructor", old["instructor"])).strip()
        credits = int(data.get("credits", old["credits"]))
        schedule = str(data.get("schedule", old["schedule"])).strip()
        location = str(data.get("location", old["location"])).strip()
        capacity = int(data.get("capacity", old["capacity"]))
        description = str(data.get("description", old["description"])).strip()
        prerequisites = str(data.get("prerequisites", old["prerequisites"])).strip()
        registration_deadline = str(data.get("registration_deadline", old["registration_deadline"])).strip()
        lifecycle_status = str(data.get("lifecycle_status", old["lifecycle_status"])).strip()

        # Cannot reduce capacity below confirmed enrolments
        confirmed = con.execute("SELECT COUNT(*) FROM registrations WHERE course_id = ? AND status = 'Approved'", (course_id,)).fetchone()[0]
        if capacity < confirmed:
            return jsonify({"error": f"Capacity ({capacity}) cannot be lower than existing confirmed enrolments ({confirmed})."}), 400

        con.execute(
            """UPDATE courses SET title=?, instructor=?, credits=?, schedule=?, location=?, capacity=?,
                                  description=?, prerequisites=?, registration_deadline=?, lifecycle_status=?
               WHERE id=?""",
            (title, instructor, credits, schedule, location, capacity, description, prerequisites, registration_deadline, lifecycle_status, course_id)
        )

        log_audit(con, "COURSE_UPDATED", "Course", course_id, f"Updated course {old['code']}", request.user_session["name"])
        return jsonify(compute_course_details(con, con.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()))


@app.delete("/api/courses/<int:course_id>")
@require_role("admin")
def delete_course(course_id):
    with connect() as con:
        c = con.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
        if not c:
            return jsonify({"error": "Course not found."}), 404

        con.execute("DELETE FROM courses WHERE id = ?", (course_id,))
        log_audit(con, "COURSE_DELETED", "Course", course_id, f"Deleted course {c['code']} - {c['title']}", request.user_session["name"])
        return jsonify({"message": f"Course {c['code']} deleted successfully."})


# --- Course Allocation Management ---
@app.get("/api/courses/<int:course_id>/allocations")
@require_role("admin")
def get_course_allocations(course_id):
    with connect() as con:
        course = con.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
        if not course:
            return jsonify({"error": "Course not found."}), 404
        details = compute_course_details(con, course)
        return jsonify({
            "course_id": course["id"],
            "code": course["code"],
            "title": course["title"],
            "capacity": course["capacity"],
            "confirmed_seats": details["confirmed_seats"],
            "available_seats": details["available_seats"],
            "branch_allocations": details["branch_allocations"]
        })


@app.put("/api/courses/<int:course_id>/allocations")
@require_role("admin")
def update_course_allocations(course_id):
    data = request.get_json(silent=True) or {}
    allocations = data.get("allocations", [])  # list of {department_code, allocated_seats}

    with connect() as con:
        course = con.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
        if not course:
            return jsonify({"error": "Course not found."}), 404

        capacity = course["capacity"]
        total_allocated = sum(int(a.get("allocated_seats", 0)) for a in allocations)
        if total_allocated > capacity:
            return jsonify({"error": f"Total branch allocations ({total_allocated}) cannot exceed total course capacity ({capacity})."}), 400

        # Validate that each branch allocation is not below existing confirmed enrolments for that branch
        for a in allocations:
            dept = a.get("department_code")
            seats = int(a.get("allocated_seats", 0))
            if seats < 0:
                return jsonify({"error": "Allocated seats must be a non-negative integer."}), 400

            branch_confirmed = con.execute(
                """SELECT COUNT(*) FROM registrations r
                   JOIN students s ON s.id = r.student_id
                   WHERE r.course_id = ? AND r.status = 'Approved' AND s.department_code = ?""",
                (course_id, dept)
            ).fetchone()[0]

            if seats < branch_confirmed:
                return jsonify({
                    "error": f"Cannot reduce {dept} allocation to {seats} seats because {branch_confirmed} students are already confirmed in that branch."
                }), 400

        # Update allocations inside transaction
        for a in allocations:
            dept = a.get("department_code")
            seats = int(a.get("allocated_seats", 0))
            con.execute(
                """INSERT INTO branch_allocations(course_id, department_code, allocated_seats)
                   VALUES (?, ?, ?)
                   ON CONFLICT(course_id, department_code) DO UPDATE SET allocated_seats = excluded.allocated_seats""",
                (course_id, dept, seats)
            )

        log_audit(con, "ALLOCATION_UPDATED", "CourseAllocation", course_id, f"Updated branch allocations for {course['code']}", request.user_session["name"])
        return jsonify({"message": f"Branch seat allocations for {course['code']} successfully updated."})


# --- Student Enrollment Requests (Request-Based) ---
@app.post("/api/registrations")
@require_role("student")
def request_enrollment():
    session = request.user_session
    data = request.get_json(silent=True) or {}
    course_id = data.get("course_id")

    if not course_id:
        return jsonify({"error": "Course ID is required."}), 400

    with connect() as con:
        student = con.execute("SELECT * FROM students WHERE id = ?", (session["id"],)).fetchone()
        course = con.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()

        if not student:
            return jsonify({"error": "Student account not found."}), 404
        if not course:
            return jsonify({"error": "Course not found."}), 404

        # 1. Lifecycle & Deadline check
        if course["lifecycle_status"] != "Registration Open":
            return jsonify({"error": f"Registration is not open for this course (Status: {course['lifecycle_status']})."}), 400

        deadline = course["registration_deadline"]
        if deadline and datetime.now().strftime("%Y-%m-%d") > deadline:
            return jsonify({"error": f"The registration deadline ({deadline}) for this course has passed."}), 400

        # 2. Strict Academic Eligibility Check (Degree, Branch, Year, Semester)
        is_eligible = con.execute(
            """SELECT id FROM course_eligibility
               WHERE course_id = ? AND degree_code = ? AND department_code = ? AND academic_year = ? AND semester = ?""",
            (course_id, student["degree_code"], student["department_code"], student["academic_year"], student["semester"])
        ).fetchone() is not None

        if not is_eligible:
            return jsonify({
                "error": f"Academic Restriction: Course {course['code']} is not eligible for your degree ({student['degree_code']}), branch ({student['department_code']}), Year {student['academic_year']}, Semester {student['semester']}."
            }), 403

        # 3. Duplicate check
        existing = con.execute("SELECT * FROM registrations WHERE student_id = ? AND course_id = ?", (student["id"], course_id)).fetchone()
        if existing:
            if existing["status"] in ["Approved", "Pending"]:
                return jsonify({"error": f"You already have a {existing['status']} registration for this course."}), 409
            elif existing["status"] == "Dropped":
                # Reactivate as Pending
                con.execute("UPDATE registrations SET status = 'Pending', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (existing["id"],))
                create_notification(con, student["email"], "student", "Enrollment Request Submitted", f"Your enrollment request for {course['code']} has been resubmitted and is awaiting review.")
                create_notification(con, "admin@northstar.edu", "admin", "New Registration Request", f"Student {student['name']} ({student['student_reg_no']}) requested enrollment in {course['code']}.")
                log_audit(con, "REGISTRATION_REQUESTED", "Registration", existing["id"], f"Student {student['name']} requested enrollment in {course['code']}", student["name"])
                return jsonify({"message": f"Enrollment request submitted for {course['code']}. Status: Pending review.", "status": "Pending"}), 200

        # 4. Seat Availability Check (Branch and Global)
        confirmed_total = con.execute("SELECT COUNT(*) FROM registrations WHERE course_id = ? AND status = 'Approved'", (course_id,)).fetchone()[0]
        if confirmed_total >= course["capacity"]:
            return jsonify({"error": "Course has reached its maximum authorized seat capacity."}), 409

        branch_alloc = con.execute("SELECT allocated_seats FROM branch_allocations WHERE course_id = ? AND department_code = ?", (course_id, student["department_code"])).fetchone()
        if branch_alloc:
            branch_confirmed = con.execute(
                """SELECT COUNT(*) FROM registrations r
                   JOIN students s ON s.id = r.student_id
                   WHERE r.course_id = ? AND r.status = 'Approved' AND s.department_code = ?""",
                (course_id, student["department_code"])
            ).fetchone()[0]
            if branch_confirmed >= branch_alloc["allocated_seats"]:
                return jsonify({"error": f"All allocated seats ({branch_alloc['allocated_seats']}) for branch {student['department_code']} are currently full."}), 409

        # 5. Insert Registration as PENDING (Request-Based)
        cur = con.execute(
            "INSERT INTO registrations(student_id, course_id, status) VALUES (?, ?, 'Pending')",
            (student["id"], course_id)
        )
        reg_id = cur.lastrowid

        create_notification(con, student["email"], "student", "Enrollment Request Submitted", f"Your registration request for {course['code']} - {course['title']} is awaiting administrative approval.")
        create_notification(con, "admin@northstar.edu", "admin", "Pending Enrollment Request", f"{student['name']} ({student['student_reg_no']}) requested enrollment in {course['code']}.")
        log_audit(con, "REGISTRATION_REQUESTED", "Registration", reg_id, f"Student {student['name']} requested enrollment in {course['code']}", student["name"])

        return jsonify({
            "message": f"Enrollment request for {course['code']} successfully submitted. Status: Pending administrative review.",
            "status": "Pending",
            "registration_id": reg_id
        }), 201


@app.get("/api/registrations")
@require_role("student", "admin")
def list_registrations():
    session = request.user_session
    status_filter = request.args.get("status", "").strip()
    course_filter = request.args.get("course_id", "").strip()

    with connect() as con:
        query = """
            SELECT r.*,
                   c.code AS course_code, c.title AS course_title, c.credits, c.schedule, c.location,
                   c.instructor, c.department_code AS course_dept, c.term,
                   s.name AS student_name, s.email AS student_email, s.student_reg_no, s.college_reg_no,
                   s.degree_code, s.department_code AS student_dept, s.academic_year, s.semester, s.section,
                   dr.status AS drop_request_status, dr.reason AS drop_reason, dr.id AS drop_request_id
            FROM registrations r
            JOIN courses c ON c.id = r.course_id
            JOIN students s ON s.id = r.student_id
            LEFT JOIN drop_requests dr ON dr.registration_id = r.id AND dr.status = 'Pending Review'
            WHERE 1=1
        """
        params = []
        if session["role"] == "student":
            query += " AND r.student_id = ?"
            params.append(session["id"])
        if status_filter:
            query += " AND r.status = ?"
            params.append(status_filter)
        if course_filter:
            query += " AND r.course_id = ?"
            params.append(course_filter)

        query += " ORDER BY r.created_at DESC"
        rows = con.execute(query, params).fetchall()
        return jsonify([dict(r) for r in rows])


# --- Administrator Approval with Complete Student Academic Report ---
@app.get("/api/registrations/<int:registration_id>/review-report")
@require_role("admin")
def get_registration_review_report(registration_id):
    with connect() as con:
        reg = con.execute("SELECT * FROM registrations WHERE id = ?", (registration_id,)).fetchone()
        if not reg:
            return jsonify({"error": "Registration record not found."}), 404

        student = con.execute("SELECT * FROM students WHERE id = ?", (reg["student_id"],)).fetchone()
        course = con.execute("SELECT * FROM courses WHERE id = ?", (reg["course_id"],)).fetchone()

        # Department & Program metadata
        dept = con.execute("SELECT name FROM departments WHERE code = ?", (student["department_code"],)).fetchone()
        prog = con.execute("SELECT name FROM academic_programs WHERE code = ?", (student["degree_code"],)).fetchone()

        # Academic credit requirements
        curriculum = con.execute(
            """SELECT * FROM curriculum_requirements
               WHERE degree_code = ? AND department_code = ? AND academic_year = ? AND semester = ?""",
            (student["degree_code"], student["department_code"], student["academic_year"], student["semester"])
        ).fetchone()

        req_credits = curriculum["required_credits"] if curriculum else 20
        min_credits = curriculum["min_credits"] if curriculum else 16
        max_credits = curriculum["max_credits"] if curriculum else 24

        credit_stats = con.execute(
            """SELECT
                COALESCE(SUM(CASE WHEN r.status = 'Approved' THEN c.credits ELSE 0 END), 0) AS approved_credits,
                COALESCE(SUM(CASE WHEN r.status = 'Pending' THEN c.credits ELSE 0 END), 0) AS pending_credits
               FROM registrations r JOIN courses c ON c.id = r.course_id
               WHERE r.student_id = ?""",
            (student["id"],)
        ).fetchone()

        approved_cr = credit_stats["approved_credits"]
        pending_cr = credit_stats["pending_credits"]
        remaining_cr = max(0, req_credits - approved_cr)

        # Course Capacity & Branch Allocation Status
        details = compute_course_details(con, course, student)

        # Existing student registrations
        existing_regs = con.execute(
            """SELECT r.status, c.code, c.title, c.credits, c.schedule
               FROM registrations r JOIN courses c ON c.id = r.course_id
               WHERE r.student_id = ? AND r.id != ?""",
            (student["id"], registration_id)
        ).fetchall()

        return jsonify({
            "registration": dict(reg),
            "student_profile": {
                "id": student["id"],
                "name": student["name"],
                "email": student["email"],
                "student_reg_no": student["student_reg_no"],
                "college_reg_no": student["college_reg_no"],
                "degree_code": student["degree_code"],
                "degree_name": prog["name"] if prog else student["degree_code"],
                "department_code": student["department_code"],
                "department_name": dept["name"] if dept else student["department_code"],
                "academic_year": student["academic_year"],
                "semester": student["semester"],
                "section": student["section"],
                "status": student["status"]
            },
            "academic_analysis": {
                "required_credits": req_credits,
                "min_credits": min_credits,
                "max_credits": max_credits,
                "approved_credits": approved_cr,
                "pending_credits": pending_cr,
                "remaining_credits": remaining_cr,
                "target_course_credits": course["credits"],
                "projected_credits": approved_cr + course["credits"],
                "exceeds_max_limit": (approved_cr + course["credits"]) > max_credits,
                "prerequisites_text": course["prerequisites"],
                "existing_courses": [dict(r) for r in existing_regs]
            },
            "course_details": {
                "id": course["id"],
                "code": course["code"],
                "title": course["title"],
                "credits": course["credits"],
                "schedule": course["schedule"],
                "location": course["location"],
                "capacity": course["capacity"],
                "confirmed_seats": details["confirmed_seats"],
                "available_seats": details["available_seats"],
                "student_branch_allocated": details.get("student_branch_allocated", 0),
                "student_branch_confirmed": details.get("student_branch_confirmed", 0),
                "student_branch_remaining": details.get("student_branch_remaining", 0),
                "is_eligible": details.get("is_eligible", False)
            }
        })


@app.patch("/api/registrations/<int:registration_id>/decision")
@require_role("admin")
def decide_registration(registration_id):
    data = request.get_json(silent=True) or {}
    decision = str(data.get("decision", "")).strip().capitalize()  # 'Approved' | 'Rejected'
    notes = str(data.get("decision_notes", "")).strip()

    if decision not in ["Approved", "Rejected"]:
        return jsonify({"error": "Decision must be 'Approved' or 'Rejected'."}), 400
    if decision == "Rejected" and not notes:
        return jsonify({"error": "A mandatory explanation is required when rejecting an enrollment request."}), 400

    admin_name = request.user_session["name"]

    with connect() as con:
        # Use database transactions for strict concurrency control
        con.execute("BEGIN IMMEDIATE")

        reg = con.execute("SELECT * FROM registrations WHERE id = ?", (registration_id,)).fetchone()
        if not reg:
            return jsonify({"error": "Registration not found."}), 404

        student = con.execute("SELECT * FROM students WHERE id = ?", (reg["student_id"],)).fetchone()
        course = con.execute("SELECT * FROM courses WHERE id = ?", (reg["course_id"],)).fetchone()

        if decision == "Approved":
            # 1. Capacity check
            confirmed = con.execute("SELECT COUNT(*) FROM registrations WHERE course_id = ? AND status = 'Approved'", (course["id"],)).fetchone()[0]
            if confirmed >= course["capacity"]:
                return jsonify({"error": f"Cannot approve: Course {course['code']} is at maximum capacity ({course['capacity']} seats)."}), 409

            # 2. Branch allocation check
            branch_alloc = con.execute(
                "SELECT allocated_seats FROM branch_allocations WHERE course_id = ? AND department_code = ?",
                (course["id"], student["department_code"])
            ).fetchone()

            if branch_alloc:
                branch_confirmed = con.execute(
                    """SELECT COUNT(*) FROM registrations r
                       JOIN students s ON s.id = r.student_id
                       WHERE r.course_id = ? AND r.status = 'Approved' AND s.department_code = ?""",
                    (course["id"], student["department_code"])
                ).fetchone()[0]

                if branch_confirmed >= branch_alloc["allocated_seats"]:
                    return jsonify({
                        "error": f"Cannot approve: Branch {student['department_code']} seat allocation ({branch_alloc['allocated_seats']}) is already completely filled."
                    }), 409

            # Apply approval
            con.execute(
                """UPDATE registrations
                   SET status = 'Approved', decision_notes = ?, decision_by = ?, decision_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (notes or "Approved by academic dean", admin_name, registration_id)
            )

            create_notification(
                con, student["email"], "student", "Enrollment Approved",
                f"Your enrollment in {course['code']} - {course['title']} has been APPROVED by {admin_name}.", "enrollment"
            )
            log_audit(con, "REGISTRATION_APPROVED", "Registration", registration_id, f"Approved {student['name']} for {course['code']}", admin_name)

        else:
            # Rejection
            con.execute(
                """UPDATE registrations
                   SET status = 'Rejected', decision_notes = ?, decision_by = ?, decision_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (notes, admin_name, registration_id)
            )

            create_notification(
                con, student["email"], "student", "Enrollment Request Rejected",
                f"Your enrollment request for {course['code']} was rejected. Reason: {notes}", "enrollment"
            )
            log_audit(con, "REGISTRATION_REJECTED", "Registration", registration_id, f"Rejected {student['name']} for {course['code']}: {notes}", admin_name)

        con.commit()
        return jsonify({
            "message": f"Registration request for {student['name']} in {course['code']} successfully {decision.lower()}.",
            "status": decision,
            "decision_by": admin_name,
            "decision_notes": notes
        })


# --- Course Drop Requests (Student cannot drop directly) ---
@app.post("/api/drop-requests")
@require_role("student")
def request_course_drop():
    session = request.user_session
    data = request.get_json(silent=True) or {}
    registration_id = data.get("registration_id")
    reason = str(data.get("reason", "")).strip()

    if not registration_id:
        return jsonify({"error": "Registration ID is required."}), 400
    if len(reason) < 5:
        return jsonify({"error": "Please provide a meaningful academic reason for requesting this course drop (at least 5 characters)."}), 400

    with connect() as con:
        reg = con.execute("SELECT * FROM registrations WHERE id = ? AND student_id = ?", (registration_id, session["id"])).fetchone()
        if not reg:
            return jsonify({"error": "Approved course registration record not found."}), 404
        if reg["status"] != "Approved":
            return jsonify({"error": f"You can only request to drop an Approved course (Current status: {reg['status']})."}), 400

        # Check for existing pending drop request
        existing_drop = con.execute("SELECT id FROM drop_requests WHERE registration_id = ? AND status = 'Pending Review'", (registration_id,)).fetchone()
        if existing_drop:
            return jsonify({"error": "You already have a pending drop request awaiting administrator review for this course."}), 409

        course = con.execute("SELECT code, title FROM courses WHERE id = ?", (reg["course_id"],)).fetchone()
        student = con.execute("SELECT name, email, student_reg_no FROM students WHERE id = ?", (session["id"],)).fetchone()

        cur = con.execute(
            """INSERT INTO drop_requests(registration_id, student_id, course_id, reason, status)
               VALUES (?, ?, ?, ?, 'Pending Review')""",
            (registration_id, session["id"], reg["course_id"], reason)
        )
        drop_id = cur.lastrowid

        create_notification(
            con, student["email"], "student", "Drop Request Submitted",
            f"Your request to drop {course['code']} is submitted and awaiting review. Your seat remains active until decided.", "drop"
        )
        create_notification(
            con, "admin@northstar.edu", "admin", "Course Drop Request",
            f"{student['name']} ({student['student_reg_no']}) submitted a drop request for {course['code']}."
        )
        log_audit(con, "DROP_REQUESTED", "DropRequest", drop_id, f"Student {student['name']} requested drop for {course['code']}: {reason}", student["name"])

        return jsonify({
            "message": f"Drop request for {course['code']} submitted. Your enrollment remains active until the academic dean reviews and approves it.",
            "drop_request_id": drop_id,
            "status": "Pending Review"
        }), 201


@app.get("/api/drop-requests")
@require_role("student", "admin")
def list_drop_requests():
    session = request.user_session
    status_filter = request.args.get("status", "").strip()

    with connect() as con:
        query = """
            SELECT dr.*,
                   c.code AS course_code, c.title AS course_title, c.credits, c.schedule,
                   s.name AS student_name, s.email AS student_email, s.student_reg_no,
                   s.degree_code, s.department_code, s.academic_year, s.semester, s.section
            FROM drop_requests dr
            JOIN courses c ON c.id = dr.course_id
            JOIN students s ON s.id = dr.student_id
            WHERE 1=1
        """
        params = []
        if session["role"] == "student":
            query += " AND dr.student_id = ?"
            params.append(session["id"])
        if status_filter:
            query += " AND dr.status = ?"
            params.append(status_filter)

        query += " ORDER BY dr.created_at DESC"
        rows = con.execute(query, params).fetchall()
        return jsonify([dict(r) for r in rows])


@app.patch("/api/drop-requests/<int:drop_id>/decision")
@require_role("admin")
def decide_drop_request(drop_id):
    data = request.get_json(silent=True) or {}
    decision = str(data.get("decision", "")).strip().capitalize()  # 'Approved' | 'Rejected'
    notes = str(data.get("decision_notes", "")).strip()

    if decision not in ["Approved", "Rejected"]:
        return jsonify({"error": "Decision must be 'Approved' or 'Rejected'."}), 400

    admin_name = request.user_session["name"]

    with connect() as con:
        con.execute("BEGIN IMMEDIATE")

        dr = con.execute("SELECT * FROM drop_requests WHERE id = ?", (drop_id,)).fetchone()
        if not dr:
            return jsonify({"error": "Drop request not found."}), 404
        if dr["status"] != "Pending Review":
            return jsonify({"error": f"This drop request has already been {dr['status'].lower()}."}), 409

        student = con.execute("SELECT * FROM students WHERE id = ?", (dr["student_id"],)).fetchone()
        course = con.execute("SELECT * FROM courses WHERE id = ?", (dr["course_id"],)).fetchone()

        if decision == "Approved":
            # Approve Drop: Mark drop request Approved, and mark registration as Dropped (freeing seat)
            con.execute(
                """UPDATE drop_requests
                   SET status = 'Approved', decision_notes = ?, decision_by = ?, decision_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (notes or "Course drop approved", admin_name, drop_id)
            )
            con.execute(
                """UPDATE registrations
                   SET status = 'Dropped', updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (dr["registration_id"],)
            )

            create_notification(
                con, student["email"], "student", "Course Drop Approved",
                f"Your request to drop {course['code']} has been APPROVED. Your enrollment is released.", "drop"
            )
            log_audit(con, "DROP_APPROVED", "DropRequest", drop_id, f"Approved course drop for {student['name']} in {course['code']}", admin_name)

        else:
            # Reject Drop: Registration remains Approved
            con.execute(
                """UPDATE drop_requests
                   SET status = 'Rejected', decision_notes = ?, decision_by = ?, decision_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (notes or "Drop request denied", admin_name, drop_id)
            )

            create_notification(
                con, student["email"], "student", "Course Drop Denied",
                f"Your request to drop {course['code']} was REJECTED. Explanation: {notes or 'No reason provided'}. Your enrollment remains confirmed.", "drop"
            )
            log_audit(con, "DROP_REJECTED", "DropRequest", drop_id, f"Rejected course drop for {student['name']} in {course['code']}: {notes}", admin_name)

        con.commit()
        return jsonify({
            "message": f"Drop request for {student['name']} in {course['code']} has been {decision.lower()}.",
            "status": decision
        })


# --- Notifications System ---
@app.get("/api/notifications")
def list_notifications():
    session = current_session()
    if not session:
        return jsonify({"notifications": [], "unread_count": 0})

    email = session["email"].lower()
    role = session["role"]

    with connect() as con:
        rows = con.execute(
            """SELECT * FROM notifications
               WHERE recipient_email = ? OR recipient_role = ?
               ORDER BY created_at DESC LIMIT 30""",
            (email, role)
        ).fetchall()
        unread = con.execute(
            """SELECT COUNT(*) FROM notifications
               WHERE (recipient_email = ? OR recipient_role = ?) AND is_read = 0""",
            (email, role)
        ).fetchone()[0]

        return jsonify({
            "notifications": [dict(r) for r in rows],
            "unread_count": unread
        })


@app.patch("/api/notifications/<int:notification_id>/read")
def mark_notification_read(notification_id):
    with connect() as con:
        con.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))
        return jsonify({"message": "Notification marked as read."})


@app.patch("/api/notifications/read-all")
def mark_all_notifications_read():
    session = current_session()
    if not session:
        return jsonify({"error": "Authentication required."}), 401
    email = session["email"].lower()
    role = session["role"]
    with connect() as con:
        con.execute("UPDATE notifications SET is_read = 1 WHERE recipient_email = ? OR recipient_role = ?", (email, role))
        return jsonify({"message": "All notifications marked as read."})


# --- System Audit Logs (Dedicated Admin Page) ---
@app.get("/api/audit-logs")
@require_role("admin")
def list_audit_logs():
    search = request.args.get("search", "").strip().lower()
    action = request.args.get("action", "").strip()

    with connect() as con:
        query = "SELECT * FROM audit_logs WHERE 1=1"
        params = []
        if search:
            query += " AND (lower(details) LIKE ? OR lower(performed_by) LIKE ? OR lower(entity) LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
        if action:
            query += " AND action = ?"
            params.append(action)

        query += " ORDER BY created_at DESC LIMIT 100"
        rows = con.execute(query, params).fetchall()
        return jsonify([dict(r) for r in rows])


# --- Student Directory (Admin) ---
@app.get("/api/students")
@require_role("admin")
def list_students():
    search = request.args.get("search", "").strip().lower()
    dept = request.args.get("department", "").strip().upper()

    with connect() as con:
        query = """
            SELECT s.*,
                   d.name AS department_name, ap.name AS degree_name,
                   COUNT(CASE WHEN r.status = 'Approved' THEN 1 END) AS approved_courses,
                   COALESCE(SUM(CASE WHEN r.status = 'Approved' THEN c.credits ELSE 0 END), 0) AS total_approved_credits,
                   COUNT(CASE WHEN r.status = 'Pending' THEN 1 END) AS pending_courses
            FROM students s
            LEFT JOIN departments d ON d.code = s.department_code
            LEFT JOIN academic_programs ap ON ap.code = s.degree_code
            LEFT JOIN registrations r ON r.student_id = s.id
            LEFT JOIN courses c ON c.id = r.course_id
            WHERE 1=1
        """
        params = []
        if search:
            query += " AND (lower(s.name) LIKE ? OR lower(s.email) LIKE ? OR lower(s.student_reg_no) LIKE ? OR lower(s.college_reg_no) LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"])
        if dept:
            query += " AND s.department_code = ?"
            params.append(dept)

        query += " GROUP BY s.id ORDER BY s.name ASC"
        rows = con.execute(query, params).fetchall()

        cleaned = []
        for r in rows:
            item = dict(r)
            item.pop("password_hash", None)
            cleaned.append(item)
        return jsonify(cleaned)


@app.get("/api/students/<int:student_id>")
@require_role("admin")
def get_student(student_id):
    with connect() as con:
        s = con.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
        if not s:
            return jsonify({"error": "Student not found."}), 404

        dept = con.execute("SELECT name FROM departments WHERE code = ?", (s["department_code"],)).fetchone()
        prog = con.execute("SELECT name FROM academic_programs WHERE code = ?", (s["degree_code"],)).fetchone()

        regs = con.execute(
            """SELECT r.*, c.code AS course_code, c.title AS course_title, c.credits, c.schedule
               FROM registrations r JOIN courses c ON c.id = r.course_id
               WHERE r.student_id = ?
               ORDER BY r.created_at DESC""",
            (student_id,)
        ).fetchall()

        drops = con.execute(
            """SELECT dr.*, c.code AS course_code, c.title AS course_title
               FROM drop_requests dr JOIN courses c ON c.id = dr.course_id
               WHERE dr.student_id = ?
               ORDER BY dr.created_at DESC""",
            (student_id,)
        ).fetchall()

        student = dict(s)
        student.pop("password_hash", None)
        student["department_name"] = dept["name"] if dept else s["department_code"]
        student["degree_name"] = prog["name"] if prog else s["degree_code"]
        student["registrations"] = [dict(r) for r in regs]
        student["drop_requests"] = [dict(dr) for dr in drops]
        return jsonify(student)


# --- System Summary ---
@app.get("/api/summary")
def get_summary():
    with connect() as con:
        total_courses = con.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
        total_students = con.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        approved_regs = con.execute("SELECT COUNT(*) FROM registrations WHERE status = 'Approved'").fetchone()[0]
        pending_regs = con.execute("SELECT COUNT(*) FROM registrations WHERE status = 'Pending'").fetchone()[0]
        pending_drops = con.execute("SELECT COUNT(*) FROM drop_requests WHERE status = 'Pending Review'").fetchone()[0]
        total_depts = con.execute("SELECT COUNT(*) FROM departments").fetchone()[0]
        total_programs = con.execute("SELECT COUNT(*) FROM academic_programs").fetchone()[0]

        total_cap = con.execute("SELECT COALESCE(SUM(capacity), 0) FROM courses").fetchone()[0]
        total_avail = max(0, total_cap - approved_regs)

        return jsonify({
            "courses": total_courses,
            "students": total_students,
            "approved_registrations": approved_regs,
            "pending_registrations": pending_regs,
            "pending_drops": pending_drops,
            "departments": total_depts,
            "programs": total_programs,
            "available_seats": total_avail,
            "total_capacity": total_cap
        })


init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    print(f"[INFO] Northstar University ERP Backend starting on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
