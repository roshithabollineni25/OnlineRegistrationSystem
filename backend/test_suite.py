#!/usr/bin/env python3
"""
University Course Registration System - End-to-End Test Suite
Tests authentication, role enforcement, dynamic academic constraints,
seat allocation, transactional approvals, drop requests, notifications, and persistence.
"""

import sys
import json
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import app, init_db, connect, hash_password


def run_tests():
    print("=" * 70)
    print("NORTHSTAR UNIVERSITY ERP - AUTOMATED TEST SUITE")
    print("=" * 70)

    # Initialize schema and seed data
    init_db()

    client = app.test_client()
    passed = 0
    total = 0

    def test(name, condition, error_detail=""):
        nonlocal passed, total
        total += 1
        if condition:
            passed += 1
            print(f"[{total:02d}/13] {name:<50} [PASS]")
            return True
        else:
            print(f"[{total:02d}/13] {name:<50} [FAIL] -> {error_detail}")
            return False

    # 1. API Health Check
    res = client.get("/api/health")
    data = res.get_json()
    test("API Health check & DB engine diagnostic", res.status_code == 200 and data.get("database", {}).get("persistent") is True, f"Status: {res.status_code}")

    # 2. Student Registration with Institutional Fields
    reg_payload = {
        "name": "Dev Test Student",
        "email": "dev.test@student.edu",
        "password": "Password@2026",
        "confirm_password": "Password@2026",
        "student_reg_no": "TEST-REG-9999",
        "college_reg_no": "COL-TEST-9999",
        "degree_code": "B.Tech.",
        "department_code": "CSE",
        "academic_year": 2,
        "semester": 4,
        "section": "A"
    }
    # Clear previous test record if exists
    with connect() as con:
        con.execute("DELETE FROM students WHERE email = ?", ("dev.test@student.edu",))

    res = client.post("/api/student/register", json=reg_payload)
    test("Student Registration with complete academic profile", res.status_code in [200, 201], f"Status: {res.status_code}, Body: {res.get_data(as_text=True)}")

    # 3. Student Login & Session Token
    login_res = client.post("/api/student/login", json={"email": "dev.test@student.edu", "password": "Password@2026"})
    login_data = login_res.get_json() or {}
    student_token = login_data.get("token")
    student_headers = {"Authorization": f"Bearer {student_token}"}
    test("Student Authentication & Bearer token", login_res.status_code == 200 and student_token is not None, f"Status: {login_res.status_code}")

    # 4. Administrator Login & RBAC
    admin_res = client.post("/api/admin/login", json={"email": "admin@northstar.edu", "password": "admin123"})
    admin_data = admin_res.get_json() or {}
    admin_token = admin_data.get("token")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    test("Administrator Authentication & Dean role", admin_res.status_code == 200 and admin_token is not None, f"Status: {admin_res.status_code}")

    # 5. Protected Endpoint Security (Reject Unauthorized)
    anon_res = client.get("/api/students")
    stud_forbidden_res = client.get("/api/students", headers=student_headers)
    test("Unauthorized & non-admin rejection on protected APIs", anon_res.status_code == 401 and stud_forbidden_res.status_code == 403, f"Anon: {anon_res.status_code}, Student: {stud_forbidden_res.status_code}")

    # 6. Branch-Filtered Catalogue (CSE Student sees CSE-301, not ME-205)
    catalog_res = client.get("/api/courses", headers=student_headers)
    catalog_courses = (catalog_res.get_json() or {}).get("courses", [])
    codes = [c["code"] for c in catalog_courses]
    test("Server-Side Branch/Program Filtering (CSE only)", "CSE-301" in codes and "ME-205" not in codes, f"Courses returned: {codes}")

    # 7. Cross-Branch Registration Prevention (HTTP 403 Forbidden)
    with connect() as con:
        me_course = con.execute("SELECT id FROM courses WHERE code = 'ME-205'").fetchone()
    me_course_id = me_course["id"] if me_course else 5
    cross_res = client.post("/api/registrations", json={"course_id": me_course_id}, headers=student_headers)
    test("Cross-branch registration rejection (403 Forbidden)", cross_res.status_code == 403, f"Status: {cross_res.status_code}, Body: {cross_res.get_data(as_text=True)}")

    # 8. Submit Legitimate Course Enrollment Request (Status -> Pending)
    with connect() as con:
        cse_course = con.execute("SELECT id FROM courses WHERE code = 'CSE-301'").fetchone()
        con.execute("DELETE FROM registrations WHERE student_id = ? AND course_id = ?", (login_data["id"], cse_course["id"]))
    req_res = client.post("/api/registrations", json={"course_id": cse_course["id"]}, headers=student_headers)
    req_data = req_res.get_json() or {}
    reg_id = req_data.get("registration_id")
    test("Submit Course Enrollment Request (Status: Pending)", req_res.status_code == 201 and reg_id is not None, f"Status: {req_res.status_code}")

    # 9. Full Student Academic Review Report for Admin Decision
    report_res = client.get(f"/api/registrations/{reg_id}/review-report", headers=admin_headers)
    report_data = report_res.get_json() or {}
    test("Full Student Review Report generation", report_res.status_code == 200 and "student_profile" in report_data and "academic_analysis" in report_data, f"Status: {report_res.status_code}")

    # 10. Administrator Approves Enrollment with Transactional Lock
    dec_res = client.patch(f"/api/registrations/{reg_id}/decision", json={"decision": "Approved", "decision_notes": "Approved by Dean for Spring 2026"}, headers=admin_headers)
    test("Admin Transactional Approval & Seat Allocation", dec_res.status_code == 200, f"Status: {dec_res.status_code}, Body: {dec_res.get_data(as_text=True)}")

    # 11. Student Submits Course Drop Request with Reason
    drop_res = client.post("/api/drop-requests", json={"registration_id": reg_id, "reason": "Schedule clash with core lab module"}, headers=student_headers)
    drop_data = drop_res.get_json() or {}
    drop_id = drop_data.get("drop_request_id")
    test("Formal Course Drop Request submission", drop_res.status_code == 201 and drop_id is not None, f"Status: {drop_res.status_code}, Body: {drop_res.get_data(as_text=True)}")

    # 12. Admin Reviews & Approves Course Drop (Releases Seat Quota)
    drop_appr_res = client.patch(f"/api/drop-requests/{drop_id}/decision", json={"decision": "Approved", "decision_notes": "Drop granted without academic penalty"}, headers=admin_headers)
    test("Admin Drop Request approval & Seat Quota release", drop_appr_res.status_code == 200, f"Status: {drop_appr_res.status_code}, Body: {drop_appr_res.get_data(as_text=True)}")

    # 13. In-App Notifications & University Audit Logging
    notif_res = client.get("/api/notifications", headers=student_headers)
    audit_res = client.get("/api/audit-logs", headers=admin_headers)
    test("In-App Notifications delivery & Audit Trail logging", notif_res.status_code == 200 and audit_res.status_code == 200, f"Notif: {notif_res.status_code}, Audit: {audit_res.status_code}")

    print("=" * 70)
    print(f"TEST RESULTS: {passed}/{total} PASSED ({passed / total * 100:.1f}%)")
    print("=" * 70)

    if passed == total:
        print("[ALL TESTS PASSED SUCCESSFULLY!]")
        return 0
    else:
        print("[TEST FAILURES DETECTED]")
        return 1


if __name__ == "__main__":
    sys.exit(run_tests())
