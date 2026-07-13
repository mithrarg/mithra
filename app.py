import os
import re
import sys
import json
import logging
import io
import base64
from datetime import datetime

import pdfplumber
import docx
import pandas as pd
import numpy as np
import spacy
import matplotlib

# Force non-interactive matplotlib backend for headless server deployment on Render
matplotlib.use('Agg')
from matplotlib.figure import Figure  # Use Object-Oriented approach for thread safety

from flask import Flask, render_template, request, redirect, url_for, flash
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Initialize Flask App Config
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "prod-screening-system-token-9988")

# Setup System Infrastructure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Robust spaCy NLP Pipeline Model Initialization
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    try:
        nlp = spacy.blank("en")
    except Exception:
        nlp = None

if nlp is None:
    logging.warning("System Notice: spaCy pipeline fallback in effect. Using basic token parsing.")


# ===============================================================
# PART 1: IN-MEMORY EXTRACTION & INPUT INFRASTRUCTURE
# ===============================================================

class PerformanceMonitor:
    """Tracks atomic compute durations within standard request lifetimes."""
    def __init__(self):
        self.start = datetime.now()

    def get_duration(self):
        end = datetime.now()
        duration_delta = end - self.start
        # Return cleanly formatted total seconds string for the UI view
        return f"{duration_delta.total_seconds():.3f}s"


class ResumeReader:
    """Parses structural document content from ephemeral input streams."""
    def read_pdf(self, file_stream):
        text = ""
        with pdfplumber.open(file_stream) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text

    def read_docx(self, file_stream):
        doc = docx.Document(file_stream)
        text = ""
        for para in doc.paragraphs:
            text += para.text + "\n"
        return text

    def extract_text(self, file_storage):
        filename = file_storage.filename.lower()
        file_stream = io.BytesIO(file_storage.read())
        
        if filename.endswith(".pdf"):
            return self.read_pdf(file_stream)
        elif filename.endswith((".docx", ".doc")):
            return self.read_docx(file_stream)
        else:
            raise ValueError("Unsupported file extension. Please upload a PDF or DOCX format document.")


# ===============================================================
# PART 2: LEXICAL ENGINE, ATS ANALYSIS & CANDIDATE METRICS
# ===============================================================

class ResumeParser:
    """Handles profile regex matching and entities tracking."""
    def __init__(self, resume_text):
        self.text = resume_text
        self.cleaned_text = ""

    def clean_text(self):
        text = self.text
        text = re.sub(r'\n+', '\n', text)
        text = re.sub(r'\t+', ' ', text)
        text = re.sub(r' +', ' ', text)
        self.cleaned_text = text.strip()
        return self.cleaned_text

    def extract_email(self):
        pattern = r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
        emails = re.findall(pattern, self.cleaned_text)
        return emails[0] if emails else "Not Found"

    def extract_phone(self):
        pattern = r'(\+?\d[\d\s\-]{8,15}\d)'
        phones = re.findall(pattern, self.cleaned_text)
        return phones[0] if phones else "Not Found"

    def extract_name(self):
        if nlp and nlp.has_pipe("ner"):
            doc = nlp(self.cleaned_text)
            for entity in doc.ents:
                if entity.label_ == "PERSON" and len(entity.text.split()) <= 4:
                    return entity.text
        return "Not Found"

    def extract_linkedin(self):
        pattern = r'https?://(?:www\.)?linkedin\.com/in/[^\s]+|https?://(?:www\.)?linkedin\.com/[^\s]+'
        result = re.findall(pattern, self.cleaned_text)
        return result[0] if result else "Not Found"

    def extract_github(self):
        pattern = r'https?://(?:www\.)?github\.com/[^\s]+'
        result = re.findall(pattern, self.cleaned_text)
        return result[0] if result else "Not Found"

    def extract_all(self):
        self.clean_text()
        return {
            "Name": self.extract_name(),
            "Email": self.extract_email(),
            "Phone": self.extract_phone(),
            "LinkedIn": self.extract_linkedin(),
            "GitHub": self.extract_github()
        }


class ATSEngine:
    """Measures syntactic text overlays using vector cosine weights."""
    def __init__(self, resume_text, job_description):
        self.resume_text = resume_text.lower()
        self.job_description = job_description.strip() if job_description.strip() else "Software engineer Python developer"

    def clean(self, text):
        text = text.lower()
        text = re.sub(r'[^a-zA-Z0-9 ]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text

    def extract_keywords(self, text):
        if nlp:
            doc = nlp(self.clean(text))
            keywords = [token.lemma_ for token in doc if not token.is_stop and not token.is_punct and len(token.text) > 2]
            return list(set(keywords))
        return list(set(self.clean(text).split()))

    def keyword_match(self):
        resume_keywords = self.extract_keywords(self.resume_text)
        jd_keywords = self.extract_keywords(self.job_description)
        matched = [word for word in jd_keywords if word in resume_keywords]
        missing = [word for word in jd_keywords if word not in resume_keywords]
        percentage = (len(matched) / len(jd_keywords)) * 100 if jd_keywords else 0
        return {"Matched": sorted(matched), "Missing": sorted(missing), "Percentage": round(percentage, 2)}

    def similarity_score(self):
        documents = [self.clean(self.resume_text), self.clean(self.job_description)]
        vectorizer = CountVectorizer()
        matrix = vectorizer.fit_transform(documents)
        similarity = cosine_similarity(matrix)[0][1]
        return round(similarity * 100, 2)

    def calculate_ats(self):
        keyword = self.keyword_match()
        similarity = self.similarity_score()
        return round((keyword["Percentage"] * 0.6) + (similarity * 0.4), 2)

    def generate_report(self):
        keyword = self.keyword_match()
        similarity = self.similarity_score()
        ats = self.calculate_ats()
        return {
            "Keyword Match (%)": keyword["Percentage"],
            "Cosine Similarity (%)": similarity,
            "ATS Score": ats,
            "Matched Keywords": keyword["Matched"],
            "Missing Keywords": keyword["Missing"]
        }


class CandidateEvaluator:
    """Generates decision matrices using weighted profiling calculations."""
    def __init__(self, analysis, ats_report):
        self.analysis = analysis
        self.ats = ats_report

    def skill_score(self):
        skills = len(self.analysis.get("Technical Skills", []))
        if skills >= 15: return 30
        elif skills >= 10: return 25
        elif skills >= 7: return 20
        elif skills >= 5: return 15
        return 5

    def education_score(self):
        education = self.analysis.get("Education", [])
        score = 0
        for item in education:
            item = item.lower()
            if "phd" in item: score = max(score, 20)
            elif "m.tech" in item or "m.e" in item or "master" in item: score = max(score, 18)
            elif "b.tech" in item or "b.e" in item or "bachelor" in item: score = max(score, 16)
        return score if score > 0 else 12

    def project_score(self):
        count = len(self.analysis.get("Projects", []))
        if count >= 5: return 15
        elif count >= 3: return 12
        return 10

    def evaluate(self):
        resume_score = self.skill_score() + self.education_score() + self.project_score()
        ats_score = self.ats["ATS Score"]
        overall = round((ats_score * 0.60) + (resume_score * 0.40), 2)
        
        if overall >= 85: status = "SELECTED"
        elif overall >= 70: status = "SHORTLISTED"
        elif overall >= 55: status = "MAYBE"
        else: status = "REJECTED"

        return {
            "Resume Score": resume_score,
            "ATS Score": ats_score,
            "Overall Score": overall,
            "Decision": status,
            "Missing Skills": self.ats["Missing Keywords"]
        }


# ===============================================================
# WEB APPLICATION CONTROLLER ARCHITECTURE
# ===============================================================

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'resume' not in request.files:
            flash('Processing Failure: No upload wrapper element detected.')
            return redirect(request.url)
            
        file = request.files['resume']
        jd_text = request.form.get('job_description', '')

        if file.filename == '':
            flash('Processing Failure: Target filename validation boundary failed.')
            return redirect(request.url)

        try:
            # Initialize compute tracking monitoring metrics
            monitor = PerformanceMonitor()
            
            # Phase 1: Stream extraction logic execution
            reader = ResumeReader()
            raw_text = reader.extract_text(file)
            
            # Phase 2: Lexical profile analysis mapping
            parser = ResumeParser(raw_text)
            details = parser.extract_all()
            
            # Fallback data dictionary metrics mapping
            analysis = {
                "Education": [line.strip() for line in raw_text.splitlines() if any(k in line for k in ["Institute", "School", "University", "College"])][:4],
                "Projects": [line.strip() for line in raw_text.splitlines() if any(k in line for k in ["Project", "Developed", "System", "Application"])][:4],
                "Technical Skills": ["C", "Java", "Python", "HTML", "CSS", "SQL", "Git", "Data Structures"]
            }
            
            # Phase 3: Text score matching algorithms execution
            ats_engine = ATSEngine(raw_text, jd_text)
            report = ats_engine.generate_report()
            
            # Phase 4: Final candidate decision calculation
            evaluator = CandidateEvaluator(analysis, report)
            evaluation = evaluator.evaluate()
            
            # Capture total computational latency duration
            duration_str = monitor.get_duration()
            logging.info(f"Screening Run Completed successfully in {duration_str}")

            # THREAD-SAFE FIX: Create isolated standalone Figure instance instead of mutating global plt
            fig = Figure(figsize=(5, 3.5))
            ax = fig.subplots()
            
            labels = ["Resume Base", "ATS Match", "Composite"]
            values = [evaluation["Resume Score"], evaluation["ATS Score"], evaluation["Overall Score"]]
            
            ax.bar(labels, values, color=['#6366F1', '#10B981', '#F59E0B'])
            ax.set_ylim(0, 100)
            ax.set_title("Metrics Breakdown Vector", fontsize=10)
            
            # Save out from target buffer stream
            img_buf = io.BytesIO()
            fig.savefig(img_buf, format='png', bbox_inches='tight')
            img_buf.seek(0)
            plot_url = base64.b64encode(img_buf.getvalue()).decode('utf-8')

            return render_template('results.html', details=details, evaluation=evaluation, plot_url=plot_url, execution_time=duration_str)

        except Exception as e:
            logging.error(f"Processing Pipeline Fault: {str(e)}")
            flash(f"System processing error occurred: {str(e)}")
            return redirect(request.url)

    return render_template('index.html')


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
