# Career Catalyst — Comprehensive AI-Powered Career Development & Proctoring Platform

Career Catalyst is a modern, modular, production-ready SaaS application built in Django designed to accelerate professional growth and bridge the technical skills gap for university students. 

---

## 🎯 The Problem We Are Solving

Transitioning from academia to the professional workforce is complex and highly fragmented for Engineer students and Fresh Graduates:
1. **The Skills Gap**: Traditional university curriculums are often decoupled from real-world technology stacks, leaving students confused about what skills to acquire.
2. **Resume Roadblocks**: Students lack ATS-optimized formatting guidelines and have difficulty translating academic projects into structured resumes.
3. **Interview Anxiety & Dishonesty**: Virtual coding examinations and interview preparation are intimidating, and standard online testing lacks secure, lightweight proctoring models.
4. **Fragmented Guidance**: Career counseling is either expensive or inaccessible, lacking personal, automated recommendations that scale.

---

## 🚀 Core Features

Career Catalyst unifies career guidance, resume building, learning paths, interview prep, and mentorship into one intelligent platform:

### 1. AI Career Recommendation & Guidance Engine (`apps/recommendation/`)
- **Weighted Core Readiness Score**: Pre-calculates an initial placement readiness level based on CGPA, profile skills count, resume projects, and active learning paths.
- **Groq LLM Hybrid Parser**: Processes candidate variables and database roadmap syllabus milestones to suggest target matches, strengths, and customized 30/90-day transition plans.
- **Local Fallback Engine**: Falls back seamlessly to database parsing if external API connections are unconfigured, preventing any service interruptions.

### 2. ATS Resume Builder & Analyzer (`apps/resume/` & `apps/ai_resume/`)
- **Interactive Forms**: A split-screen resume workspace providing a live iframe PDF/HTML preview.
- **Dynamic DOM Updates**: Added AJAX endpoints and scripts to perform lists additions and deletions instantly without full-page reloads.
- **One-Click Profile Autofill**: Instantly imports college, graduation year, degree, and comma-separated skills from the Student Profile in one click.

### 3. Curriculum Learning Roadmaps (`apps/roadmaps/`)
- **Structured Milestones**: 12-week learning pathways across 15 career tracks containing estimated study hours, difficulties, and resource types.
- **Verified References**: Top-tier public documentation, video, and article reference URLs linked directly to each weekly topic.

### 4. Code Workspace & MCQ Quiz Hub (`apps/interviews/`)
- **Smart Indentation Editor**: Intercepts keyboard events on the code editor. Pressing `Tab` inserts four spaces, and pressing `Enter` preserves indentation level and automatically appends four spaces for lines ending with a colon (`:`).
- **Proctor Warning logs**: Tracks tab switches, window blurs, right-clicks, and copy-paste blocks.

### 5. Computer Vision AI Proctoring Stream
- **Alternating Model Cycles**: Staggers the execution of BlazeFace (facial landmark bounds) and COCO-SSD (cell phone object classifiers) to prevent UI thread lockups and eliminate typing lag.
- **Violation Hold-Times**: Locks warning state indicators (e.g. Phone Detection, Looking Away, Face Missing) as active for **5 seconds** to prevent flashing.
- **Risk Score Gauge**: Computes a dynamic cumulative risk bar (Green $\rightarrow$ Yellow $\rightarrow$ Red) and automatically logs events to the `ProctorLog` database model.

### 6. Mentor Marketplace & Messaging (`apps/community/`)
- **Marketplace Listing**: Filter verified mentors based on company, domains, rating, and recommended match scores.
- **Direct Chat Engine**: Private 1-to-1 chat messaging room with live auto-reply logs simulating specific mentor advice.

---

## 🛠️ Architecture & Technical Stack

We adhere strictly to clean architecture and separation of concerns:
- **Core**: Django 5.x, SQLite/PostgreSQL, Bootstrap 5 (Styling custom properties), and Vanilla JavaScript.
- **Separation Pattern**:
  - `models.py`: Defines database schemas.
  - `services.py`: Implements transaction business logic (no raw database writes inside views).
  - `forms.py`: Handles forms rendering and custom clean validations.
  - `utils.py`: Contains matching algorithms and scoring logic.

---

## ⚡ Getting Started

### 1. Activate the Virtual Environment
Navigate to the root directory and run the command matching your shell:
* **PowerShell**:
  ```powershell
  .venv\Scripts\Activate.ps1
  ```
* **Command Prompt (cmd)**:
  ```cmd
  .venv\Scripts\activate.bat
  ```
* **Git Bash**:
  ```bash
  source .venv/Scripts/activate
  ```

### 2. Configure Environment Variables
Create or open the `.env` file at the project root and add the following keys:
```env
SECRET_KEY=replace_this_with_a_secure_key_later
DEBUG=True
GROQ_API_KEY=gsk_your_actual_groq_key_here
```

### 3. Run Database Migrations
```bash
python manage.py migrate
```

### 4. Seed Database Data
```bash
python manage.py seed_roadmaps
python manage.py seed_community
```

### 5. Run the Server
```bash
python manage.py runserver
```
Visit the platform at `http://127.0.0.1:8000/`.