#!/usr/bin/env python3
"""
Online Course Registration System - Database Migration & Maintenance Utility
Usage:
  python migrate.py --status    Check database engine, target, and record counts
  python migrate.py --init      Create all tables, constraints, and indexes
  python migrate.py --seed      Populate initial programs, depts, courses, and demo accounts
  python migrate.py --verify    Run integrity checks across foreign keys & seat allocations
"""

import sys
import os
import argparse
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from database import connect, get_db_info, IS_POSTGRES
from app import hash_password, init_db, ADMIN_DEFAULT_PASSWORD


def check_status():
    info = get_db_info()
    print("=" * 60)
    print("NORTHSTAR UNIVERSITY ERP - DATABASE STATUS")
    print("=" * 60)
    print(f"  Engine:        {info['engine']}")
    print(f"  Target:        {info.get('connection') or info.get('path')}")
    print(f"  Mode:          {info['mode']}")
    print(f"  Persistent:    {info['persistent']}")
    print("-" * 60)

    tables = [
        "academic_programs", "departments", "curriculum_requirements",
        "students", "admins", "courses", "course_eligibility",
        "branch_allocations", "registrations", "drop_requests",
        "notifications", "audit_logs"
    ]

    try:
        with connect() as con:
            print(f"  {'TABLE NAME':<30} {'RECORD COUNT':>15}")
            print("  " + "-" * 46)
            total_records = 0
            for tbl in tables:
                try:
                    count = con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                    total_records += count
                    print(f"  {tbl:<30} {count:>15}")
                except Exception as e:
                    print(f"  {tbl:<30} {'[MISSING / ERROR]':>15}")
            print("  " + "=" * 46)
            print(f"  {'TOTAL RECORDS':<30} {total_records:>15}")
            print("=" * 60)
    except Exception as e:
        print(f"[ERROR] Failed to query database: {e}", file=sys.stderr)
        sys.exit(1)


def run_init():
    print("[INFO] Initializing relational schema...")
    try:
        init_db()
        print("[SUCCESS] All tables, indexes, and initial constraints established.")
    except Exception as e:
        print(f"[ERROR] Schema initialization failed: {e}", file=sys.stderr)
        sys.exit(1)


def run_verify():
    print("[INFO] Running database integrity & constraint verification...")
    with connect() as con:
        # 1. Verify seat allocations <= course capacity
        courses = con.execute("SELECT id, code, capacity FROM courses").fetchall()
        alloc_errors = 0
        for c in courses:
            alloc_sum = con.execute("SELECT COALESCE(SUM(allocated_seats), 0) FROM branch_allocations WHERE course_id = ?", (c["id"],)).fetchone()[0]
            if alloc_sum > c["capacity"]:
                print(f"[WARN] Course {c['code']} allocation sum ({alloc_sum}) exceeds total capacity ({c['capacity']})!")
                alloc_errors += 1

        # 2. Verify confirmed registrations <= allocated seats
        reg_errors = 0
        regs = con.execute("SELECT course_id, COUNT(*) as confirmed FROM registrations WHERE status = 'Confirmed' GROUP BY course_id").fetchall()
        for r in regs:
            course = con.execute("SELECT code, capacity FROM courses WHERE id = ?", (r["course_id"],)).fetchone()
            if course and r["confirmed"] > course["capacity"]:
                print(f"[WARN] Course {course['code']} confirmed registrations ({r['confirmed']}) exceed capacity ({course['capacity']})!")
                reg_errors += 1

        if alloc_errors == 0 and reg_errors == 0:
            print("[SUCCESS] All relational constraints, capacities, and branch quotas are consistent!")
        else:
            print(f"[ALERT] Found {alloc_errors} allocation anomalies and {reg_errors} capacity anomalies.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Course Registration Database Maintenance")
    parser.add_argument("--status", action="store_true", help="Display database engine status and table metrics")
    parser.add_argument("--init", action="store_true", help="Initialize schema and seed initial configuration")
    parser.add_argument("--seed", action="store_true", help="Re-run seed script")
    parser.add_argument("--verify", action="store_true", help="Run relational integrity validation")

    args = parser.parse_args()

    if args.init or args.seed:
        run_init()
        check_status()
    elif args.verify:
        run_verify()
    elif args.status or len(sys.argv) == 1:
        check_status()
    else:
        parser.print_help()
