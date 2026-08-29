# 🚀 Career Catalyst — Comprehensive AI-Powered Career Development & Proctoring Platform

Career Catalyst is a modern, modular, production-ready SaaS application built in Django designed to accelerate professional growth and bridge the technical skills gap for university students. 

---

## 🎯 The Problem We Are Solving

Transitioning from academia to the professional workforce is complex and highly fragmented for Engineer students and Fresh Graduates:
1. **The Skills Gap**: Traditional university curriculums are often decoupled from real-world technology stacks, leaving students confused about what skills to acquire.
2. **Resume Roadblocks**: Students lack ATS-optimized formatting guidelines and have difficulty translating academic projects into structured resumes.
3. **Interview Anxiety & Dishonesty**: Virtual coding examinations and interview preparation are intimidating, and standard online testing lacks secure, lightweight proctoring models.
4. **Fragmented Guidance**: Career counseling is either expensive or inaccessible, lacking personal, automated recommendations that scale.

---

## 🚀 Core Features & Modules

Career Catalyst unifies career guidance, resume building, learning paths, interview prep, and mentorship into one intelligent, highly interactive platform:

### 1. 🤖 AI Virtual Assistant Chatbot (New!)
* **Animated Robot Mascot**: Features a custom-rendered floating robot mascot that reacts to mouse hovers with a continuous bobbing floating loop (`@keyframes bot-float`) and a playful waving animation (`@keyframes bot-wave`).
* **Zero-Server-Cost Local Router**: Uses regex-based routing to capture queries regarding career pathways, resumes, mentorships, and practice hub questions, immediately returning deep links to the platform's corresponding feature pages.
* **Persistent History**: Saves session chat logs inside the browser's `sessionStorage` so the conversation remains intact as students navigate between pages.

### 2. 🧠 AI Career Recommendation & Guidance Engine (`apps/recommendation/`)
* **Weighted Core Readiness Score**: Pre-calculates an initial placement readiness level based on CGPA, profile skills count, resume projects, and active learning paths.
* **Radar Chart Metrics**: Renders an interactive Chart.js Radar Plot comparison against core curriculum dimensions (e.g. Coding Skills, Project Experience, CGPA, Certifications).
* **Weekly Roadmap Sylabus Checklists**: Converted standard milestone listings into collapsible weekly checklist items where students can check off tasks. checked states dynamically strikethrough topic names and persist completion state locally.
* **Groq LLM Hybrid Parser**: Processes candidate variables and database roadmap syllabus milestones to suggest target matches, strengths, and customized 30/90-day transition plans. Falls back to local database parsing if API keys are unconfigured.

### 3. 📄 ATS Resume Builder & Analyzer (`apps/resume/` & `apps/ai_resume/`)
* **Interactive Split-Screen Builder**: A split-screen resume workspace providing a live iframe PDF/HTML preview.
* **AJAX Dynamic DOM Updates**: Perform section additions (Education, Experience, Projects) and deletions instantly without full-page reloads.
* **One-Click Profile Autofill**: Instantly imports college, graduation year, degree, and comma-separated skills from the Student Profile in one click.
* **ATS Grading & Analysis**: Compares compiled resume content against pasted job description keyword vectors to grade compliance scores and list missing keywords.

### 4. 🧭 Curriculum Learning Roadmaps (`apps/roadmaps/`)
* **Structured Milestones**: 12-week learning pathways across 15 career tracks containing estimated study hours, difficulties, and resource types.
* **Verified References**: Top-tier public documentation, video, and article reference URLs linked directly to each weekly topic.
* **Theme-Adaptive Checklists**: Topic checkoff selections automatically fade into translucent green/grey highlights based on the active color theme.

### 5. 💻 Code Sandbox & MCQ Quiz Hub (`apps/interviews/`)
* **Multi-Theme Coding Editor**: small dropdown theme switcher directly above the code editor (VS-Dark, Monokai, GitHub Light, Solarized Dark) that toggles css styling variables and persists coding workspace themes in local storage.
* **Smart Indentation Editor**: Intercepts keyboard events on the code editor. Pressing `Tab` inserts four spaces, and pressing `Enter` preserves indentation level and automatically appends four spaces for lines ending with a colon (`:`).
* **Multi-Layer Proctor Warning System**: Tracks tab switches, window blurs, right-clicks, and copy-paste blocks. Warning counts trigger animated toasts, and exceeding limits soft-submits the candidate's test automatically.

### 6. 👁️ Webcam AI Proctoring Stream
* **Alternating Model Cycles**: Staggers the execution of BlazeFace (facial landmark bounds) and COCO-SSD (cell phone object classifiers) to prevent UI thread lockups and eliminate typing lag.
* **Violation Hold-Times**: Locks warning state indicators (e.g. Phone Detection, Looking Away, Face Missing) as active for **5 seconds** to prevent flashing.
* **Risk Score Gauge**: Computes a dynamic cumulative risk bar (Green $\rightarrow$ Yellow $\rightarrow$ Red) and automatically logs events to the `ProctorLog` database model.

### 7. 🤝 Mentor Marketplace & Messaging (`apps/community/`)
* **Marketplace Listing**: Filter verified mentors based on company, domains, rating, and recommended match scores.
* **Direct Chat Engine**: Private 1-to-1 chat messaging room with live auto-reply logs simulating specific mentor advice.

---

## 🎨 Premium Design & Usability

* **Global Dark / Light Switcher**: A sleek sun/moon theme toggle button in the navbar toggles CSS custom variables (adjusting slate backgrounds, cards, borders, and text colors) using high-specificity selectors (`html[data-theme="dark"]`) and persists preferences in `localStorage`.
* **Dark Mode Visual Enhancements**:
  * Dropdown input fields (`.form-select`) adaptively render dark navy backgrounds with white text.
  * Form labels and checkboxes automatically shift color to keep readability high.
  * Table rows are forced to card-bg color blocks, preventing light text from rendering invisible on top of white default bootstrap rows.
  * Circular progress score indicators and timelines adaptively blend background circles with active card backgrounds (`var(--card-bg)`).

---

## 📊 Demo Presentation Slides Deck (New!)

To assist with presenting the project, an interactive 15-page slide deck viewer has been built and included inside the project artifacts folder:
* **Interactive Slides Viewer**: **[presentation.html](file:///C:/Users/SYED%20FARHAN%20AHMED/.gemini/antigravity/brain/798ef57c-31b5-40be-89e9-67b5f4ff8788/presentation.html)**
* **Features**:
  * Keyboard navigation supported via Left/Right arrows or spacebar.
  * Built-in vector flowcharts (SVGs) showing the system flow diagrams cleanly without external CDN script load errors.
  * Detailed visual diagrams for **System Architecture** and **Database Entity-Relationship Schema (ERD)**.
* **Raw Slide Content Reference**: **[presentation_slides.md](file:///C:/Users/SYED%20FARHAN%20AHMED/.gemini/antigravity/brain/798ef57c-31b5-40be-89e9-67b5f4ff8788/presentation_slides.md)**.

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