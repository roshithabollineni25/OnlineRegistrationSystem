import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  GraduationCap,
  BookOpen,
  Calendar,
  Clock,
  MapPin,
  Users,
  Search,
  Filter,
  CheckCircle2,
  AlertCircle,
  Clock3,
  XCircle,
  Plus,
  Pencil,
  Trash2,
  LogOut,
  User,
  ShieldCheck,
  ChevronRight,
  Menu,
  X,
  Eye,
  Check,
  Building2,
  FileText,
  History,
  CheckCheck,
  ArrowRight,
  ArrowLeft,
  Bell,
  SlidersHorizontal,
  Layers,
  Award,
  AlertTriangle,
  RotateCcw
} from 'lucide-react';
import './styles.css';

// Production-ready API resolution: reads from VITE_API_BASE_URL; falls back to relative /api in production
const API_BASE = (
  import.meta.env.VITE_API_BASE_URL
    ? import.meta.env.VITE_API_BASE_URL.replace(/\/+$/, '')
    : (import.meta.env.DEV ? 'http://127.0.0.1:5001/api' : '/api')
);

const initials = (name = '') =>
  name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map(p => p[0])
    .join('')
    .toUpperCase();

function App() {
  const [token, setToken] = useState(localStorage.getItem('ocr_token') || '');
  const [role, setRole] = useState(token ? localStorage.getItem('ocr_role') || '' : '');
  const [activeTab, setActiveTab] = useState(role === 'admin' ? 'admin-overview' : 'student-overview');
  const [currentUser, setCurrentUser] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('ocr_user') || '{}');
    } catch {
      return {};
    }
  });

  // Academic Configuration state
  const [academicConfig, setAcademicConfig] = useState({ programs: [], departments: [], curricula: [] });

  // Auth gate state
  const [authRole, setAuthRole] = useState('student'); // 'student' | 'admin'
  const [authMode, setAuthMode] = useState('login'); // 'login' | 'register'
  const [authForm, setAuthForm] = useState({
    name: '',
    email: '',
    password: '',
    confirm_password: '',
    student_reg_no: '',
    college_reg_no: '',
    degree_code: 'B.Tech.',
    department_code: 'CSE',
    academic_year: 2,
    semester: 4,
    section: 'A'
  });

  // Data states
  const [courses, setCourses] = useState([]);
  const [registrations, setRegistrations] = useState([]);
  const [dropRequests, setDropRequests] = useState([]);
  const [students, setStudents] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [studentStanding, setStudentStanding] = useState(null);
  const [summary, setSummary] = useState({
    courses: 0,
    students: 0,
    approved_registrations: 0,
    pending_registrations: 0,
    pending_drops: 0,
    departments: 0,
    programs: 0,
    available_seats: 0
  });

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedDept, setSelectedDept] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [auditActionFilter, setAuditActionFilter] = useState('');
  const [showAllCourses, setShowAllCourses] = useState(false);

  // Modals & Detailed Views
  const [detailModalCourse, setDetailModalCourse] = useState(null);
  const [courseFormModal, setCourseFormModal] = useState(null);
  const [allocationModalCourse, setAllocationModalCourse] = useState(null);
  const [allocationForm, setAllocationForm] = useState([]);
  const [rosterModal, setRosterModal] = useState(null);
  const [studentDetailModal, setStudentDetailModal] = useState(null);
  const [confirmDialog, setConfirmDialog] = useState(null);
  const [dropRequestModal, setDropRequestModal] = useState(null); // registration object
  const [dropReason, setDropReason] = useState('');

  // Admin Review Report Modal
  const [reviewReportModal, setReviewReportModal] = useState(null);
  const [decisionNotes, setDecisionNotes] = useState('');

  // Drop Review Modal (Admin)
  const [dropReviewModal, setDropReviewModal] = useState(null);
  const [dropDecisionNotes, setDropDecisionNotes] = useState('');

  // UI state
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  const showToast = (message, type = 'success') => {
    setToast({ message, type });
    setTimeout(() => {
      setToast(null);
    }, 4500);
  };

  // Central API Client
  async function apiCall(endpoint, options = {}) {
    const currentToken = localStorage.getItem('ocr_token');
    const headers = {
      'Content-Type': 'application/json',
      ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
      ...(options.headers || {})
    };

    const response = await fetch(API_BASE + endpoint, { ...options, headers });
    let data = {};
    try {
      data = await response.json();
    } catch {}

    if (!response.ok) {
      if (response.status === 401 && !endpoint.includes('/login') && !endpoint.includes('/register')) {
        handleSignOut();
      }
      throw new Error(data.error || 'A network error occurred. Please try again.');
    }
    return data;
  }

  // Load initial academic configuration (degrees, departments)
  async function loadAcademicConfig() {
    try {
      const config = await apiCall('/academic/config');
      setAcademicConfig(config);
      if (config.programs?.length > 0 && !authForm.degree_code) {
        setAuthForm(prev => ({ ...prev, degree_code: config.programs[0].code }));
      }
      if (config.departments?.length > 0 && !authForm.department_code) {
        setAuthForm(prev => ({ ...prev, department_code: config.departments[0].code }));
      }
    } catch {}
  }

  // Load main application data
  async function loadData() {
    try {
      const [coursesRes, summaryRes] = await Promise.all([
        apiCall(role === 'student' && !showAllCourses ? '/courses' : '/courses?all=true'),
        apiCall('/summary')
      ]);
      setCourses(coursesRes.courses || []);
      setSummary(summaryRes);

      if (token) {
        // Notifications
        try {
          const notesRes = await apiCall('/notifications');
          setNotifications(notesRes.notifications || []);
          setUnreadCount(notesRes.unread_count || 0);
        } catch {}

        if (role === 'student') {
          const [myRegs, myDrops, profile] = await Promise.all([
            apiCall('/registrations'),
            apiCall('/drop-requests'),
            apiCall('/student/profile')
          ]);
          setRegistrations(Array.isArray(myRegs) ? myRegs : []);
          setDropRequests(Array.isArray(myDrops) ? myDrops : []);
          setStudentStanding(profile.academic_standing || null);
          setCurrentUser(prev => ({ ...prev, ...profile }));
        } else if (role === 'admin') {
          const [allRegs, allDrops, allStudents, logs] = await Promise.all([
            apiCall('/registrations'),
            apiCall('/drop-requests'),
            apiCall('/students'),
            apiCall('/audit-logs')
          ]);
          setRegistrations(Array.isArray(allRegs) ? allRegs : []);
          setDropRequests(Array.isArray(allDrops) ? allDrops : []);
          setStudents(Array.isArray(allStudents) ? allStudents : []);
          setAuditLogs(Array.isArray(logs) ? logs : []);
        }
      }
    } catch (err) {
      if (err.message.toLowerCase().includes('failed to fetch')) {
        showToast('Unable to reach the backend API. Please ensure the Python server is running.', 'error');
      } else if (token) {
        showToast(err.message, 'error');
      }
    }
  }

  useEffect(() => {
    loadAcademicConfig();
  }, []);

  useEffect(() => {
    loadData();
  }, [token, role, showAllCourses]);

  // Auth Submit Handlers
  const handleAuthSubmit = async e => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      if (authRole === 'admin') {
        const res = await apiCall('/admin/login', {
          method: 'POST',
          body: JSON.stringify({ email: authForm.email, password: authForm.password })
        });
        localStorage.setItem('ocr_token', res.token);
        localStorage.setItem('ocr_role', 'admin');
        const userData = { name: res.name || 'Dean of Academic Affairs', email: res.email, title: res.title };
        localStorage.setItem('ocr_user', JSON.stringify(userData));
        setToken(res.token);
        setRole('admin');
        setCurrentUser(userData);
        setActiveTab('admin-overview');
        showToast(`Signed in as ${userData.name}. Welcome to the Administration Portal.`);
      } else {
        if (authMode === 'login') {
          const res = await apiCall('/student/login', {
            method: 'POST',
            body: JSON.stringify({ email: authForm.email, password: authForm.password })
          });
          localStorage.setItem('ocr_token', res.token);
          localStorage.setItem('ocr_role', 'student');
          const userData = {
            name: res.name,
            email: res.email,
            student_reg_no: res.student_reg_no,
            college_reg_no: res.college_reg_no,
            degree_code: res.degree_code,
            degree_name: res.degree_name,
            department_code: res.department_code,
            department_name: res.department_name,
            academic_year: res.academic_year,
            semester: res.semester,
            section: res.section
          };
          localStorage.setItem('ocr_user', JSON.stringify(userData));
          setToken(res.token);
          setRole('student');
          setCurrentUser(userData);
          setActiveTab('student-overview');
          showToast(`Welcome back, ${userData.name}!`);
        } else {
          // Register Student
          await apiCall('/student/register', {
            method: 'POST',
            body: JSON.stringify(authForm)
          });
          showToast('Academic profile created successfully! Please sign in with your credentials.');
          setAuthMode('login');
        }
      }
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSignOut = async () => {
    try {
      await apiCall('/logout', { method: 'POST' });
    } catch {}
    localStorage.removeItem('ocr_token');
    localStorage.removeItem('ocr_role');
    localStorage.removeItem('ocr_user');
    setToken('');
    setRole('');
    setCurrentUser({});
    setActiveTab('student-overview');
    setMobileMenuOpen(false);
    setNotificationsOpen(false);
    showToast('You have successfully signed out.');
  };

  // Quick Demo Login Helper
  const handleDemoSignIn = (email, personaRole, password = 'student123') => {
    setAuthRole(personaRole);
    setAuthMode('login');
    setAuthForm(prev => ({
      ...prev,
      email,
      password: personaRole === 'admin' ? 'admin123' : password
    }));
  };

  // Student Actions
  const handleRequestEnrollment = async course => {
    try {
      const res = await apiCall('/registrations', {
        method: 'POST',
        body: JSON.stringify({ course_id: course.id })
      });
      showToast(res.message || `Enrollment requested for ${course.code}. Status: Pending review.`);
      if (detailModalCourse) setDetailModalCourse(null);
      await loadData();
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  const handleOpenDropModal = reg => {
    setDropRequestModal(reg);
    setDropReason('');
  };

  const handleSubmitDropRequest = async e => {
    e.preventDefault();
    if (!dropReason || dropReason.trim().length < 5) {
      showToast('Please state a valid academic reason (at least 5 characters).', 'error');
      return;
    }
    setIsSubmitting(true);
    try {
      const res = await apiCall('/drop-requests', {
        method: 'POST',
        body: JSON.stringify({ registration_id: dropRequestModal.id, reason: dropReason.trim() })
      });
      showToast(res.message);
      setDropRequestModal(null);
      setDropReason('');
      await loadData();
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Admin Actions
  const handleOpenReviewReport = async reg => {
    try {
      const report = await apiCall(`/registrations/${reg.id}/review-report`);
      setReviewReportModal(report);
      setDecisionNotes('');
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  const handleAdminRegistrationDecision = async (regId, decision) => {
    if (decision === 'Rejected' && (!decisionNotes || decisionNotes.trim().length < 3)) {
      showToast('A clear explanation is mandatory when rejecting a registration request.', 'error');
      return;
    }
    setIsSubmitting(true);
    try {
      const res = await apiCall(`/registrations/${regId}/decision`, {
        method: 'PATCH',
        body: JSON.stringify({ decision, decision_notes: decisionNotes.trim() })
      });
      showToast(res.message);
      setReviewReportModal(null);
      setDecisionNotes('');
      await loadData();
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAdminDropDecision = async (dropId, decision) => {
    setIsSubmitting(true);
    try {
      const res = await apiCall(`/drop-requests/${dropId}/decision`, {
        method: 'PATCH',
        body: JSON.stringify({ decision, decision_notes: dropDecisionNotes.trim() })
      });
      showToast(res.message);
      setDropReviewModal(null);
      setDropDecisionNotes('');
      await loadData();
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleOpenAllocationModal = async course => {
    try {
      const data = await apiCall(`/courses/${course.id}/allocations`);
      setAllocationModalCourse(data);
      setAllocationForm(
        data.branch_allocations.map(b => ({
          department_code: b.department_code,
          department_name: b.department_name,
          allocated_seats: b.allocated_seats,
          branch_confirmed: b.branch_confirmed
        }))
      );
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  const handleSaveAllocations = async e => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      const res = await apiCall(`/courses/${allocationModalCourse.course_id}/allocations`, {
        method: 'PUT',
        body: JSON.stringify({ allocations: allocationForm })
      });
      showToast(res.message);
      setAllocationModalCourse(null);
      await loadData();
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteCourse = course => {
    setConfirmDialog({
      title: 'Delete Course Offering',
      message: `Are you sure you want to permanently delete course ${course.code}: ${course.title}? All associated student registrations and branch allocations will be removed.`,
      confirmText: 'Confirm Deletion',
      isDanger: true,
      onConfirm: async () => {
        try {
          await apiCall(`/courses/${course.id}`, { method: 'DELETE' });
          showToast(`Course ${course.code} removed.`);
          setConfirmDialog(null);
          await loadData();
        } catch (err) {
          showToast(err.message, 'error');
        }
      }
    });
  };

  const handleMarkAllNotificationsRead = async () => {
    try {
      await apiCall('/notifications/read-all', { method: 'PATCH' });
      setNotifications(prev => prev.map(n => ({ ...n, is_read: 1 })));
      setUnreadCount(0);
    } catch {}
  };

  // Filtered Course Catalog
  const filteredCourses = useMemo(() => {
    return courses.filter(c => {
      const matchesSearch =
        !searchQuery ||
        `${c.code} ${c.title} ${c.department_name} ${c.instructor}`
          .toLowerCase()
          .includes(searchQuery.toLowerCase());
      const matchesDept = !selectedDept || c.department_code === selectedDept;
      return matchesSearch && matchesDept;
    });
  }, [courses, searchQuery, selectedDept]);

  // Navigation Items
  const navItems =
    role === 'admin'
      ? [
          { id: 'admin-overview', label: 'Administration Overview', icon: Building2 },
          { id: 'admin-courses', label: 'Course Management', icon: BookOpen },
          { id: 'admin-allocations', label: 'Course Allocations', icon: Layers },
          {
            id: 'admin-approvals',
            label: 'Enrollment Approvals',
            icon: CheckCheck,
            badge: summary.pending_registrations
          },
          {
            id: 'admin-drops',
            label: 'Drop Requests Queue',
            icon: RotateCcw,
            badge: summary.pending_drops
          },
          { id: 'admin-students', label: 'Student Directory', icon: Users },
          { id: 'admin-audit', label: 'System Audit Logs', icon: History }
        ]
      : [
          { id: 'student-overview', label: 'Academic Overview', icon: GraduationCap },
          { id: 'student-catalog', label: 'Course Catalogue', icon: BookOpen },
          {
            id: 'student-my-courses',
            label: 'My Registrations',
            icon: CheckCircle2,
            badge: registrations.filter(r => r.status === 'Approved' || r.status === 'Pending').length
          },
          { id: 'student-profile', label: 'Student Profile', icon: User }
        ];

  // Dynamic Semesters for Registration Form
  const availableSemesters = useMemo(() => {
    const year = parseInt(authForm.academic_year) || 1;
    return [(year - 1) * 2 + 1, year * 2];
  }, [authForm.academic_year]);

  // ==========================================================================
  // RENDER: Unauthenticated Portal Entry (Institutional Split Layout)
  // ==========================================================================
  if (!token) {
    return (
      <div className="auth-split-layout">
        {/* Left Hero Pane */}
        <div className="auth-hero-pane">
          <div className="auth-hero-brand">
            <div className="auth-hero-crest">
              <GraduationCap size={24} />
            </div>
            <div className="auth-hero-brand-copy">
              <strong>Northstar Academic ERP</strong>
              <span>University Course Registration</span>
            </div>
          </div>

          <div className="auth-hero-content">
            <div className="auth-hero-pill">
              <Award size={14} /> Official Academic Session 2026–2027
            </div>
            <h1 className="auth-hero-title">Academic Governance & Course Enrollment</h1>
            <p className="auth-hero-desc">
              Institutional course registration system featuring branch-enforced eligibility, transactional seat
              allocation, request-based administrator review, and student academic credit compliance.
            </p>

            <div className="auth-hero-features">
              <div className="auth-hero-feature-item">
                <Check size={16} />
                <span>Strict branch, degree, and semester eligibility enforcement</span>
              </div>
              <div className="auth-hero-feature-item">
                <Check size={16} />
                <span>Transparent branch-wise seat quotas with real-time capacity</span>
              </div>
              <div className="auth-hero-feature-item">
                <Check size={16} />
                <span>Formal administrative enrollment approvals & drop review workflows</span>
              </div>
              <div className="auth-hero-feature-item">
                <Check size={16} />
                <span>Automated curriculum credit analysis & complete student reports</span>
              </div>
            </div>
          </div>

          <div className="auth-hero-footer">
            Office of Academic Registrar & Institutional Curriculum Affairs • Northstar System v3.0
          </div>
        </div>

        {/* Right Form Pane */}
        <div className="auth-form-pane">
          <div className="auth-card">
            <div className="auth-card-header">
              <h2>{authRole === 'admin' ? 'Administrator Workspace' : 'Student Academic Portal'}</h2>
              <p className="page-subtitle">
                {authRole === 'admin'
                  ? 'Access executive curriculum controls, approval queues, and allocations.'
                  : 'Sign in to your student profile or register for academic courses.'}
              </p>
            </div>

            {/* Role Tab Selector */}
            <div className="role-tab-selector">
              <button
                type="button"
                className={`role-tab-btn ${authRole === 'student' ? 'active' : ''}`}
                onClick={() => {
                  setAuthRole('student');
                  setAuthMode('login');
                }}
              >
                Student Portal
              </button>
              <button
                type="button"
                className={`role-tab-btn ${authRole === 'admin' ? 'active' : ''}`}
                onClick={() => {
                  setAuthRole('admin');
                  setAuthMode('login');
                }}
              >
                Administrator
              </button>
            </div>

            {/* Sub-toggle: Sign In vs Complete Registration */}
            {authRole === 'student' && (
              <div className="auth-subtoggle">
                <button
                  type="button"
                  className={`auth-subtoggle-btn ${authMode === 'login' ? 'active' : ''}`}
                  onClick={() => setAuthMode('login')}
                >
                  Student Sign In
                </button>
                <button
                  type="button"
                  className={`auth-subtoggle-btn ${authMode === 'register' ? 'active' : ''}`}
                  onClick={() => setAuthMode('register')}
                >
                  Register New Student Profile
                </button>
              </div>
            )}

            {/* Auth Form */}
            <form onSubmit={handleAuthSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {authMode === 'register' && authRole === 'student' && (
                <>
                  <div className="academic-section-divider">1. Personal & Account Credentials</div>

                  <div className="form-group">
                    <label className="form-label">Full Student Name</label>
                    <input
                      type="text"
                      required
                      className="form-control"
                      placeholder="e.g. Aarav Kumar"
                      value={authForm.name}
                      onChange={e => setAuthForm({ ...authForm, name: e.target.value })}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Official University Email Address</label>
                    <input
                      type="email"
                      required
                      className="form-control"
                      placeholder="student@student.edu"
                      value={authForm.email}
                      onChange={e => setAuthForm({ ...authForm, email: e.target.value })}
                    />
                  </div>

                  <div className="form-row-2">
                    <div className="form-group">
                      <label className="form-label">Password (min. 6 characters)</label>
                      <input
                        type="password"
                        required
                        className="form-control"
                        placeholder="••••••••"
                        value={authForm.password}
                        onChange={e => setAuthForm({ ...authForm, password: e.target.value })}
                      />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Confirm Password</label>
                      <input
                        type="password"
                        required
                        className="form-control"
                        placeholder="••••••••"
                        value={authForm.confirm_password}
                        onChange={e => setAuthForm({ ...authForm, confirm_password: e.target.value })}
                      />
                    </div>
                  </div>

                  <div className="academic-section-divider">2. Institutional & Branch Information</div>

                  <div className="form-row-2">
                    <div className="form-group">
                      <label className="form-label">Student Registration Number</label>
                      <input
                        type="text"
                        required
                        className="form-control"
                        placeholder="e.g. STU2026CSE05"
                        value={authForm.student_reg_no}
                        onChange={e => setAuthForm({ ...authForm, student_reg_no: e.target.value })}
                      />
                    </div>
                    <div className="form-group">
                      <label className="form-label">College Registration Number</label>
                      <input
                        type="text"
                        required
                        className="form-control"
                        placeholder="e.g. COL-2026-9045"
                        value={authForm.college_reg_no}
                        onChange={e => setAuthForm({ ...authForm, college_reg_no: e.target.value })}
                      />
                    </div>
                  </div>

                  <div className="form-row-2">
                    <div className="form-group">
                      <label className="form-label">Degree / Program</label>
                      <select
                        className="form-control"
                        value={authForm.degree_code}
                        onChange={e => setAuthForm({ ...authForm, degree_code: e.target.value })}
                      >
                        {academicConfig.programs.map(p => (
                          <option key={p.code} value={p.code}>
                            {p.code} — {p.name}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="form-group">
                      <label className="form-label">Department / Branch</label>
                      <select
                        className="form-control"
                        value={authForm.department_code}
                        onChange={e => setAuthForm({ ...authForm, department_code: e.target.value })}
                      >
                        {academicConfig.departments.map(d => (
                          <option key={d.code} value={d.code}>
                            {d.name} ({d.code})
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="form-row-3">
                    <div className="form-group">
                      <label className="form-label">Academic Year</label>
                      <select
                        className="form-control"
                        value={authForm.academic_year}
                        onChange={e => {
                          const y = parseInt(e.target.value);
                          setAuthForm({ ...authForm, academic_year: y, semester: (y - 1) * 2 + 1 });
                        }}
                      >
                        <option value={1}>Year 1</option>
                        <option value={2}>Year 2</option>
                        <option value={3}>Year 3</option>
                        <option value={4}>Year 4</option>
                      </select>
                    </div>

                    <div className="form-group">
                      <label className="form-label">Semester</label>
                      <select
                        className="form-control"
                        value={authForm.semester}
                        onChange={e => setAuthForm({ ...authForm, semester: parseInt(e.target.value) })}
                      >
                        {availableSemesters.map(s => (
                          <option key={s} value={s}>
                            Semester {s}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="form-group">
                      <label className="form-label">Section</label>
                      <select
                        className="form-control"
                        value={authForm.section}
                        onChange={e => setAuthForm({ ...authForm, section: e.target.value })}
                      >
                        <option value="A">Section A</option>
                        <option value="B">Section B</option>
                        <option value="C">Section C</option>
                      </select>
                    </div>
                  </div>
                </>
              )}

              {authMode === 'login' && (
                <>
                  <div className="form-group">
                    <label className="form-label">
                      {authRole === 'admin' ? 'Administrator Email' : 'Official Student Email'}
                    </label>
                    <input
                      type="email"
                      required
                      className="form-control"
                      placeholder={authRole === 'admin' ? 'admin@northstar.edu' : 'student@student.edu'}
                      value={authForm.email}
                      onChange={e => setAuthForm({ ...authForm, email: e.target.value })}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Password</label>
                    <input
                      type="password"
                      required
                      className="form-control"
                      placeholder="Enter password"
                      value={authForm.password}
                      onChange={e => setAuthForm({ ...authForm, password: e.target.value })}
                    />
                  </div>
                </>
              )}

              <button
                type="submit"
                disabled={isSubmitting}
                className="btn btn-primary btn-lg"
                style={{ marginTop: '10px' }}
              >
                {isSubmitting
                  ? 'Processing…'
                  : authMode === 'login'
                  ? `Sign In to ${authRole === 'admin' ? 'Administrator Portal' : 'Student Portal'}`
                  : 'Submit Registration Profile'}
              </button>
            </form>

            {/* Quick Demo Credentials */}
            <div className="demo-credentials-box">
              <strong>Institutional Evaluation Accounts</strong>
              <p style={{ marginTop: '2px', fontSize: '0.6875rem', color: 'var(--text-tertiary)' }}>
                Click any pre-configured student or administrator account to test branch rules:
              </p>
              <div className="demo-chips">
                <button
                  type="button"
                  className="demo-chip-btn"
                  onClick={() => handleDemoSignIn('aarav.kumar@student.edu', 'student')}
                >
                  Aarav Kumar (B.Tech. CSE)
                </button>
                <button
                  type="button"
                  className="demo-chip-btn"
                  onClick={() => handleDemoSignIn('rhea.s@student.edu', 'student')}
                >
                  Rhea Sengupta (B.Tech. IT)
                </button>
                <button
                  type="button"
                  className="demo-chip-btn"
                  onClick={() => handleDemoSignIn('vikram.p@student.edu', 'student')}
                >
                  Vikram Patel (B.Tech. MECH)
                </button>
                <button
                  type="button"
                  className="demo-chip-btn"
                  onClick={() => handleDemoSignIn('tanya.v@student.edu', 'student')}
                >
                  Tanya Verma (LL.B. LAW)
                </button>
                <button
                  type="button"
                  className="demo-chip-btn"
                  style={{ backgroundColor: 'var(--color-primary)', color: '#ffffff' }}
                  onClick={() => handleDemoSignIn('admin@northstar.edu', 'admin', 'admin123')}
                >
                  Dean of Academic Affairs (Admin)
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Floating Toast */}
        {toast && (
          <div className="toast-container">
            <div className={`toast toast-${toast.type}`}>
              {toast.type === 'success' ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
              <span>{toast.message}</span>
              <button className="toast-close" onClick={() => setToast(null)}>
                <X size={14} />
              </button>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ==========================================================================
  // RENDER: Authenticated Portal Shell
  // ==========================================================================
  return (
    <div className="app-shell">
      {/* Sidebar Navigation */}
      <aside className={`sidebar ${mobileMenuOpen ? 'mobile-open' : ''}`}>
        <div className="sidebar-header">
          <div className="brand-link">
            <div className="brand-logo-icon">
              <GraduationCap size={22} />
            </div>
            <div className="brand-meta">
              <strong>Northstar ERP</strong>
              <span>{role === 'admin' ? 'University Administration' : 'Student Portal'}</span>
            </div>
          </div>
          <button className="btn-icon-only mobile-menu-toggle" onClick={() => setMobileMenuOpen(false)}>
            <X size={18} />
          </button>
        </div>

        <div className="sidebar-nav-section">
          <div className="nav-section-title">{role === 'admin' ? 'Administration' : 'Academic Workspace'}</div>
          <nav style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {navItems.map(item => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  className={`nav-link-btn ${isActive ? 'active' : ''}`}
                  onClick={() => {
                    setActiveTab(item.id);
                    setMobileMenuOpen(false);
                  }}
                >
                  <Icon size={18} />
                  <span>{item.label}</span>
                  {item.badge !== undefined && item.badge > 0 && (
                    <span className="nav-link-badge">{item.badge}</span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>

        <div className="sidebar-footer">
          <div className="user-profile-tile">
            <div className={`avatar ${role === 'admin' ? 'avatar-admin' : ''}`}>
              {role === 'admin' ? 'DEAN' : initials(currentUser.name) || 'ST'}
            </div>
            <div className="user-info">
              <span className="user-name">{currentUser.name || 'User'}</span>
              <span className="user-role">
                {role === 'admin'
                  ? 'Dean of Academic Affairs'
                  : `${currentUser.student_reg_no || ''} • ${currentUser.department_code || ''}`}
              </span>
            </div>
            <button className="signout-btn" onClick={handleSignOut} title="Sign out" aria-label="Sign out">
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="main-wrapper">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="btn-icon-only mobile-menu-toggle"
              onClick={() => setMobileMenuOpen(true)}
              aria-label="Open navigation"
            >
              <Menu size={20} />
            </button>
            <div className="breadcrumbs">
              <span>Northstar ERP</span>
              <span className="breadcrumbs-separator">/</span>
              <span>{role === 'admin' ? 'Academic Administration' : currentUser.department_name || 'Student'}</span>
              <span className="breadcrumbs-separator">/</span>
              <span className="breadcrumbs-current">
                {navItems.find(item => item.id === activeTab)?.label || 'Overview'}
              </span>
            </div>
          </div>

          <div className="topbar-right">
            {/* Notification Bell */}
            <div style={{ position: 'relative' }}>
              <button
                className="notification-bell-btn"
                onClick={() => setNotificationsOpen(!notificationsOpen)}
                aria-label="View notifications"
              >
                <Bell size={18} />
                {unreadCount > 0 && <span className="notification-unread-dot" />}
              </button>

              {notificationsOpen && (
                <div className="notifications-panel">
                  <div className="notifications-header">
                    <strong>Notifications ({unreadCount} unread)</strong>
                    {unreadCount > 0 && (
                      <button className="btn btn-ghost btn-sm" onClick={handleMarkAllNotificationsRead}>
                        Mark all read
                      </button>
                    )}
                  </div>
                  <div className="notifications-list">
                    {notifications.length > 0 ? (
                      notifications.map(n => (
                        <div key={n.id} className={`notification-item ${n.is_read ? '' : 'unread'}`}>
                          <div className="notification-title">{n.title}</div>
                          <div className="notification-msg">{n.message}</div>
                          <div className="notification-time">
                            {new Date(n.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })},{' '}
                            {new Date(n.created_at).toLocaleDateString()}
                          </div>
                        </div>
                      ))
                    ) : (
                      <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-tertiary)' }}>
                        No notifications to display.
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            <div className="term-indicator">
              <span className="term-dot" />
              <span>Spring 2026 Academic Session</span>
            </div>
          </div>
        </header>

        <main className="content-container">
          {/* ============================================================== */}
          {/* STUDENT SCREEN 1: Academic Overview */}
          {/* ============================================================== */}
          {role === 'student' && activeTab === 'student-overview' && (
            <div>
              <div className="page-title-row">
                <div>
                  <span className="page-eyebrow">
                    <GraduationCap size={15} /> Student Academic Overview
                  </span>
                  <h1>Welcome, {currentUser.name}</h1>
                  <p className="page-subtitle">
                    {currentUser.degree_name} • Department of {currentUser.department_name} • Year{' '}
                    {currentUser.academic_year}, Semester {currentUser.semester} (Section {currentUser.section})
                  </p>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button className="btn btn-secondary" onClick={() => setActiveTab('student-my-courses')}>
                    View My Registrations
                  </button>
                  <button className="btn btn-primary" onClick={() => setActiveTab('student-catalog')}>
                    <BookOpen size={16} /> Open Course Catalogue
                  </button>
                </div>
              </div>

              {/* Academic Credit Requirements & Standing Box */}
              {studentStanding && (
                <div className="credit-standing-box">
                  <div className="credit-standing-info">
                    <h3>Curriculum Credit Analysis</h3>
                    <p>
                      Academic rule: Minimum {studentStanding.min_credits} credits, Maximum {studentStanding.max_credits}{' '}
                      credits required for {currentUser.degree_code} {currentUser.department_code} Semester{' '}
                      {currentUser.semester}.
                    </p>
                  </div>
                  <div className="credit-pill-group">
                    <div className="credit-pill">
                      <span className="credit-pill-val">{studentStanding.required_credits}</span>
                      <span className="credit-pill-lbl">Target Credits</span>
                    </div>
                    <div className="credit-pill">
                      <span className="credit-pill-val" style={{ color: '#065f46' }}>
                        {studentStanding.approved_credits}
                      </span>
                      <span className="credit-pill-lbl">Approved Credits</span>
                    </div>
                    <div className="credit-pill">
                      <span className="credit-pill-val" style={{ color: '#b45309' }}>
                        {studentStanding.pending_credits}
                      </span>
                      <span className="credit-pill-lbl">Pending Credits</span>
                    </div>
                    <div className="credit-pill">
                      <span className="credit-pill-val" style={{ color: '#164e3f' }}>
                        {studentStanding.remaining_credits}
                      </span>
                      <span className="credit-pill-lbl">Remaining Needed</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Quick Metrics */}
              <div className="metrics-grid">
                <div className="metric-card">
                  <div className="metric-header">
                    <span className="metric-label">Confirmed Enrolments</span>
                    <div className="metric-icon-wrap">
                      <CheckCircle2 size={16} />
                    </div>
                  </div>
                  <div className="metric-value">
                    {registrations.filter(r => r.status === 'Approved').length}
                  </div>
                  <div className="metric-footer">Confirmed active courses</div>
                </div>

                <div className="metric-card">
                  <div className="metric-header">
                    <span className="metric-label">Pending Requests</span>
                    <div className="metric-icon-wrap" style={{ color: '#d97706', backgroundColor: '#fffbeb' }}>
                      <Clock3 size={16} />
                    </div>
                  </div>
                  <div className="metric-value">
                    {registrations.filter(r => r.status === 'Pending').length}
                  </div>
                  <div className="metric-footer">Awaiting Dean authorization</div>
                </div>

                <div className="metric-card">
                  <div className="metric-header">
                    <span className="metric-label">Eligible Courses</span>
                    <div className="metric-icon-wrap">
                      <BookOpen size={16} />
                    </div>
                  </div>
                  <div className="metric-value">{courses.length}</div>
                  <div className="metric-footer">Restricted to your branch & sem</div>
                </div>

                <div className="metric-card">
                  <div className="metric-header">
                    <span className="metric-label">Total Catalog Seats</span>
                    <div className="metric-icon-wrap">
                      <Users size={16} />
                    </div>
                  </div>
                  <div className="metric-value">{summary.available_seats}</div>
                  <div className="metric-footer">Remaining across all offerings</div>
                </div>
              </div>

              {/* Two Column Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: '24px' }}>
                <div className="card">
                  <div className="card-header">
                    <h3>Confirmed Semester Courses</h3>
                    <button className="btn btn-ghost btn-sm" onClick={() => setActiveTab('student-my-courses')}>
                      Full Schedule <ChevronRight size={14} />
                    </button>
                  </div>
                  <div className="card-body" style={{ padding: 0 }}>
                    {registrations.filter(r => r.status === 'Approved').length > 0 ? (
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Code</th>
                            <th>Course Title</th>
                            <th>Schedule & Room</th>
                            <th>Credits</th>
                          </tr>
                        </thead>
                        <tbody>
                          {registrations
                            .filter(r => r.status === 'Approved')
                            .map(reg => (
                              <tr key={reg.id}>
                                <td className="table-code-cell">{reg.course_code}</td>
                                <td className="table-title-cell">{reg.course_title}</td>
                                <td>
                                  <div>{reg.schedule}</div>
                                  <div style={{ fontSize: '0.6875rem', color: 'var(--text-tertiary)' }}>
                                    {reg.location}
                                  </div>
                                </td>
                                <td>{reg.credits} Cr</td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    ) : (
                      <div className="empty-state" style={{ margin: '20px', border: 'none' }}>
                        <div className="empty-state-icon">
                          <BookOpen size={24} />
                        </div>
                        <div className="empty-state-title">No Confirmed Enrolments</div>
                        <div className="empty-state-desc">
                          You do not have any approved course enrollments yet. Browse your branch catalogue to submit an
                          enrollment request.
                        </div>
                        <button className="btn btn-primary btn-sm" onClick={() => setActiveTab('student-catalog')}>
                          Open Course Catalogue
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                {/* Institutional Student Profile */}
                <div className="card">
                  <div className="card-header">
                    <h3>Institutional Record</h3>
                  </div>
                  <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <div>
                      <span className="form-label">Student Reg Number</span>
                      <div style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--color-primary)' }}>
                        {currentUser.student_reg_no}
                      </div>
                    </div>
                    <div>
                      <span className="form-label">College Reg Number</span>
                      <div style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                        {currentUser.college_reg_no}
                      </div>
                    </div>
                    <div>
                      <span className="form-label">Enrolled Degree & Branch</span>
                      <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                        {currentUser.degree_code} — {currentUser.department_name}
                      </div>
                    </div>
                    <div>
                      <span className="form-label">Academic Standing</span>
                      <div>
                        Year {currentUser.academic_year}, Semester {currentUser.semester} (Section{' '}
                        {currentUser.section})
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ============================================================== */}
          {/* STUDENT SCREEN 2: Course Catalogue (Strict Branch Restricted) */}
          {/* ============================================================== */}
          {role === 'student' && activeTab === 'student-catalog' && (
            <div>
              <div className="page-title-row">
                <div>
                  <span className="page-eyebrow">
                    <BookOpen size={15} /> Academic Catalogue
                  </span>
                  <h1>Branch-Restricted Course Catalogue</h1>
                  <p className="page-subtitle">
                    Displaying courses eligible for {currentUser.degree_code} {currentUser.department_code} Year{' '}
                    {currentUser.academic_year}, Semester {currentUser.semester}.
                  </p>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <label style={{ fontSize: '0.8125rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <input
                      type="checkbox"
                      checked={showAllCourses}
                      onChange={e => setShowAllCourses(e.target.checked)}
                    />
                    <span>Show All University Offerings</span>
                  </label>
                </div>
              </div>

              {/* Search Bar */}
              <div className="filter-bar">
                <div className="search-input-wrapper">
                  <Search size={16} className="search-icon-left" />
                  <input
                    type="text"
                    className="search-input"
                    placeholder="Search by course code, title, instructor..."
                    value={searchQuery}
                    onChange={e => setSearchQuery(e.target.value)}
                  />
                </div>
                <div className="filter-count">
                  {filteredCourses.length} {filteredCourses.length === 1 ? 'course' : 'courses'} available
                </div>
              </div>

              {/* Course Card Grid */}
              {filteredCourses.length > 0 ? (
                <div className="course-grid">
                  {filteredCourses.map(course => {
                    const status = course.registration_status;
                    const isEligible = course.is_eligible;
                    const canRequest = course.can_request_enrollment;
                    const branchQuota = course.student_branch_allocated ?? course.capacity;
                    const branchLeft = course.student_branch_remaining ?? course.available_seats;

                    return (
                      <div className="course-card" key={course.id}>
                        <div className="course-card-header">
                          <span className="course-code-badge">{course.code}</span>
                          <span className="dept-pill">{course.department_name}</span>
                        </div>

                        <div className="course-card-body">
                          <h3 className="course-card-title">{course.title}</h3>
                          <p className="course-card-desc">{course.description || 'No description provided.'}</p>

                          <div className="course-meta-list">
                            <div className="course-meta-item">
                              <User size={14} />
                              <span>{course.instructor}</span>
                            </div>
                            <div className="course-meta-item">
                              <Clock size={14} />
                              <span>{course.schedule}</span>
                            </div>
                            <div className="course-meta-item">
                              <Calendar size={14} />
                              <span>Registration Deadline: {course.registration_deadline}</span>
                            </div>
                          </div>

                          {/* Branch-Wise Availability Strip */}
                          <div className="branch-seats-strip">
                            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                              <span>Branch Quota ({currentUser.department_code}):</span>
                              <strong>{branchLeft} seats left</strong>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '2px', fontSize: '0.6875rem', color: 'var(--text-tertiary)' }}>
                              <span>Total Course Capacity:</span>
                              <span>
                                {course.confirmed_seats} / {course.capacity} filled
                              </span>
                            </div>
                            <div className="capacity-progress-track">
                              <div
                                className="capacity-progress-bar"
                                style={{
                                  width: `${Math.min(100, Math.round((course.confirmed_seats / course.capacity) * 100))}%`
                                }}
                              />
                            </div>
                          </div>

                          {/* Eligibility Status */}
                          <div style={{ marginTop: '8px' }}>
                            {isEligible ? (
                              <span className="badge badge-approved">
                                <Check size={12} /> Eligible for your branch
                              </span>
                            ) : (
                              <span className="badge badge-rejected">
                                <XCircle size={12} /> Restricted to other departments
                              </span>
                            )}
                          </div>
                        </div>

                        <div className="course-card-footer">
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            onClick={() => setDetailModalCourse(course)}
                          >
                            <Eye size={14} /> View Details
                          </button>

                          {status === 'Approved' ? (
                            <span className="badge badge-approved">
                              <Check size={12} /> Enrolled
                            </span>
                          ) : status === 'Pending' ? (
                            <span className="badge badge-pending">
                              <Clock3 size={12} /> Pending Review
                            </span>
                          ) : status === 'Drop Requested' ? (
                            <span className="badge badge-warning">
                              <Clock3 size={12} /> Drop Pending
                            </span>
                          ) : (
                            <button
                              type="button"
                              className="btn btn-primary btn-sm"
                              disabled={!canRequest}
                              onClick={() => handleRequestEnrollment(course)}
                              title={course.request_ineligible_reason || 'Submit enrollment request for Dean review'}
                            >
                              Request Enrollment
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="empty-state">
                  <div className="empty-state-icon">
                    <Search size={24} />
                  </div>
                  <div className="empty-state-title">No Eligible Courses Found</div>
                  <div className="empty-state-desc">
                    There are no published courses matching your search query for your branch and semester.
                  </div>
                  <button className="btn btn-secondary btn-sm" onClick={() => setSearchQuery('')}>
                    Clear Search
                  </button>
                </div>
              )}
            </div>
          )}

          {/* ============================================================== */}
          {/* STUDENT SCREEN 3: My Courses & Formal Drop Workflow */}
          {/* ============================================================== */}
          {role === 'student' && activeTab === 'student-my-courses' && (
            <div>
              <div className="page-title-row">
                <div>
                  <span className="page-eyebrow">
                    <FileText size={15} /> Student Records
                  </span>
                  <h1>My Course Registrations</h1>
                  <p className="page-subtitle">
                    Monitor requested and confirmed registrations. Approved courses require formal Dean review to drop.
                  </p>
                </div>
                <button className="btn btn-primary" onClick={() => setActiveTab('student-catalog')}>
                  <Plus size={16} /> Request Another Course
                </button>
              </div>

              {registrations.length > 0 ? (
                <div className="table-responsive">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Course Code</th>
                        <th>Course Title</th>
                        <th>Schedule & Location</th>
                        <th>Credits</th>
                        <th>Status</th>
                        <th>Dean Decision / Notes</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {registrations.map(reg => {
                        const isPendingDrop = reg.drop_request_status === 'Pending Review';

                        let statusBadge = (
                          <span className="badge badge-approved">
                            <Check size={12} /> Confirmed
                          </span>
                        );
                        if (reg.status === 'Pending') {
                          statusBadge = (
                            <span className="badge badge-pending">
                              <Clock3 size={12} /> Pending Review
                            </span>
                          );
                        } else if (reg.status === 'Rejected') {
                          statusBadge = (
                            <span className="badge badge-rejected">
                              <XCircle size={12} /> Request Rejected
                            </span>
                          );
                        } else if (reg.status === 'Dropped') {
                          statusBadge = <span className="badge badge-dropped">Dropped</span>;
                        }

                        return (
                          <tr key={reg.id}>
                            <td className="table-code-cell">{reg.course_code}</td>
                            <td>
                              <div className="table-title-cell">{reg.course_title}</div>
                              <div style={{ fontSize: '0.6875rem', color: 'var(--text-tertiary)' }}>
                                {reg.instructor} • {reg.course_dept}
                              </div>
                            </td>
                            <td>
                              <div>{reg.schedule}</div>
                              <div style={{ fontSize: '0.6875rem', color: 'var(--text-tertiary)' }}>
                                {reg.location}
                              </div>
                            </td>
                            <td>{reg.credits} Cr</td>
                            <td>{statusBadge}</td>
                            <td>
                              {isPendingDrop ? (
                                <span style={{ color: '#b45309', fontSize: '0.75rem', fontWeight: 600 }}>
                                  Drop request pending: "{reg.drop_reason}"
                                </span>
                              ) : reg.decision_notes ? (
                                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                                  {reg.decision_notes} ({reg.decision_by})
                                </span>
                              ) : (
                                <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>—</span>
                              )}
                            </td>
                            <td>
                              {reg.status === 'Approved' && !isPendingDrop ? (
                                <button
                                  type="button"
                                  className="btn btn-secondary btn-sm"
                                  style={{ color: 'var(--status-rejected-text)' }}
                                  onClick={() => handleOpenDropModal(reg)}
                                >
                                  Request Drop
                                </button>
                              ) : isPendingDrop ? (
                                <span className="badge badge-warning">Drop Under Review</span>
                              ) : (
                                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Inactive</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="empty-state">
                  <div className="empty-state-icon">
                    <BookOpen size={24} />
                  </div>
                  <div className="empty-state-title">No Registration Records</div>
                  <div className="empty-state-desc">
                    You have not submitted any enrollment requests yet. Browse your branch catalogue to select eligible
                    courses.
                  </div>
                  <button className="btn btn-primary" onClick={() => setActiveTab('student-catalog')}>
                    Browse Eligible Courses
                  </button>
                </div>
              )}
            </div>
          )}

          {/* ============================================================== */}
          {/* STUDENT SCREEN 4: Profile */}
          {/* ============================================================== */}
          {role === 'student' && activeTab === 'student-profile' && (
            <div>
              <div className="page-title-row">
                <div>
                  <span className="page-eyebrow">
                    <User size={15} /> Student Academic Identity
                  </span>
                  <h1>Student Academic Profile</h1>
                  <p className="page-subtitle">
                    Institutional enrollment record, degree program, and verified semester progress.
                  </p>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '24px' }}>
                <div className="card">
                  <div className="card-body" style={{ textAlign: 'center', padding: '36px 20px' }}>
                    <div
                      className="avatar"
                      style={{ width: '68px', height: '68px', fontSize: '1.375rem', margin: '0 auto 16px' }}
                    >
                      {initials(currentUser.name)}
                    </div>
                    <h3 style={{ fontSize: '1.125rem' }}>{currentUser.name}</h3>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.8125rem', marginTop: '4px' }}>
                      {currentUser.email}
                    </p>
                    <div style={{ marginTop: '16px' }}>
                      <span className="badge badge-approved">{currentUser.student_reg_no}</span>
                    </div>
                  </div>
                </div>

                <div className="card">
                  <div className="card-header">
                    <h3>Verified Academic Credentials</h3>
                  </div>
                  <div className="card-body" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                    <div>
                      <span className="form-label">Student Reg Number</span>
                      <div style={{ fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--color-primary)' }}>
                        {currentUser.student_reg_no}
                      </div>
                    </div>
                    <div>
                      <span className="form-label">College Reg Number</span>
                      <div style={{ fontFamily: 'var(--font-mono)' }}>{currentUser.college_reg_no}</div>
                    </div>
                    <div>
                      <span className="form-label">Degree / Program</span>
                      <div style={{ fontWeight: 600 }}>{currentUser.degree_name}</div>
                    </div>
                    <div>
                      <span className="form-label">Department / Branch</span>
                      <div style={{ fontWeight: 600 }}>{currentUser.department_name}</div>
                    </div>
                    <div>
                      <span className="form-label">Academic Year & Semester</span>
                      <div>
                        Year {currentUser.academic_year}, Semester {currentUser.semester} (Section {currentUser.section})
                      </div>
                    </div>
                    <div>
                      <span className="form-label">Institutional Status</span>
                      <div>
                        <span className="badge badge-approved">Active In Good Standing</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ============================================================== */}
          {/* ADMIN SCREEN 1: Administration Overview */}
          {/* ============================================================== */}
          {role === 'admin' && activeTab === 'admin-overview' && (
            <div>
              <div className="page-title-row">
                <div>
                  <span className="page-eyebrow">
                    <Building2 size={15} /> Academic Governance
                  </span>
                  <h1>Institutional Administration Overview</h1>
                  <p className="page-subtitle">
                    Real-time enrollment statistics, branch seat allocations, approval queues, and system audits.
                  </p>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button className="btn btn-secondary" onClick={() => setActiveTab('admin-approvals')}>
                    <CheckCheck size={16} /> Approvals Queue ({summary.pending_registrations})
                  </button>
                  <button className="btn btn-secondary" onClick={() => setActiveTab('admin-drops')}>
                    <RotateCcw size={16} /> Drop Requests ({summary.pending_drops})
                  </button>
                </div>
              </div>

              {/* Metrics Strip */}
              <div className="metrics-grid">
                <div className="metric-card">
                  <div className="metric-header">
                    <span className="metric-label">Published Courses</span>
                    <div className="metric-icon-wrap">
                      <BookOpen size={16} />
                    </div>
                  </div>
                  <div className="metric-value">{summary.courses}</div>
                  <div className="metric-footer">Across {summary.departments} academic departments</div>
                </div>

                <div className="metric-card">
                  <div className="metric-header">
                    <span className="metric-label">Confirmed Enrolments</span>
                    <div className="metric-icon-wrap">
                      <CheckCircle2 size={16} />
                    </div>
                  </div>
                  <div className="metric-value">{summary.approved_registrations}</div>
                  <div className="metric-footer">Allocated and approved seats</div>
                </div>

                <div className="metric-card">
                  <div className="metric-header">
                    <span className="metric-label">Pending Enrollments</span>
                    <div className="metric-icon-wrap" style={{ color: '#b45309', backgroundColor: '#fffbeb' }}>
                      <Clock3 size={16} />
                    </div>
                  </div>
                  <div className="metric-value" style={{ color: summary.pending_registrations > 0 ? '#b45309' : 'inherit' }}>
                    {summary.pending_registrations}
                  </div>
                  <div className="metric-footer">Requests awaiting Dean signoff</div>
                </div>

                <div className="metric-card">
                  <div className="metric-header">
                    <span className="metric-label">Pending Course Drops</span>
                    <div className="metric-icon-wrap" style={{ color: '#ef4444', backgroundColor: '#fef2f2' }}>
                      <RotateCcw size={16} />
                    </div>
                  </div>
                  <div className="metric-value" style={{ color: summary.pending_drops > 0 ? '#b91c1c' : 'inherit' }}>
                    {summary.pending_drops}
                  </div>
                  <div className="metric-footer">Student drops requiring review</div>
                </div>
              </div>

              {/* Two Column Layout: Pending Approvals & Live Audit Stream */}
              <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '24px' }}>
                <div className="card">
                  <div className="card-header">
                    <h3>Pending Enrollment Approvals Queue</h3>
                    <button className="btn btn-ghost btn-sm" onClick={() => setActiveTab('admin-approvals')}>
                      Open Queue <ChevronRight size={14} />
                    </button>
                  </div>
                  <div className="card-body" style={{ padding: 0 }}>
                    {registrations.filter(r => r.status === 'Pending').length > 0 ? (
                      <table className="data-table">
                        <thead>
                          <tr>
                            <th>Student</th>
                            <th>Target Course</th>
                            <th>Action</th>
                          </tr>
                        </thead>
                        <tbody>
                          {registrations
                            .filter(r => r.status === 'Pending')
                            .slice(0, 5)
                            .map(reg => (
                              <tr key={reg.id}>
                                <td>
                                  <strong>{reg.student_name}</strong>
                                  <div style={{ fontSize: '0.6875rem', color: 'var(--text-tertiary)' }}>
                                    {reg.student_reg_no} • {reg.student_dept}
                                  </div>
                                </td>
                                <td>
                                  <span className="table-code-cell">{reg.course_code}</span> — {reg.course_title}
                                </td>
                                <td>
                                  <button
                                    type="button"
                                    className="btn btn-primary btn-sm"
                                    onClick={() => handleOpenReviewReport(reg)}
                                  >
                                    Review Report
                                  </button>
                                </td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    ) : (
                      <div className="empty-state" style={{ margin: '20px', border: 'none' }}>
                        <div className="empty-state-icon">
                          <CheckCheck size={24} />
                        </div>
                        <div className="empty-state-title">Enrollment Queue Clear</div>
                        <div className="empty-state-desc">All student enrollment requests have been decided.</div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Audit Stream */}
                <div className="card">
                  <div className="card-header">
                    <h3>Recent System Audit Events</h3>
                    <button className="btn btn-ghost btn-sm" onClick={() => setActiveTab('admin-audit')}>
                      Full Audit Log <ChevronRight size={14} />
                    </button>
                  </div>
                  <div className="card-body" style={{ padding: 0 }}>
                    <div style={{ maxHeight: '340px', overflowY: 'auto' }}>
                      {auditLogs.slice(0, 6).map(log => (
                        <div
                          key={log.id}
                          style={{
                            padding: '10px 16px',
                            borderBottom: '1px solid var(--border-subtle)',
                            fontSize: '0.75rem'
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <span style={{ fontWeight: 700, color: 'var(--color-primary)' }}>{log.action}</span>
                            <span style={{ color: 'var(--text-tertiary)' }}>
                              {new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                          </div>
                          <div style={{ color: 'var(--text-secondary)', marginTop: '2px' }}>{log.details}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ============================================================== */}
          {/* ADMIN SCREEN 2: Course Management */}
          {/* ============================================================== */}
          {role === 'admin' && activeTab === 'admin-courses' && (
            <div>
              <div className="page-title-row">
                <div>
                  <span className="page-eyebrow">
                    <BookOpen size={15} /> Curriculum Management
                  </span>
                  <h1>Course Management & Scheduling</h1>
                  <p className="page-subtitle">
                    Configure curriculum offerings, prerequisites, academic dates, capacities, and enrolled rosters.
                  </p>
                </div>
              </div>

              {/* Filter Bar */}
              <div className="filter-bar">
                <div className="search-input-wrapper">
                  <Search size={16} className="search-icon-left" />
                  <input
                    type="text"
                    className="search-input"
                    placeholder="Search by course code, title, instructor..."
                    value={searchQuery}
                    onChange={e => setSearchQuery(e.target.value)}
                  />
                </div>
                <div className="filter-count">{filteredCourses.length} courses configured</div>
              </div>

              <div className="table-responsive">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Code</th>
                      <th>Course Title</th>
                      <th>Department</th>
                      <th>Instructor</th>
                      <th>Schedule & Location</th>
                      <th>Capacity & Enrolment</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredCourses.map(course => (
                      <tr key={course.id}>
                        <td className="table-code-cell">{course.code}</td>
                        <td>
                          <div className="table-title-cell">{course.title}</div>
                          <div style={{ fontSize: '0.6875rem', color: 'var(--text-tertiary)' }}>
                            {course.credits} Credits • Prerequisites: {course.prerequisites}
                          </div>
                        </td>
                        <td>{course.department_name}</td>
                        <td>{course.instructor}</td>
                        <td>
                          <div>{course.schedule}</div>
                          <div style={{ fontSize: '0.6875rem', color: 'var(--text-tertiary)' }}>{course.location}</div>
                        </td>
                        <td>
                          <div style={{ minWidth: '90px' }}>
                            <div style={{ fontSize: '0.75rem', display: 'flex', justifyContent: 'space-between' }}>
                              <span>
                                {course.confirmed_seats} / {course.capacity}
                              </span>
                              <span style={{ fontWeight: 600 }}>{course.available_seats} left</span>
                            </div>
                            <div className="capacity-progress-track">
                              <div
                                className="capacity-progress-bar"
                                style={{
                                  width: `${Math.min(100, Math.round((course.confirmed_seats / course.capacity) * 100))}%`
                                }}
                              />
                            </div>
                          </div>
                        </td>
                        <td>
                          <span className="badge badge-approved">{course.lifecycle_status}</span>
                        </td>
                        <td>
                          <div className="table-actions">
                            <button
                              type="button"
                              className="btn-icon-only"
                              title="Inspect Enrolled Students Roster"
                              onClick={async () => {
                                const fullCourse = await apiCall(`/courses/${course.id}`);
                                setRosterModal(fullCourse);
                              }}
                            >
                              <Users size={16} />
                            </button>
                            <button
                              type="button"
                              className="btn-icon-only"
                              title="Edit Branch Seat Allocations"
                              onClick={() => handleOpenAllocationModal(course)}
                            >
                              <Layers size={16} />
                            </button>
                            <button
                              type="button"
                              className="btn-icon-only"
                              title="Delete Course"
                              style={{ color: 'var(--status-rejected-text)' }}
                              onClick={() => handleDeleteCourse(course)}
                            >
                              <Trash2 size={16} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ============================================================== */}
          {/* ADMIN SCREEN 3: Dedicated Course Allocation Overview */}
          {/* ============================================================== */}
          {role === 'admin' && activeTab === 'admin-allocations' && (
            <div>
              <div className="page-title-row">
                <div>
                  <span className="page-eyebrow">
                    <Layers size={15} /> Seat Allocation Architecture
                  </span>
                  <h1>Branch-Wise Course Allocations</h1>
                  <p className="page-subtitle">
                    Dynamic breakdown of course capacities, department quotas, confirmed enrollments, and pending
                    requests.
                  </p>
                </div>
              </div>

              <div className="table-responsive">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Course Code</th>
                      <th>Course Title</th>
                      <th>Total Capacity</th>
                      <th>Branch Seat Allocations & Availability</th>
                      <th>Confirmed Seats</th>
                      <th>Remaining</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {courses.map(course => (
                      <tr key={course.id}>
                        <td className="table-code-cell">{course.code}</td>
                        <td className="table-title-cell">{course.title}</td>
                        <td>
                          <strong>{course.capacity} seats</strong>
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                            {course.branch_allocations?.map(b => (
                              <div
                                key={b.department_code}
                                style={{
                                  padding: '4px 8px',
                                  backgroundColor: 'var(--bg-subtle)',
                                  border: '1px solid var(--border-subtle)',
                                  borderRadius: 'var(--radius-sm)',
                                  fontSize: '0.6875rem'
                                }}
                              >
                                <strong>{b.department_code}:</strong> {b.branch_confirmed}/{b.allocated_seats} (
                                {b.branch_remaining} left)
                              </div>
                            ))}
                          </div>
                        </td>
                        <td>{course.confirmed_seats}</td>
                        <td>
                          <strong style={{ color: course.available_seats > 0 ? '#065f46' : '#991b1b' }}>
                            {course.available_seats} seats
                          </strong>
                        </td>
                        <td>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => handleOpenAllocationModal(course)}
                          >
                            <SlidersHorizontal size={14} /> Edit Allocation
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ============================================================== */}
          {/* ADMIN SCREEN 4: Enrollment Approvals Queue */}
          {/* ============================================================== */}
          {role === 'admin' && activeTab === 'admin-approvals' && (
            <div>
              <div className="page-title-row">
                <div>
                  <span className="page-eyebrow">
                    <CheckCheck size={15} /> Academic Review Queue
                  </span>
                  <h1>Enrollment Approvals Queue</h1>
                  <p className="page-subtitle">
                    Inspect complete academic profiles and curriculum compliance reports before authorizing
                    enrollment.
                  </p>
                </div>
              </div>

              {registrations.filter(r => r.status === 'Pending').length > 0 ? (
                <div className="table-responsive">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Student Reg No</th>
                        <th>Student Name</th>
                        <th>Department</th>
                        <th>Target Course</th>
                        <th>Requested Date</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {registrations
                        .filter(r => r.status === 'Pending')
                        .map(reg => (
                          <tr key={reg.id}>
                            <td className="table-code-cell">{reg.student_reg_no}</td>
                            <td className="table-title-cell">{reg.student_name}</td>
                            <td>{reg.student_dept}</td>
                            <td>
                              <span className="table-code-cell">{reg.course_code}</span> — {reg.course_title} (
                              {reg.credits} Cr)
                            </td>
                            <td>{new Date(reg.created_at).toLocaleDateString()}</td>
                            <td>
                              <button
                                type="button"
                                className="btn btn-primary btn-sm"
                                onClick={() => handleOpenReviewReport(reg)}
                              >
                                Review Academic Report
                              </button>
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="empty-state">
                  <div className="empty-state-icon">
                    <CheckCheck size={24} />
                  </div>
                  <div className="empty-state-title">Approval Queue Clear</div>
                  <div className="empty-state-desc">There are no pending course enrollment requests at this time.</div>
                </div>
              )}
            </div>
          )}

          {/* ============================================================== */}
          {/* ADMIN SCREEN 5: Dedicated Drop Requests Queue */}
          {/* ============================================================== */}
          {role === 'admin' && activeTab === 'admin-drops' && (
            <div>
              <div className="page-title-row">
                <div>
                  <span className="page-eyebrow">
                    <RotateCcw size={15} /> Course Drop Governance
                  </span>
                  <h1>Course Drop Requests Queue</h1>
                  <p className="page-subtitle">
                    Students cannot drop courses directly. Review academic consequences and authorize or deny course
                    drops.
                  </p>
                </div>
              </div>

              {dropRequests.filter(dr => dr.status === 'Pending Review').length > 0 ? (
                <div className="table-responsive">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Student Reg No</th>
                        <th>Student Name</th>
                        <th>Course</th>
                        <th>Credits</th>
                        <th>Student Drop Reason</th>
                        <th>Date Submitted</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dropRequests
                        .filter(dr => dr.status === 'Pending Review')
                        .map(dr => (
                          <tr key={dr.id}>
                            <td className="table-code-cell">{dr.student_reg_no}</td>
                            <td className="table-title-cell">{dr.student_name}</td>
                            <td>
                              <span className="table-code-cell">{dr.course_code}</span> — {dr.course_title}
                            </td>
                            <td>{dr.credits} Cr</td>
                            <td style={{ maxWidth: '240px', color: 'var(--text-secondary)' }}>"{dr.reason}"</td>
                            <td>{new Date(dr.created_at).toLocaleDateString()}</td>
                            <td>
                              <button
                                type="button"
                                className="btn btn-primary btn-sm"
                                onClick={() => {
                                  setDropReviewModal(dr);
                                  setDropDecisionNotes('');
                                }}
                              >
                                Review Drop Request
                              </button>
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="empty-state">
                  <div className="empty-state-icon">
                    <CheckCheck size={24} />
                  </div>
                  <div className="empty-state-title">No Pending Course Drop Requests</div>
                  <div className="empty-state-desc">There are no student drop requests awaiting administrative decision.</div>
                </div>
              )}
            </div>
          )}

          {/* ============================================================== */}
          {/* ADMIN SCREEN 6: Student Directory */}
          {/* ============================================================== */}
          {role === 'admin' && activeTab === 'admin-students' && (
            <div>
              <div className="page-title-row">
                <div>
                  <span className="page-eyebrow">
                    <Users size={15} /> Student Roster
                  </span>
                  <h1>Student Academic Directory</h1>
                  <p className="page-subtitle">
                    Comprehensive roster of registered students, department enrollments, and approved semester loads.
                  </p>
                </div>
              </div>

              <div className="table-responsive">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Student Reg No</th>
                      <th>College Reg No</th>
                      <th>Name</th>
                      <th>Program & Branch</th>
                      <th>Year / Sem</th>
                      <th>Confirmed Courses</th>
                      <th>Approved Credits</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {students.map(st => (
                      <tr key={st.id}>
                        <td className="table-code-cell">{st.student_reg_no}</td>
                        <td style={{ fontFamily: 'var(--font-mono)' }}>{st.college_reg_no}</td>
                        <td className="table-title-cell">{st.name}</td>
                        <td>
                          {st.degree_code} — {st.department_name}
                        </td>
                        <td>
                          Y{st.academic_year} / S{st.semester} (Sec {st.section})
                        </td>
                        <td>{st.approved_courses} courses</td>
                        <td>
                          <strong>{st.total_approved_credits} Credits</strong>
                        </td>
                        <td>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={async () => {
                              const detail = await apiCall(`/students/${st.id}`);
                              setStudentDetailModal(detail);
                            }}
                          >
                            <Eye size={14} /> Full Record
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ============================================================== */}
          {/* ADMIN SCREEN 7: Dedicated Audit Logs Page */}
          {/* ============================================================== */}
          {role === 'admin' && activeTab === 'admin-audit' && (
            <div>
              <div className="page-title-row">
                <div>
                  <span className="page-eyebrow">
                    <History size={15} /> Compliance Tracking
                  </span>
                  <h1>Dedicated System Audit Logs</h1>
                  <p className="page-subtitle">
                    Immutable chronological record of administrator approvals, course modifications, seat allocation
                    adjustments, and drop decisions.
                  </p>
                </div>
              </div>

              <div className="table-responsive">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Timestamp</th>
                      <th>Action Type</th>
                      <th>Target Entity</th>
                      <th>Event Details</th>
                      <th>Acting Administrator</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditLogs.map(log => (
                      <tr key={log.id}>
                        <td style={{ whiteSpace: 'nowrap', fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>
                          {new Date(log.created_at).toLocaleString()}
                        </td>
                        <td>
                          <span className="badge badge-info">{log.action}</span>
                        </td>
                        <td>{log.entity}</td>
                        <td>{log.details}</td>
                        <td>
                          <strong>{log.performed_by}</strong>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* ==================================================================== */}
      {/* MODAL: Full Student Academic Review Report (Admin Approval) */}
      {/* ==================================================================== */}
      {reviewReportModal && (
        <div
          className="modal-backdrop"
          onClick={e => {
            if (e.target === e.currentTarget) setReviewReportModal(null);
          }}
        >
          <div className="modal-container modal-container-lg">
            <div className="modal-header">
              <div>
                <button className="back-btn" onClick={() => setReviewReportModal(null)}>
                  <ArrowLeft size={14} /> Back to Approvals Queue
                </button>
                <h3>Academic Review Report: Enrollment Request</h3>
                <p className="page-subtitle">
                  Comprehensive academic analysis for {reviewReportModal.student_profile.name} (
                  {reviewReportModal.student_profile.student_reg_no})
                </p>
              </div>
              <button className="btn-icon-only" onClick={() => setReviewReportModal(null)}>
                <X size={18} />
              </button>
            </div>

            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {/* Student Identity Card */}
              <div style={{ padding: '16px', backgroundColor: 'var(--bg-subtle)', borderRadius: 'var(--radius-md)' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', fontSize: '0.8125rem' }}>
                  <div>
                    <span className="form-label">Student Reg No</span>
                    <strong style={{ display: 'block', fontFamily: 'var(--font-mono)' }}>
                      {reviewReportModal.student_profile.student_reg_no}
                    </strong>
                  </div>
                  <div>
                    <span className="form-label">College Reg No</span>
                    <strong style={{ display: 'block', fontFamily: 'var(--font-mono)' }}>
                      {reviewReportModal.student_profile.college_reg_no}
                    </strong>
                  </div>
                  <div>
                    <span className="form-label">Degree & Branch</span>
                    <strong>
                      {reviewReportModal.student_profile.degree_code} —{' '}
                      {reviewReportModal.student_profile.department_code}
                    </strong>
                  </div>
                  <div>
                    <span className="form-label">Year / Semester / Section</span>
                    <strong>
                      Year {reviewReportModal.student_profile.academic_year}, Sem{' '}
                      {reviewReportModal.student_profile.semester} (Sec {reviewReportModal.student_profile.section})
                    </strong>
                  </div>
                </div>
              </div>

              {/* Academic Credit Analysis */}
              <div className="card">
                <div className="card-header">
                  <h3>Curriculum Credit Verification</h3>
                </div>
                <div className="card-body">
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', textAlign: 'center' }}>
                    <div style={{ padding: '10px', backgroundColor: 'var(--bg-subtle)', borderRadius: 'var(--radius-sm)' }}>
                      <span className="form-label">Required Credits</span>
                      <strong style={{ fontSize: '1.25rem', display: 'block', color: 'var(--color-primary)' }}>
                        {reviewReportModal.academic_analysis.required_credits}
                      </strong>
                    </div>
                    <div style={{ padding: '10px', backgroundColor: 'var(--status-approved-bg)', borderRadius: 'var(--radius-sm)' }}>
                      <span className="form-label">Approved Credits</span>
                      <strong style={{ fontSize: '1.25rem', display: 'block', color: 'var(--status-approved-text)' }}>
                        {reviewReportModal.academic_analysis.approved_credits}
                      </strong>
                    </div>
                    <div style={{ padding: '10px', backgroundColor: 'var(--status-pending-bg)', borderRadius: 'var(--radius-sm)' }}>
                      <span className="form-label">Pending Credits</span>
                      <strong style={{ fontSize: '1.25rem', display: 'block', color: 'var(--status-pending-text)' }}>
                        {reviewReportModal.academic_analysis.pending_credits}
                      </strong>
                    </div>
                    <div style={{ padding: '10px', backgroundColor: 'var(--bg-subtle)', borderRadius: 'var(--radius-sm)' }}>
                      <span className="form-label">Projected Total</span>
                      <strong style={{ fontSize: '1.25rem', display: 'block', color: 'var(--color-primary)' }}>
                        {reviewReportModal.academic_analysis.projected_credits}
                      </strong>
                    </div>
                  </div>

                  {reviewReportModal.academic_analysis.exceeds_max_limit && (
                    <div
                      style={{
                        marginTop: '12px',
                        padding: '10px',
                        backgroundColor: '#fef2f2',
                        color: '#991b1b',
                        borderRadius: 'var(--radius-sm)',
                        fontSize: '0.75rem',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px'
                      }}
                    >
                      <AlertTriangle size={16} /> Warning: Approving this course will exceed the maximum semester credit
                      limit ({reviewReportModal.academic_analysis.max_credits} credits). Explicit exception override
                      required.
                    </div>
                  )}
                </div>
              </div>

              {/* Target Course & Capacity */}
              <div className="card">
                <div className="card-header">
                  <h3>Target Course Seat Availability</h3>
                </div>
                <div className="card-body">
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '14px' }}>
                    <div>
                      <span className="form-label">Course Details</span>
                      <div style={{ fontWeight: 700 }}>
                        {reviewReportModal.course_details.code} — {reviewReportModal.course_details.title}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
                        {reviewReportModal.course_details.credits} Credits • {reviewReportModal.course_details.schedule}
                      </div>
                    </div>
                    <div>
                      <span className="form-label">Total Course Capacity</span>
                      <div style={{ fontWeight: 700 }}>
                        {reviewReportModal.course_details.confirmed_seats} /{' '}
                        {reviewReportModal.course_details.capacity} filled
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#065f46' }}>
                        {reviewReportModal.course_details.available_seats} total seats available
                      </div>
                    </div>
                    <div>
                      <span className="form-label">
                        Student Branch ({reviewReportModal.student_profile.department_code}) Quota
                      </span>
                      <div style={{ fontWeight: 700 }}>
                        {reviewReportModal.course_details.student_branch_confirmed} /{' '}
                        {reviewReportModal.course_details.student_branch_allocated} filled
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#065f46', fontWeight: 600 }}>
                        {reviewReportModal.course_details.student_branch_remaining} branch seats remaining
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Decision Section */}
              <div className="form-group">
                <label className="form-label">
                  Administrative Decision Notes / Explanation (Mandatory if Rejecting or Overriding)
                </label>
                <input
                  type="text"
                  className="form-control"
                  placeholder="e.g. Prerequisites verified and credit requirements met / Ineligible semester"
                  value={decisionNotes}
                  onChange={e => setDecisionNotes(e.target.value)}
                />
              </div>
            </div>

            <div className="modal-footer">
              <button type="button" className="btn btn-secondary" onClick={() => setReviewReportModal(null)}>
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-danger"
                disabled={isSubmitting}
                onClick={() =>
                  handleAdminRegistrationDecision(reviewReportModal.registration.id, 'Rejected')
                }
              >
                Reject Request
              </button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={isSubmitting}
                onClick={() =>
                  handleAdminRegistrationDecision(reviewReportModal.registration.id, 'Approved')
                }
              >
                Authorize & Confirm Enrollment
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* MODAL: Course Drop Request Form (Student) */}
      {/* ==================================================================== */}
      {dropRequestModal && (
        <div
          className="modal-backdrop"
          onClick={e => {
            if (e.target === e.currentTarget) setDropRequestModal(null);
          }}
        >
          <div className="modal-container">
            <div className="modal-header">
              <div>
                <button className="back-btn" onClick={() => setDropRequestModal(null)}>
                  <ArrowLeft size={14} /> Back to My Courses
                </button>
                <h3>Formal Course Drop Request</h3>
                <p className="page-subtitle">
                  {dropRequestModal.course_code}: {dropRequestModal.course_title}
                </p>
              </div>
              <button className="btn-icon-only" onClick={() => setDropRequestModal(null)}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleSubmitDropRequest}>
              <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div
                  style={{
                    padding: '12px',
                    backgroundColor: 'var(--color-primary-subtle)',
                    borderRadius: 'var(--radius-md)',
                    fontSize: '0.8125rem',
                    color: 'var(--color-primary)'
                  }}
                >
                  <strong>Academic Policy Notice:</strong> Approved course enrollments cannot be dropped directly. Your
                  drop request will be submitted to the Dean of Academic Affairs. Your enrollment and seat allocation
                  remain active until officially approved.
                </div>

                <div className="form-group">
                  <label className="form-label">Academic Reason for Drop Request (Mandatory)</label>
                  <textarea
                    rows={4}
                    required
                    className="form-control"
                    placeholder="Describe why you need to drop this course (e.g. Schedule clash with required core laboratory, change of elective track)..."
                    value={dropReason}
                    onChange={e => setDropReason(e.target.value)}
                  />
                  <span className="form-hint">
                    This reason will be recorded in the institutional audit log and reviewed by the Dean.
                  </span>
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setDropRequestModal(null)}>
                  Cancel
                </button>
                <button type="submit" disabled={isSubmitting} className="btn btn-danger">
                  {isSubmitting ? 'Submitting…' : 'Submit Drop Request to Dean'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* MODAL: Review Course Drop Request (Admin) */}
      {/* ==================================================================== */}
      {dropReviewModal && (
        <div
          className="modal-backdrop"
          onClick={e => {
            if (e.target === e.currentTarget) setDropReviewModal(null);
          }}
        >
          <div className="modal-container">
            <div className="modal-header">
              <div>
                <button className="back-btn" onClick={() => setDropReviewModal(null)}>
                  <ArrowLeft size={14} /> Back to Drop Queue
                </button>
                <h3>Review Student Drop Request</h3>
                <p className="page-subtitle">
                  {dropReviewModal.student_name} ({dropReviewModal.student_reg_no})
                </p>
              </div>
              <button className="btn-icon-only" onClick={() => setDropReviewModal(null)}>
                <X size={18} />
              </button>
            </div>

            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <span className="form-label">Course to Drop</span>
                <div style={{ fontWeight: 700, fontSize: '0.9375rem' }}>
                  {dropReviewModal.course_code} — {dropReviewModal.course_title} ({dropReviewModal.credits} Credits)
                </div>
              </div>

              <div>
                <span className="form-label">Student's Stated Reason</span>
                <div
                  style={{
                    padding: '12px',
                    backgroundColor: 'var(--bg-subtle)',
                    borderRadius: 'var(--radius-sm)',
                    fontStyle: 'italic',
                    marginTop: '4px'
                  }}
                >
                  "{dropReviewModal.reason}"
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Dean Decision Explanation</label>
                <input
                  type="text"
                  className="form-control"
                  placeholder="e.g. Authorized without penalty / Denied: Minimum credit threshold violated"
                  value={dropDecisionNotes}
                  onChange={e => setDropDecisionNotes(e.target.value)}
                />
              </div>
            </div>

            <div className="modal-footer">
              <button type="button" className="btn btn-secondary" onClick={() => setDropReviewModal(null)}>
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-danger"
                disabled={isSubmitting}
                onClick={() => handleAdminDropDecision(dropReviewModal.id, 'Rejected')}
              >
                Deny Drop (Maintain Enrollment)
              </button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={isSubmitting}
                onClick={() => handleAdminDropDecision(dropReviewModal.id, 'Approved')}
              >
                Approve Drop & Release Seat
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* MODAL: Course Details Modal (Student & Admin) */}
      {/* ==================================================================== */}
      {detailModalCourse && (
        <div
          className="modal-backdrop"
          onClick={e => {
            if (e.target === e.currentTarget) setDetailModalCourse(null);
          }}
        >
          <div className="modal-container">
            <div className="modal-header">
              <div>
                <button className="back-btn" onClick={() => setDetailModalCourse(null)}>
                  <ArrowLeft size={14} /> Back to Catalogue
                </button>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="course-code-badge">{detailModalCourse.code}</span>
                  <span className="dept-pill">{detailModalCourse.department_name}</span>
                </div>
                <h3 style={{ marginTop: '6px' }}>{detailModalCourse.title}</h3>
              </div>
              <button className="btn-icon-only" onClick={() => setDetailModalCourse(null)}>
                <X size={18} />
              </button>
            </div>

            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <span className="form-label">Description</span>
                <p style={{ marginTop: '4px', color: 'var(--text-secondary)' }}>
                  {detailModalCourse.description || 'No detailed syllabus provided.'}
                </p>
              </div>

              <div className="form-row-2">
                <div>
                  <span className="form-label">Instructor</span>
                  <div style={{ fontWeight: 600 }}>{detailModalCourse.instructor}</div>
                </div>
                <div>
                  <span className="form-label">Credits</span>
                  <div style={{ fontWeight: 600 }}>{detailModalCourse.credits} Credits</div>
                </div>
                <div>
                  <span className="form-label">Meeting Schedule</span>
                  <div>{detailModalCourse.schedule}</div>
                </div>
                <div>
                  <span className="form-label">Campus Room</span>
                  <div>{detailModalCourse.location}</div>
                </div>
                <div>
                  <span className="form-label">Academic Dates</span>
                  <div>
                    {detailModalCourse.start_date} to {detailModalCourse.end_date}
                  </div>
                </div>
                <div>
                  <span className="form-label">Registration Deadline</span>
                  <div>{detailModalCourse.registration_deadline}</div>
                </div>
              </div>

              <div>
                <span className="form-label">Prerequisites</span>
                <div style={{ color: 'var(--text-secondary)' }}>{detailModalCourse.prerequisites || 'None'}</div>
              </div>

              {/* Branch Allocations Breakdown */}
              <div style={{ marginTop: '8px' }}>
                <span className="form-label">Department Seat Allocations</span>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '6px' }}>
                  {detailModalCourse.branch_allocations?.map(b => (
                    <div
                      key={b.department_code}
                      style={{
                        padding: '6px 10px',
                        backgroundColor: 'var(--bg-subtle)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: 'var(--radius-sm)',
                        fontSize: '0.75rem'
                      }}
                    >
                      <strong>{b.department_code}:</strong> {b.branch_confirmed}/{b.allocated_seats} seats (
                      {b.branch_remaining} available)
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="modal-footer">
              <button type="button" className="btn btn-secondary" onClick={() => setDetailModalCourse(null)}>
                Close
              </button>
              {role === 'student' && (
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={!detailModalCourse.can_request_enrollment}
                  onClick={() => handleRequestEnrollment(detailModalCourse)}
                >
                  {detailModalCourse.registration_status === 'Approved'
                    ? 'Already Enrolled'
                    : detailModalCourse.registration_status === 'Pending'
                    ? 'Request Pending'
                    : 'Submit Enrollment Request'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* MODAL: Edit Course Allocations (Admin) */}
      {/* ==================================================================== */}
      {allocationModalCourse && (
        <div
          className="modal-backdrop"
          onClick={e => {
            if (e.target === e.currentTarget) setAllocationModalCourse(null);
          }}
        >
          <div className="modal-container">
            <div className="modal-header">
              <div>
                <button className="back-btn" onClick={() => setAllocationModalCourse(null)}>
                  <ArrowLeft size={14} /> Back to Allocations
                </button>
                <h3>Configure Branch Seat Allocations</h3>
                <p className="page-subtitle">
                  {allocationModalCourse.code} — Total Authorized Capacity: {allocationModalCourse.capacity} seats
                </p>
              </div>
              <button className="btn-icon-only" onClick={() => setAllocationModalCourse(null)}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleSaveAllocations}>
              <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                  Set seat quotas reserved for each academic branch. The sum of all branch quotas must not exceed the
                  total capacity ({allocationModalCourse.capacity}). Quotas cannot be reduced below confirmed
                  enrolments.
                </p>

                {allocationForm.map((alloc, idx) => (
                  <div key={alloc.department_code} className="form-group">
                    <label className="form-label">
                      {alloc.department_name} ({alloc.department_code}) — {alloc.branch_confirmed} confirmed
                    </label>
                    <input
                      type="number"
                      min={alloc.branch_confirmed || 0}
                      className="form-control"
                      value={alloc.allocated_seats}
                      onChange={e => {
                        const val = parseInt(e.target.value) || 0;
                        setAllocationForm(prev => {
                          const updated = [...prev];
                          updated[idx].allocated_seats = val;
                          return updated;
                        });
                      }}
                    />
                  </div>
                ))}
              </div>

              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setAllocationModalCourse(null)}>
                  Cancel
                </button>
                <button type="submit" disabled={isSubmitting} className="btn btn-primary">
                  {isSubmitting ? 'Saving…' : 'Save Branch Allocations'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* MODAL: Enrolled Students Roster (Admin) */}
      {/* ==================================================================== */}
      {rosterModal && (
        <div
          className="modal-backdrop"
          onClick={e => {
            if (e.target === e.currentTarget) setRosterModal(null);
          }}
        >
          <div className="modal-container modal-container-lg">
            <div className="modal-header">
              <div>
                <button className="back-btn" onClick={() => setRosterModal(null)}>
                  <ArrowLeft size={14} /> Back to Courses
                </button>
                <span className="course-code-badge">{rosterModal.code}</span>
                <h3 style={{ marginTop: '6px' }}>Enrolled Students Roster</h3>
                <p className="page-subtitle">
                  {rosterModal.title} • {rosterModal.confirmed_seats} confirmed students
                </p>
              </div>
              <button className="btn-icon-only" onClick={() => setRosterModal(null)}>
                <X size={18} />
              </button>
            </div>

            <div className="modal-body" style={{ padding: 0 }}>
              {rosterModal.roster && rosterModal.roster.length > 0 ? (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Student Reg No</th>
                      <th>College Reg No</th>
                      <th>Full Name</th>
                      <th>Department</th>
                      <th>Year / Sem</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rosterModal.roster.map(st => (
                      <tr key={st.id}>
                        <td className="table-code-cell">{st.student_reg_no}</td>
                        <td style={{ fontFamily: 'var(--font-mono)' }}>{st.college_reg_no}</td>
                        <td className="table-title-cell">{st.student_name}</td>
                        <td>{st.department_code}</td>
                        <td>
                          Y{st.academic_year} / S{st.semester}
                        </td>
                        <td>
                          <span
                            className={`badge ${
                              st.status === 'Approved' ? 'badge-approved' : 'badge-pending'
                            }`}
                          >
                            {st.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="empty-state" style={{ margin: '24px', border: 'none' }}>
                  <div className="empty-state-icon">
                    <Users size={24} />
                  </div>
                  <div className="empty-state-title">No Enrolled Students</div>
                  <div className="empty-state-desc">There are no approved registrations for this course offering.</div>
                </div>
              )}
            </div>

            <div className="modal-footer">
              <button type="button" className="btn btn-secondary" onClick={() => setRosterModal(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* MODAL: Confirmation Dialog */}
      {/* ==================================================================== */}
      {confirmDialog && (
        <div
          className="modal-backdrop"
          onClick={e => {
            if (e.target === e.currentTarget) setConfirmDialog(null);
          }}
        >
          <div className="modal-container" style={{ maxWidth: '480px' }}>
            <div className="modal-header">
              <h3>{confirmDialog.title}</h3>
              <button className="btn-icon-only" onClick={() => setConfirmDialog(null)}>
                <X size={18} />
              </button>
            </div>

            <div className="modal-body">
              <p style={{ color: 'var(--text-secondary)' }}>{confirmDialog.message}</p>
            </div>

            <div className="modal-footer">
              <button type="button" className="btn btn-secondary" onClick={() => setConfirmDialog(null)}>
                Cancel
              </button>
              <button
                type="button"
                className={`btn ${confirmDialog.isDanger ? 'btn-danger' : 'btn-primary'}`}
                onClick={confirmDialog.onConfirm}
              >
                {confirmDialog.confirmText || 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* TOAST NOTIFICATION CONTAINER */}
      {/* ==================================================================== */}
      {toast && (
        <div className="toast-container">
          <div className={`toast toast-${toast.type}`}>
            {toast.type === 'success' ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
            <span>{toast.message}</span>
            <button className="toast-close" onClick={() => setToast(null)}>
              <X size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
