# Northstar University ERP — Online Course Registration System

A deployment-ready, production-grade academic course registration and administration platform engineered with **React + Vite** on the frontend, a **Flask RESTful API** on the backend, and unified relational database support for **PostgreSQL** (production) and **SQLite** (local development).

Designed strictly in accordance with **institutional academic standards** and the **Adapt Interview Learning UI/UX benchmark**: sophisticated institutional forest-green (`#164e3f`) and warm-neutral (`#f8faf8`) palette, split-hero authentication, branch-enforced course eligibility, dynamic seat allocations, request-based student enrollment, formal course drop review, and curriculum credit compliance.

---

## 1. System Architecture

```
                          ┌───────────────────────────┐
                          │   React 18 + Vite SPA     │
                          │   (Tailored CSS / Lucide) │
                          └─────────────┬─────────────┘
                                        │ HTTPS / JSON
                                        ▼
                          ┌───────────────────────────┐
                          │    Flask 3.1 REST API     │
                          │ (Gunicorn / WSGI / RBAC)  │
                          └─────────────┬─────────────┘
                                        │
                    ┌───────────────────┴───────────────────┐
                    ▼                                       ▼
        ┌───────────────────────┐               ┌───────────────────────┐
        │  PostgreSQL 14+ / 16  │               │   SQLite 3 (Local)    │
        │ (Production / Cloud)  │               │ (Persistent Data File)│
        └───────────────────────┘               └───────────────────────┘
```

### Relational Schema (12 Tables)
- **Academic Setup**: `academic_programs`, `departments`, `curriculum_requirements`.
- **Identity & Access**: `students` (complete institutional profile), `admins` (Dean role), `audit_logs`.
- **Curriculum & Capacity**: `courses`, `course_eligibility` (branch/degree rules), `branch_allocations` (department quotas).
- **Workflows & Communication**: `registrations` (two-step approval), `drop_requests` (formal drop review), `notifications` (in-app notification center).

---

## 2. Local Development & Testing

### Prerequisites
- Python 3.10+ (Python 3.12 recommended)
- Node.js 18+ (Node.js 20 recommended) & npm

### Step 1: Start Backend
```bash
# Navigate to backend directory
cd backend

# Create & activate a virtual environment (optional but recommended)
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies (Flask, psycopg2-binary, gunicorn, etc.)
pip install -r requirements.txt

# Run initial migration and verify status
python migrate.py --status

# Launch development server (defaults to port 5001 in local dev)
python app.py
```
*Backend health check will be live at `http://127.0.0.1:5001/api/health`.*

### Step 2: Start Frontend
```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Launch Vite development server
npm run dev
```
*Frontend portal will be live at `http://localhost:5173`.*

### Step 3: Run Automated Test Suite
The automated test suite runs 13 end-to-end integration and security tests against the live database:
```bash
cd backend
python test_suite.py
```
*Output: `ALL 13 TESTS PASSED (100.0%)`.*

---

## 3. Pre-Configured Evaluation Personas

### Student Portal Personas
Each student has a distinct institutional profile, degree program, department, academic year, and semester:

| Student Name | Email | Password | Student Reg No | Program & Branch | Standing |
|:---|:---|:---|:---|:---|:---|
| **Aarav Kumar** | `aarav.kumar@student.edu` | `student123` | `STU2026CSE01` | B.Tech. CSE | Year 2 / Sem 4 (A) |
| **Rhea Sengupta** | `rhea.s@student.edu` | `student123` | `STU2026IT02` | B.Tech. IT | Year 2 / Sem 4 (B) |
| **Vikram Patel** | `vikram.p@student.edu` | `student123` | `STU2026ME03` | B.Tech. MECH | Year 2 / Sem 4 (A) |
| **Tanya Verma** | `tanya.v@student.edu` | `student123` | `STU2026LAW04` | LL.B. LAW | Year 2 / Sem 3 (A) |

*You can also click the quick demo chips on the login screen or register an arbitrary new student profile.*

### Administrator Portal Persona
- **Email**: `admin@northstar.edu`
- **Password**: `admin123`
- **Role**: Dean of Academic Affairs

---

## 4. Production Deployment Guide (Step-by-Step)

The application is structured for complete independence. Choose your preferred deployment pattern:

### Option A: Cloud PaaS (e.g. Render / Railway + Vercel)

#### 1. Database (PostgreSQL)
1. Create a managed PostgreSQL database on **Neon**, **Supabase**, **Render**, or **Railway**.
2. Copy your connection URI (`postgresql://user:password@host:port/dbname?sslmode=require`).
3. Run the schema initializer:
   ```bash
   export DATABASE_URL="your-postgresql-connection-uri"
   python backend/migrate.py --init
   ```
   *(Or copy the contents of `backend/schema.sql` into the Supabase / Neon SQL Editor).*

#### 2. Backend (Render / Railway)
1. Create a new **Web Service** pointing to the `backend/` directory.
2. Configure runtime: **Python 3**.
3. Build command:
   ```bash
   pip install -r requirements.txt
   ```
4. Start command:
   ```bash
   gunicorn --bind 0.0.0.0:$PORT --workers 4 --threads 2 app:app
   ```
5. Set Environment Variables:
   - `FLASK_ENV`: `production`
   - `DATABASE_URL`: `your-postgresql-connection-uri`
   - `SECRET_KEY`: `generate-a-random-32-byte-hex-string`
   - `CORS_ORIGINS`: `https://your-frontend-app.vercel.app`
   - `OCR_ADMIN_PASSWORD`: `your-secure-admin-password`

#### 3. Frontend (Vercel / Netlify / Cloudflare Pages)
1. Create a new project pointing to the `frontend/` directory.
2. Build command:
   ```bash
   npm run build
   ```
3. Output directory: `dist`.
4. Set Environment Variable:
   - `VITE_API_BASE_URL`: `https://your-backend-service.onrender.com/api`
5. Deploy.

---

### Option B: Docker Compose (Single VM / VPS: AWS EC2, DigitalOcean, Linode, Hetzner)

A complete `docker-compose.yml` is provided at the repository root with PostgreSQL 16, persistent volume storage, health checks, Gunicorn backend, and Nginx reverse proxy:

```bash
# 1. Clone repository to your server
git clone <your-repo-url>
cd online-course-registration

# 2. Configure environment
cp .env.example .env
# Edit .env with your domain and secure passwords:
# nano .env

# 3. Build and launch services in detached mode
docker compose up -d --build

# 4. Verify running containers
docker compose ps

# 5. Check database status inside backend container
docker compose exec backend python migrate.py --status
```
*The application is immediately available on port 80 (HTTP) or can be placed behind an SSL termination proxy such as Caddy or Certbot.*

---

### Option C: Traditional Linux VM (Ubuntu 22.04 / 24.04 with Systemd & Nginx)

#### 1. Setup Backend Systemd Service
Create `/etc/systemd/system/course-erp.service`:
```ini
[Unit]
Description=Northstar University Course ERP Backend
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/course-erp/backend
Environment="PATH=/var/www/course-erp/backend/venv/bin"
Environment="DATABASE_URL=postgresql://coursedb_user:password@localhost/coursedb"
Environment="SECRET_KEY=your-production-secret-key"
Environment="CORS_ORIGINS=https://portal.university.edu"
Environment="PORT=5000"
ExecStart=/var/www/course-erp/backend/venv/bin/gunicorn --workers 4 --threads 2 --bind 127.0.0.1:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now course-erp
```

#### 2. Build Frontend
```bash
cd /var/www/course-erp/frontend
npm ci
export VITE_API_BASE_URL="/api"
npm run build
```

#### 3. Configure Nginx
Create `/etc/nginx/sites-available/course-erp`:
```nginx
server {
    listen 80;
    server_name portal.university.edu;

    root /var/www/course-erp/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:5000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 5. Environment Variables Reference

### Backend Variables (`backend/.env`)

| Variable | Required | Default | Description |
|:---|:---:|:---|:---|
| `DATABASE_URL` | **Yes (Prod)** | *None* | PostgreSQL URI (`postgresql://user:pass@host:5432/db`). When set, automatically engages PostgreSQL engine. |
| `DATABASE_PATH` | No | `courses.db` | Path for persistent SQLite database file if PostgreSQL is not used. |
| `SECRET_KEY` | **Yes (Prod)** | Built-in fallback | Cryptographic secret for signing sessions and tokens. |
| `CORS_ORIGINS` | **Yes (Prod)** | `*` | Comma-separated list of allowed frontend origins (e.g. `https://portal.university.edu`). |
| `PORT` | No | `5000` | Port for WSGI / Gunicorn server. Automatically assigned by cloud hosts. |
| `FLASK_ENV` | No | `production` | Set to `production` for security hardening. |
| `OCR_ADMIN_PASSWORD` | No | `admin123` | Initial default password for seed administrator account. |

### Frontend Variables (`frontend/.env`)

| Variable | Required | Default | Description |
|:---|:---:|:---|:---|
| `VITE_API_BASE_URL` | No | `/api` (prod) / `http://127.0.0.1:5000/api` (dev) | Full backend API address. When frontend is served behind reverse-proxy, leave blank to use relative `/api`. |

---

## 6. REST API Endpoint Reference

| Method | Endpoint | Access | Purpose |
|:---|:---|:---:|:---|
| `GET` | `/api/health` | Public | Service status, engine diagnostic, and version |
| `GET` | `/api/academic/config` | Public | Degree programs, departments, and curricula |
| `POST` | `/api/academic/programs` | Admin | Register new degree program |
| `POST` | `/api/academic/departments` | Admin | Register new academic department |
| `POST` | `/api/student/register` | Public | Register student with full academic profile |
| `POST` | `/api/student/login` | Public | Student authentication (PBKDF2 SHA-256) |
| `POST` | `/api/admin/login` | Public | Administrator authentication |
| `POST` | `/api/logout` | Auth | Terminate active session token |
| `GET` | `/api/student/profile` | Student | Academic profile & credit compliance standing |
| `GET` | `/api/courses` | Auth | Course catalogue (strictly filtered by student branch) |
| `GET` | `/api/courses/<id>` | Auth | Course details & administrative roster |
| `POST` | `/api/courses` | Admin | Create curriculum course |
| `PATCH` | `/api/courses/<id>` | Admin | Update course capacity, schedule, status |
| `DELETE` | `/api/courses/<id>` | Admin | Delete course (cascades registrations) |
| `GET` | `/api/courses/<id>/allocations` | Admin | Inspect department seat quotas |
| `PUT` | `/api/courses/<id>/allocations` | Admin | Update branch seat allocations |
| `GET` | `/api/registrations` | Auth | List registrations (scoped for student / full for Dean) |
| `POST` | `/api/registrations` | Student | Submit enrollment request (status: `Pending`) |
| `GET` | `/api/registrations/<id>/review-report` | Admin | Full Student Academic Review Report |
| `PATCH` | `/api/registrations/<id>/decision` | Admin | Approve or reject registration (transactional lock) |
| `POST` | `/api/drop-requests` | Student | Submit course drop request with reason |
| `GET` | `/api/drop-requests` | Auth | List drop requests |
| `PATCH` | `/api/drop-requests/<id>/decision` | Admin | Approve or reject drop request |
| `GET` | `/api/notifications` | Auth | User notification center & unread count |
| `PATCH` | `/api/notifications/read-all` | Auth | Mark all notifications as read |
| `GET` | `/api/students` | Admin | Student directory with credit totals |
| `GET` | `/api/students/<id>` | Admin | Detailed student profile and history |
| `GET` | `/api/audit-logs` | Admin | Comprehensive system audit log |
| `GET` | `/api/summary` | Public | University aggregate statistics |

---

## 7. Security Hardening Measures Implemented
1. **Password Security**: Salted PBKDF2 SHA-256 password hashing with 100,000 iterations via Python's standard `hashlib.pbkdf2_hmac`.
2. **Session Security**: High-entropy cryptographically secure random tokens (`secrets.token_urlsafe(32)`).
3. **Role-Based Access Control**: Strict `@require_role("admin")` and `@require_role("student")` decorators guarding API routes.
4. **Data Concurrency**: Transactional write-locking (`BEGIN IMMEDIATE` in SQLite, `BEGIN` in PostgreSQL) on enrollment decisions and drop actions to prevent race conditions.
5. **Audit Trail**: Non-repudiation audit logging (`audit_logs`) tracking actor email, action type, affected entity, and timestamp.
