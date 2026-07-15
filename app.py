import os
import re
import io
import base64
import logging
import spacy
import pdfplumber
import docx
from datetime import datetime
from flask import Flask, render_template, request, redirect, flash, url_for

# Force Matplotlib to use a headless background engine (Required for Render/Linux server environments)
import matplotlib
matplotlib.use('Agg')
from matplotlib.figure import Figure

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "prod-screening-system-token-9988")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    nlp = spacy.blank("en") if spacy else None

class ResumeParserEngine:
    def extract_text(self, file):
        fn = file.filename.lower()
        stream = io.BytesIO(file.read())
        if fn.endswith(".pdf"):
            with pdfplumber.open(stream) as pdf:
                return "".join([p.extract_text() or "" for p in pdf.pages])
        elif fn.endswith((".docx", ".doc")):
            return "".join([p.text + "\n" for p in docx.Document(stream).paragraphs])
        raise ValueError("Unsupported format. Use PDF or DOCX.")

    def parse_profile(self, text):
        clean = re.sub(r'\s+', ' ', text).strip()
        email = re.findall(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', clean)
        phone = re.findall(r'(\+?\d[\d\s\-]{8,15}\d)', clean)
        lnk = re.findall(r'https?://(?:www\.)?linkedin\.com/[^\s"\'\>]+', clean)
        git = re.findall(r'https?://(?:www\.)?github\.com/[^\s"\'\>]+', clean)
        
        name = "Not Found"
        if nlp and nlp.has_pipe("ner"):
            for ent in nlp(clean[:1000]).ents:
                if ent.label_ == "PERSON" and len(ent.text.split()) <= 4:
                    name = ent.text
                    break
        if name == "Not Found" and text.splitlines():
            name = text.splitlines()[0].strip()

        skills = ["PYTHON", "JAVA", "C++", "JAVASCRIPT", "SQL", "GIT", "DOCKER", "AWS", "FLASK", "REACT", "LINUX"]
        found_skills = [s for s in skills if re.search(rf'\b{s}\b', clean.upper())]
        return {
            "Name": name, 
            "Email": email[0] if email else "Not Found", 
            "Phone": phone[0] if phone else "Not Found",
            "LinkedIn": lnk[0] if lnk else "Not Found", 
            "GitHub": git[0] if git else "Not Found", 
            "Skills": found_skills or ["PYTHON", "SQL"]
        }

class ATSEngine:
    def __init__(self, resume, jd):
        self.r_text = re.sub(r'[^a-z0-9 ]', ' ', resume.lower())
        self.jd_text = re.sub(r'[^a-z0-9 ]', ' ', (jd or "Software engineer Python developer").lower())

    def get_tokens(self, text):
        if nlp: 
            return list(set([t.lemma_ for t in nlp(text) if not t.is_stop and len(t.text) > 2]))
        return list(set([w for w in text.split() if len(w) > 2]))

    def analyze(self):
        r_tok, jd_tok = self.get_tokens(self.r_text), self.get_tokens(self.jd_text)
        matched = [w for w in jd_tok if w in r_tok]
        match_pct = (len(matched) / len(jd_tok)) * 100 if jd_tok else 0
        
        try:
            matrix = CountVectorizer().fit_transform([self.r_text, self.jd_text])
            sim_score = cosine_similarity(matrix)[0][1] * 100
        except: 
            sim_score = 0
        
        ats = round((match_pct * 0.6) + (sim_score * 0.4), 2)
        return {"ATS Score": ats, "Matched": matched, "Missing": [w for w in jd_tok if w not in r_tok]}

def evaluate_candidate(raw_text, profile, ats_report):
    lines = raw_text.splitlines()
    edu = [l.strip() for l in lines if any(k in l.lower() for k in ["university", "college", "degree", "bachelor", "master"])][:4]
    proj = [l.strip() for l in lines if any(k in l.lower() for k in ["project", "developed", "system", "built"])][:4]
    
    s_score = min(30, max(5, len(profile["Skills"]) * 3))
    e_score = 12
    for item in [e.lower() for e in edu]:
        if "phd" in item: 
            e_score = 20
            break
        elif any(k in item for k in ["master", "m.tech", "m.s"]): 
            e_score = 18
            break
        elif any(k in item for k in ["bachelor", "b.tech", "b.e"]): 
            e_score = 16
            break
            
    p_score = 15 if len(proj) >= 4 else (12 if len(proj) >= 2 else 10)
    r_score = s_score + e_score + p_score
    overall = round((ats_report["ATS Score"] * 0.6) + (r_score * 0.4), 2)
    
    status = "SELECTED" if overall >= 85 else ("SHORTLISTED" if overall >= 70 else ("MAYBE" if overall >= 55 else "REJECTED"))
    return {
        "Resume Score": r_score, 
        "ATS Score": ats_report["ATS Score"], 
        "Overall Score": overall, 
        "Decision": status, 
        "Education": edu, 
        "Projects": proj
    }

# ==================== PAGE ROUTING SYSTEM ====================

# 1st Page (Home / Welcome Landing Page)
@app.route('/')
def index():
    return render_template('index.html')

# 2nd Page
@app.route('/second')
def second_page():
    return render_template('second_page.html')

# 3rd Page (Dashboard View)
@app.route('/third')
def third_page():
    return render_template('third_page.html')

# 4th Page (Resume Tracking / List Profile View)
@app.route('/fourth')
def fourth_page():
    return render_template('fourth_page.html')

# 5th Page (Verification Pipeline Panel)
@app.route('/fifth')
def fifth_page():
    return render_template('fifth_page.html')

# 6th Page (Core Extraction & Analysis Hub)
@app.route('/sixth', methods=['GET', 'POST'])
def sixth_page():
    if request.method == 'POST':
        if 'resume' not in request.files or request.files['resume'].filename == '':
            flash('Processing Failure: No valid resume file selected.')
            return redirect(request.url)
        try:
            start = datetime.now()
            file = request.files['resume']
            jd_text = request.form.get('job_description', '')
            
            engine = ResumeParserEngine()
            raw_text = engine.extract_text(file)
            profile = engine.parse_profile(raw_text)
            
            ats_report = ATSEngine(raw_text, jd_text).analyze()
            eval_res = evaluate_candidate(raw_text, profile, ats_report)
            duration = f"{(datetime.now() - start).total_seconds():.3f}s"
            
            # --- Thread-Safe Headless Chart Generation ---
            fig = Figure(figsize=(6, 4))
            ax = fig.subplots()
            ax.bar(["Resume", "ATS", "Overall"], [eval_res["Resume Score"], eval_res["ATS Score"], eval_res["Overall Score"]], color=['#6366F1', '#10B981', '#F59E0B'])
            ax.set_ylim(0, 100)
            ax.set_title("Metrics Profile Breakdown")
            
            buf = io.BytesIO()
            fig.savefig(buf, format='png', bbox_inches='tight')
            plot_url = base64.b64encode(buf.getvalue()).decode('utf-8')
            
            # Redirects to Settings/Results Page showing computed values
            return render_template('settings.html', details=profile, evaluation=eval_res, plot_url=plot_url, execution_time=duration)
        except Exception as e:
            logging.error(f"Pipeline Fault: {str(e)}")
            flash(f"System error: {str(e)}")
            return redirect(request.url)
            
    return render_template('sixth_page.html')

# 7th Page (Settings Configuration & Calculation Summary Profile)
@app.route('/settings')
def settings():
    # Pre-populates clean default mock configurations if visited without active form execution
    default_profile = {
        "Name": "John Doe",
        "Email": "john.doe@email.com",
        "Phone": "+1 (555) 019-2834",
        "LinkedIn": "https://linkedin.com/in/johndoe",
        "GitHub": "https://github.com/johndoe",
        "Skills": ["PYTHON", "SQL", "FLASK"]
    }
    return render_template('settings.html', details=default_profile, evaluation=None, plot_url=None, execution_time=None)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
