-- ============================================================================
-- ONLINE COURSE REGISTRATION SYSTEM - UNIVERSITY ERP DATABASE SCHEMA
-- Standard ANSI / PostgreSQL / SQLite Compatible Schema
-- ============================================================================

-- 1. Academic Programs (Degree Configurations)
CREATE TABLE IF NOT EXISTS academic_programs (
    id SERIAL PRIMARY KEY,
    code VARCHAR(32) UNIQUE NOT NULL,
    name VARCHAR(128) NOT NULL,
    duration_years INTEGER NOT NULL DEFAULT 4,
    total_semesters INTEGER NOT NULL DEFAULT 8
);

-- 2. Academic Departments
CREATE TABLE IF NOT EXISTS departments (
    id SERIAL PRIMARY KEY,
    code VARCHAR(32) UNIQUE NOT NULL,
    name VARCHAR(128) NOT NULL
);

-- 3. Curriculum Credit Requirements
CREATE TABLE IF NOT EXISTS curriculum_requirements (
    id SERIAL PRIMARY KEY,
    degree_code VARCHAR(32) NOT NULL,
    department_code VARCHAR(32) NOT NULL,
    academic_year INTEGER NOT NULL,
    semester INTEGER NOT NULL,
    required_credits INTEGER NOT NULL DEFAULT 20,
    min_credits INTEGER NOT NULL DEFAULT 16,
    max_credits INTEGER NOT NULL DEFAULT 24,
    UNIQUE(degree_code, department_code, academic_year, semester)
);

-- 4. Students Directory
CREATE TABLE IF NOT EXISTS students (
    id SERIAL PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    email VARCHAR(128) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    student_reg_no VARCHAR(64) UNIQUE NOT NULL,
    college_reg_no VARCHAR(64) UNIQUE NOT NULL,
    degree_code VARCHAR(32) NOT NULL,
    department_code VARCHAR(32) NOT NULL,
    academic_year INTEGER NOT NULL,
    semester INTEGER NOT NULL,
    section VARCHAR(8) NOT NULL DEFAULT 'A',
    status VARCHAR(32) NOT NULL DEFAULT 'Active',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 5. University Administrators
CREATE TABLE IF NOT EXISTS admins (
    id SERIAL PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    email VARCHAR(128) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    role VARCHAR(64) NOT NULL DEFAULT 'Dean of Academic Affairs',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 6. Courses Catalogue
CREATE TABLE IF NOT EXISTS courses (
    id SERIAL PRIMARY KEY,
    code VARCHAR(32) UNIQUE NOT NULL,
    title VARCHAR(256) NOT NULL,
    department_code VARCHAR(32) NOT NULL,
    instructor VARCHAR(128) NOT NULL,
    credits INTEGER NOT NULL CHECK(credits BETWEEN 1 AND 8),
    schedule VARCHAR(128) NOT NULL,
    location VARCHAR(128) NOT NULL DEFAULT 'Academic Block A, Hall 101',
    capacity INTEGER NOT NULL CHECK(capacity > 0),
    description TEXT NOT NULL DEFAULT '',
    prerequisites VARCHAR(256) NOT NULL DEFAULT 'None',
    term VARCHAR(64) NOT NULL DEFAULT 'Spring 2026',
    start_date VARCHAR(32) NOT NULL DEFAULT '2026-01-15',
    end_date VARCHAR(32) NOT NULL DEFAULT '2026-05-15',
    registration_deadline VARCHAR(32) NOT NULL DEFAULT '2026-12-31',
    lifecycle_status VARCHAR(64) NOT NULL DEFAULT 'Registration Open',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 7. Course Eligibility Rules
CREATE TABLE IF NOT EXISTS course_eligibility (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    degree_code VARCHAR(32) NOT NULL,
    department_code VARCHAR(32) NOT NULL,
    academic_year INTEGER NOT NULL,
    semester INTEGER NOT NULL,
    UNIQUE(course_id, degree_code, department_code, academic_year, semester)
);

-- 8. Department / Branch Seat Allocations
CREATE TABLE IF NOT EXISTS branch_allocations (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    department_code VARCHAR(32) NOT NULL,
    allocated_seats INTEGER NOT NULL CHECK(allocated_seats >= 0),
    UNIQUE(course_id, department_code)
);

-- 9. Student Registration & Approvals
CREATE TABLE IF NOT EXISTS registrations (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    status VARCHAR(32) NOT NULL DEFAULT 'Pending',
    decision_notes TEXT NOT NULL DEFAULT '',
    decision_by VARCHAR(128) NOT NULL DEFAULT '',
    decision_at VARCHAR(64),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, course_id)
);

-- 10. Course Drop Requests
CREATE TABLE IF NOT EXISTS drop_requests (
    id SERIAL PRIMARY KEY,
    registration_id INTEGER NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'Pending Review',
    decision_notes TEXT NOT NULL DEFAULT '',
    decision_by VARCHAR(128) NOT NULL DEFAULT '',
    decision_at VARCHAR(64),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 11. In-App Notifications
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    recipient_email VARCHAR(128) NOT NULL,
    recipient_role VARCHAR(32) NOT NULL DEFAULT 'student',
    title VARCHAR(256) NOT NULL,
    message TEXT NOT NULL,
    category VARCHAR(64) NOT NULL DEFAULT 'enrollment',
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 12. University Audit Logs
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    action VARCHAR(64) NOT NULL,
    entity VARCHAR(64) NOT NULL,
    entity_id INTEGER,
    details TEXT NOT NULL,
    performed_by VARCHAR(128) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_courses_code ON courses(code);
CREATE INDEX IF NOT EXISTS idx_registrations_student ON registrations(student_id);
CREATE INDEX IF NOT EXISTS idx_registrations_course ON registrations(course_id);
CREATE INDEX IF NOT EXISTS idx_eligibility_lookup ON course_eligibility(degree_code, department_code, academic_year, semester);
CREATE INDEX IF NOT EXISTS idx_allocations_lookup ON branch_allocations(course_id, department_code);
CREATE INDEX IF NOT EXISTS idx_notifications_recipient ON notifications(recipient_email, is_read);
CREATE INDEX IF NOT EXISTS idx_drop_requests_status ON drop_requests(status);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at);
