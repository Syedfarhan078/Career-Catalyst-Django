import re
import io
import pdfplumber
import pypdf
import docx

def clean_text(text):
    """
    Remove non-printable characters, unprintable Unicode artifacts, and clean whitespaces.
    """
    if not text:
        return ""
    text = text.replace('\ufffd', ' ').replace('\x00', '')
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\r\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def extract_text_from_pdf(file):
    """
    Extract raw text from a PDF file using a robust 6-strategy extraction pipeline.
    Handles Canva, Figma, LaTeX, multi-column, and table-based PDF resumes.
    """
    if hasattr(file, 'seek'):
        file.seek(0)
        
    file_bytes = file.read() if hasattr(file, 'read') else file
    
    if hasattr(file, 'seek'):
        file.seek(0)
        
    if not file_bytes:
        return ""
        
    extracted_text_chunks = []
    
    # Strategy 1 & 2 & 3: pdfplumber standard, layout, words, and tables
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                # 1. Standard text
                p_text = page.extract_text()
                if p_text and len(p_text.strip()) > 20:
                    extracted_text_chunks.append(p_text)
                    continue
                    
                # 2. Layout-aware extraction
                try:
                    p_layout_text = page.extract_text(layout=True)
                    if p_layout_text and len(p_layout_text.strip()) > 20:
                        extracted_text_chunks.append(p_layout_text)
                        continue
                except Exception:
                    pass
                    
                # 3. Word-box token extraction (Crucial for Canva / complex design layouts)
                try:
                    words = page.extract_words()
                    if words:
                        word_text = " ".join(w.get('text', '') for w in words if w.get('text'))
                        if len(word_text.strip()) > 20:
                            extracted_text_chunks.append(word_text)
                            continue
                except Exception:
                    pass
                    
                # 4. Table cell extraction
                try:
                    tables = page.extract_tables()
                    for table in tables:
                        for row in table:
                            extracted_text_chunks.append(" ".join(str(c) for c in row if c))
                except Exception:
                    pass
    except Exception as e:
        print(f"pdfplumber extraction notice: {e}")
        
    final_text = "\n".join(extracted_text_chunks).strip()
    
    # Strategy 5 & 6: pypdf fallback
    if len(final_text) < 30:
        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            pypdf_chunks = []
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    pypdf_chunks.append(t)
            pypdf_combined = "\n".join(pypdf_chunks).strip()
            if len(pypdf_combined) > len(final_text):
                final_text = pypdf_combined
        except Exception as e:
            print(f"pypdf extraction notice: {e}")
            
    return clean_text(final_text)

def extract_text_from_docx(file):
    """
    Extract raw text from a DOCX file using python-docx with stream safety.
    """
    if hasattr(file, 'seek'):
        file.seek(0)
        
    file_bytes = file.read() if hasattr(file, 'read') else file
    
    if hasattr(file, 'seek'):
        file.seek(0)
        
    if not file_bytes:
        return ""
        
    text = []
    try:
        doc = docx.Document(io.BytesIO(file_bytes))
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text.append(paragraph.text.strip())
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        text.append(cell.text.strip())
    except Exception as e:
        print(f"DOCX parsing notice: {e}")
        
    return clean_text("\n".join(text))

def parse_resume_file(file):
    """
    Determine file type (PDF/DOCX) and extract text with stream safety.
    """
    filename = getattr(file, 'name', '').lower()
    if filename.endswith('.pdf'):
        return extract_text_from_pdf(file)
    elif filename.endswith('.docx') or filename.endswith('.doc'):
        return extract_text_from_docx(file)
    else:
        # Fallback to PDF then plain text
        try:
            parsed = extract_text_from_pdf(file)
            if parsed:
                return parsed
        except Exception:
            pass
            
        try:
            if hasattr(file, 'seek'):
                file.seek(0)
            raw = file.read()
            if hasattr(file, 'seek'):
                file.seek(0)
            if isinstance(raw, bytes):
                return clean_text(raw.decode('utf-8', errors='ignore'))
            return clean_text(str(raw))
        except Exception:
            raise ValueError("Unsupported file format. Please upload PDF or DOCX.")

SECTION_HEADER_PATTERNS = {
    "education": [r"\beducation\b", r"\bacademics?\b", r"\bacademic background\b", r"\buniversity\b"],
    "experience": [r"\bexperience\b", r"\bwork experience\b", r"\bemployment\b", r"\bprofessional experience\b", r"\bcareer history\b", r"\binternships?\b"],
    "projects": [r"\bprojects?\b", r"\btechnical projects\b", r"\bpersonal projects\b", r"\bkey projects\b", r"\bportfolio\b"],
    "skills": [r"\bskills?\b", r"\btechnical skills\b", r"\bcore competencies\b", r"\btools & technologies\b", r"\btechnologies\b", r"\bexpertise\b"],
    "certifications": [r"\bcertifications?\b", r"\bcertificates?\b", r"\blicenses?\b", r"\bachievements?\b", r"\bawards?\b"],
    "summary": [r"\bsummary\b", r"\bprofessional summary\b", r"\babout me\b", r"\bprofile\b", r"\bobjective\b"]
}

def segment_resume_sections(text):
    """
    Segments resume text into distinct structured sections.
    Returns dictionary with section contents and boolean presence.
    """
    lines = text.split('\n')
    sections = {
        "summary": [],
        "education": [],
        "experience": [],
        "projects": [],
        "skills": [],
        "certifications": [],
        "other": []
    }
    
    current_section = "other"
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
            
        if len(stripped.split()) <= 4:
            matched_sec = None
            for sec_name, patterns in SECTION_HEADER_PATTERNS.items():
                for pat in patterns:
                    if re.search(pat, stripped, re.IGNORECASE):
                        matched_sec = sec_name
                        break
                if matched_sec:
                    break
                    
            if matched_sec:
                current_section = matched_sec
                continue
                
        sections[current_section].append(stripped)
        
    result_sections = {k: "\n".join(v).strip() for k, v in sections.items()}
    presence = {
        "education": bool(result_sections["education"]),
        "experience": bool(result_sections["experience"]),
        "projects": bool(result_sections["projects"]),
        "skills": bool(result_sections["skills"]),
        "certifications": bool(result_sections["certifications"]),
        "summary": bool(result_sections["summary"])
    }
    
    return {
        "sections": result_sections,
        "presence": presence
    }

def extract_bullet_points(text):
    """
    Extracts individual bullet points and accomplishment statements from resume.
    Focuses on Experience and Projects.
    """
    segmented = segment_resume_sections(text)
    candidate_text = segmented["sections"]["experience"] + "\n" + segmented["sections"]["projects"]
    if not candidate_text.strip():
        candidate_text = text
        
    bullets = []
    lines = candidate_text.split('\n')
    
    bullet_regex = re.compile(r'^\s*([•\-\*–—>]|\d+[\.\)])\s*(.+)$')
    
    current_bullet = ""
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_bullet:
                bullets.append(current_bullet.strip())
                current_bullet = ""
            continue
            
        m = bullet_regex.match(stripped)
        if m:
            if current_bullet:
                bullets.append(current_bullet.strip())
            current_bullet = m.group(2)
        elif current_bullet and len(stripped.split()) > 2 and not stripped.isupper():
            current_bullet += " " + stripped
        elif len(stripped.split()) >= 6:
            if current_bullet:
                bullets.append(current_bullet.strip())
            current_bullet = stripped
            
    if current_bullet:
        bullets.append(current_bullet.strip())
        
    cleaned_bullets = []
    for b in bullets:
        words = b.split()
        if 4 <= len(words) <= 60 and not re.match(r'^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{4})\b', b, re.IGNORECASE):
            cleaned_bullets.append(b)
            
    return cleaned_bullets
