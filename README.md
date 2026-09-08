<div align="center">

# Career Catalyst
### Enterprise AI-Powered Career Development, ATS Analytics & Assessment Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-5.2-green.svg)](https://www.djangoproject.com/)
[![Database](https://img.shields.io/badge/database-PostgreSQL%20%2F%20Neon-336791.svg)](https://neon.tech/)
[![Frontend](https://img.shields.io/badge/UI-Bootstrap%205%20%7C%20Vanilla%20JS-7952B3.svg)](https://getbootstrap.com/)
[![Architecture](https://img.shields.io/badge/architecture-modular%20SaaS-orange.svg)](#architecture--directory-structure)

<p align="center">
  <b>An end-to-end career acceleration engine providing ATS resume parsing, AI-driven skill gap recommendations, proctored technical evaluations, curated roadmaps, and 1-on-1 mentorship.</b>
</p>

</div>

---

## 📌 Overview

**Career Catalyst** is a modular, production-grade SaaS platform built with Django and PostgreSQL, designed to bridge the gap between education and modern industry hiring requirements. It delivers intelligent career guidance through vector-based resume matching, live proctored coding assessments, structured curriculum roadmaps, and expert mentor interaction.

---

## ⚡ Key Platform Capabilities

```
                       ┌─────────────────────────────────────────┐
                       │            Career Catalyst              │
                       │           Enterprise Engine             │
                       └────────────────────┬────────────────────┘
                                            │
         ┌──────────────────┬───────────────┴───────────────┬──────────────────┐
         │                  │                               │                  │
         ▼                  ▼                               ▼                  ▼
┌─────────────────┐ ┌─────────────────┐           ┌─────────────────┐ ┌─────────────────┐
│   AI Guidance   │ │   ATS Resume    │           │ Code Sandbox &  │ │  Mentorship &   │
│  & Readiness    │ │  Analyzer & PDF │           │  AI Proctoring  │ │    Community    │
└─────────────────┘ └─────────────────┘           └─────────────────┘ └─────────────────┘
```

### 1. 🧠 AI Career Recommendation & Gap Analysis (`apps/recommendation/`)
- **Readiness Scoring Algorithm**: Pre-calculates comprehensive placement readiness using multi-factor indexing (skills count, GPA, completed projects, verified certifications).
- **Radar Visualizations**: Renders multi-dimensional competency radar charts using Chart.js.
- **LLM Curriculum Synthesis**: Integrates high-throughput LLM pipelines (Groq LLaMA-3 / OpenAI) to generate customized 30/60/90-day skill transition strategies with deterministic database fallbacks.

### 2. 📄 ATS Resume Compiler & Job-Match Scorer (`apps/resume/` & `apps/ai_resume/`)
- **Split-Screen Interactive Workspace**: Live DOM-to-PDF synchronization with sub-second preview rendering.
- **Keyword Vector Analysis**: Evaluates resume content against target Job Descriptions (JD), outputting match percentages and missing competency recommendations.
- **Dynamic Modular Forms**: Add/remove education, experience, and project entries with AJAX transactions.

### 3. 🧭 Curated Learning Roadmaps (`apps/roadmaps/`)
- **15+ Industry Pathways**: Step-by-step 12-week roadmaps covering Software Engineering, Data Science, DevOps, Cybersecurity, Product Management, and more.
- **Progress Tracking**: Interactive milestone checklists with state persistence.

### 4. 💻 Proctored Coding Sandbox & Skill Evaluation (`apps/interviews/`)
- **Multi-Theme Code Sandbox**: Custom code execution editor supporting Python, JavaScript, and Java with automated indentation parsing and custom syntax themes (VS Dark, Monokai, Solarized).
- **AI Computer Vision Proctoring**: Client-side face landmark and multi-face detection (BlazeFace) combined with object detection (COCO-SSD) to flag anomalies (e.g., unauthorized devices, looking away).
- **Integrity Enforcement**: Real-time event logging tracking window blurs, right-click attempts, and tab switching with automated soft-submission thresholds.

### 5. 🤝 1-on-1 Mentor Network & Discussion Hub (`apps/community/`)
- **Verified Mentor Directory**: Filter industry mentors by domain expertise, company affiliation, and ratings.
- **Direct Messaging Rooms**: Private message exchanges with real-time feedback flows.

### 6. 🛡️ Enterprise Security & Authentication (`apps/accounts/`)
- **PBKDF2-Hashed OTP Verification**: 6-digit email activation with brute-force rate limiting (5 attempts lock), 60-second resend throttling, and automated database cleanup.
- **Hybrid Email Relay**: Automatically routes via HTTPS REST API (Brevo) on cloud environments to bypass PaaS SMTP port blocks, with SMTP fallback for local development.

---

## 🛠️ Technology Stack

| Domain | Technologies |
| :--- | :--- |
| **Backend Framework** | Python 3.10+, Django 5.2 |
| **Database & ORM** | PostgreSQL (Production / Neon Serverless), SQLite (Local Dev fallback) |
| **Task & Static Assets** | WhiteNoise 6.x, Gunicorn WSGI |
| **Frontend Architecture** | HTML5, Modern CSS3 Custom Variables, Bootstrap 5.3, Vanilla JavaScript (ES6+) |
| **AI / Computer Vision** | Groq LLaMA-3 REST API, TensorFlow.js (BlazeFace, COCO-SSD) |
| **Data Visualization** | Chart.js 4.x |
| **Security & Privacy** | PBKDF2 Hashing, CSRF Protection, Anti-Inspect Client Hardening, Content Security Policy |

---

## 📁 Architecture & Directory Structure

```text
Career-Catalyst-Django/
├── apps/
│   ├── accounts/          # Authentication, PBKDF2 OTP verification, Custom User services
│   ├── ai_resume/         # AI-powered ATS resume parsing & keyword matching
│   ├── community/         # Mentor directory, 1-on-1 messaging & forum channels
│   ├── core/              # Global views, landing page modules, dashboard dispatchers
│   ├── interviews/        # Code sandbox, proctoring stream & automated grading
│   ├── profiles/          # User profile management, skill taxonomy & portfolio assets
│   ├── recommendation/    # Career matching engine, readiness scores & LLM roadmap logic
│   ├── resume/            # Dynamic resume builder, split-screen PDF preview
│   └── roadmaps/          # Multi-track learning pathways, weekly checklists
├── config/                # Project routing, WSGI/ASGI handlers, environment configurations
├── static/                # Global stylesheet design systems, scripts, assets
│   ├── css/               # base.css, components.css, chatbot.css, home.css
│   ├── js/                # main.js (theme engine & anti-inspect), home.js, chatbot.js
│   └── images/            # Brand marks, vector assets, favicons
├── templates/             # Semantic Django template tree with modular partials
├── build.sh               # Cloud CI/CD build script (pip install, collectstatic, migrate)
├── Procfile               # Production WSGI process definition
├── requirements.txt       # Frozen production package dependencies
└── manage.py              # Django administrative CLI
```

---

## 🚀 Quickstart & Local Development

### 1. Prerequisites
- Python 3.10+
- Git


### 2. Create & Activate a Virtual Environment
```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```
```

### 4. Apply Migrations & Seed Baseline Data
```bash
python manage.py migrate
python manage.py seed_roadmaps
python manage.py seed_community
python manage.py seed_interviews
```

### 5. Run the Development Server
```bash
python manage.py runserver
```
Visit `http://127.0.0.1:8000/` in your browser.

---

## 🧪 Testing & Quality Assurance

Run the automated test suite covering authentication, profiles, services, and core workflows:

```bash
python manage.py test apps.accounts.tests apps.profiles.tests apps.core.tests
```

---

## 🚢 Production Deployment

The platform is optimized for zero-downtime deployment on containerized PaaS platforms (e.g., **Render**, **Railway**, **Heroku**) paired with cloud PostgreSQL (**Neon**):

1. **Build Step**: Automatically runs `./build.sh` (installs dependencies, executes `collectstatic --noinput`, and applies database migrations).
2. **Web Process**: Launched via `gunicorn config.wsgi:application`.
3. **Static Storage**: Served directly with Gzip/Brotli compression using **WhiteNoise**.
4. **Outbound Mail**: Uses **Brevo REST API** via HTTPS (`BREVO_API_KEY`) to guarantee zero-latency email delivery across cloud network firewalls.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<div align="center">
  <sub>Engineered with precision for career development. Built by Syed Farhan Ahmed.</sub>
</div>