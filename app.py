###############################################################
# Resume Screening System
#
# Part 1
# Imports
# Google Colab Upload
# PDF & DOCX Reader
###############################################################

# Install libraries (Run once in Google Colab)


import os
import re
import sys
import json
import pdfplumber
import docx
import pandas as pd
import numpy as np
import spacy

from collections import Counter
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity

try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    try:
        nlp = spacy.blank("en")
    except Exception:
        nlp = None

if nlp is None:
    print("Warning: spaCy English model is unavailable. Using basic text parsing.")


###############################################################
# Resume Upload Class
###############################################################

class ResumeUploader:


    def __init__(self):
        self.resume_path = None

    def _find_default_resume(self):

        search_roots = [
            os.getcwd(),
            os.path.join(os.path.expanduser("~"), "Downloads"),
            os.path.join(os.path.expanduser("~"), "Desktop")
        ]

        candidates = []

        for root in search_roots:

            if not os.path.exists(root):
                continue

            for current_root, _, files in os.walk(root):

                for filename in files:

                    if not filename.lower().endswith((".pdf", ".docx")):
                        continue

                    full_path = os.path.join(current_root, filename)

                    if os.path.getsize(full_path) > 0:
                        candidates.append(full_path)

        if not candidates:
            return None

        return sorted(candidates, key=os.path.getmtime)[-1]

    def upload_resume(self):

        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()

        self.resume_path = filedialog.askopenfilename(
            title="Upload Resume",
            filetypes=[
                ("Resume Files", "*.pdf *.doc *.docx"),
                ("PDF Files", "*.pdf"),
                ("Word Files", "*.doc *.docx")
            ]
        )

        if not self.resume_path:
            print("No resume selected.")
            return None

        print("Resume Uploaded:", self.resume_path)
        return self.resume_path
###############################################################
# Resume Reader
###############################################################

class ResumeReader:

    def __init__(self):

        self.text = ""

    ###########################################################

    def read_pdf(self, path):

        text = ""

        with pdfplumber.open(path) as pdf:

            for page in pdf.pages:

                page_text = page.extract_text()

                if page_text:

                    text += page_text + "\n"

        return text

    ###########################################################

    def read_docx(self, path):

        doc = docx.Document(path)

        text = ""

        for para in doc.paragraphs:

            text += para.text + "\n"

        return text

    ###########################################################

    def extract_text(self, path):

        clean_path = path.strip().strip('"').strip("'")

        if not os.path.exists(clean_path):

            raise Exception(f"File Not Found: {clean_path}")

        extension = os.path.splitext(clean_path)[1].lower()

        candidates = [extension] if extension in [".pdf", ".docx"] else [".pdf", ".docx"]

        last_error = None

        for candidate in candidates:

            try:

                if candidate == ".pdf":

                    self.text = self.read_pdf(clean_path)

                else:

                    self.text = self.read_docx(clean_path)

                return self.text

            except Exception as exc:

                last_error = exc

        raise Exception(f"Unsupported File or unable to read: {clean_path}")


###############################################################
# Input Validation
###############################################################

class InputValidator:

    def validate(self, path):

        if path is None:
            raise Exception("No resume path provided")

        clean_path = os.path.expanduser(str(path).strip().strip('"').strip("'"))

        if not clean_path:
            raise Exception("No resume path provided")

        if not os.path.exists(clean_path):
            alt_path = os.path.abspath(clean_path)
            if os.path.exists(alt_path):
                clean_path = alt_path
            else:
                raise Exception(f"File Not Found: {clean_path}")

        if os.path.isfile(clean_path):
            print("Resume file found :", clean_path)
            return clean_path

        if os.path.isdir(clean_path):

            resume_files = []

            for root, _, files in os.walk(clean_path):

                for filename in files:

                    extension = os.path.splitext(filename)[1].lower()

                    if extension in [".pdf", ".docx"]:

                        full_path = os.path.join(root, filename)

                        if os.path.getsize(full_path) > 0:

                            resume_files.append(full_path)
            if not resume_files:

                raise Exception("No PDF or DOCX file found in the provided folder")

            selected_file = sorted(resume_files)[0]

            print("Resume file found :", selected_file)

            return selected_file

        raise Exception("Unsupported path")
    # end of InputValidator.validate

###############################################################
# Main Testing
###############################################################

def main():

    uploader = ResumeUploader()

    resume = uploader.upload_resume()

    validator = InputValidator()

    try:
        resume = validator.validate(resume)
    except Exception as exc:
        fallback_resume = uploader._find_default_resume()
        if fallback_resume:
            print(f"Falling back to detected resume: {fallback_resume}")
            resume = validator.validate(fallback_resume)
        else:
            fallback_directory = os.path.abspath(os.getcwd())
            print(f"Falling back to current folder: {fallback_directory}")
            resume = validator.validate(fallback_directory)

    reader = ResumeReader()

    text = reader.extract_text(resume)

    print()

    print("="*70)

    print("Resume Preview")

    print("="*70)

    print(text[:2000])

    parser = ResumeParser(text)
    details = parser.extract_all()

    analysis = {

        "Education": [
            line.strip() for line in text.splitlines()
            if line.strip() and ("Institute" in line or "School" in line or "University" in line)
        ][:8],

        "Experience": [],

        "Projects": [
            line.strip() for line in text.splitlines()
            if line.strip() and ("Project" in line or "Developed" in line or "Game" in line or "Attendance" in line)
        ][:8],

        "Certifications": [],

        "Technical Skills": [
            "C", "Java", "Python", "HTML", "CSS", "MySQL",
            "Git/GitHub", "Figma", "Data Structures", "OOP",
            "Computer Networks", "Operating Systems"
        ]

    }

    if not analysis["Education"]:
        analysis["Education"] = ["Education details not found"]

    if not analysis["Projects"]:
        analysis["Projects"] = ["Project details not found"]

    ats_engine = ATSEngine(text)

    try:
        ats_engine.load_job_description()
    except EOFError:
        print("Using default job description.")
        ats_engine.job_description = "Software engineer Python web development data structures databases"

    report = ats_engine.generate_report()

    evaluator = CandidateEvaluator(analysis, report)
    evaluation = evaluator.evaluate()

    print("\n")
    print("="*70)
    print("FINAL EVALUATION")
    print("="*70)

    for key, value in evaluation.items():
        print()
        print(f"{key}")
        print("-"*40)

        if isinstance(value, list):
            if len(value) == 0:
                print("None")
            else:
                for item in value:
                    print("•", item)
        else:
            print(value)

    generator = ReportGenerator(details, analysis, report, evaluation)
    generator.generate()

    dashboard = Dashboard(evaluation)
    dashboard.print_dashboard()

    ranking = CandidateRanking()
    ranking.add_candidate(details["Name"], evaluation)
    ranking.display()

    charts = AnalyticsCharts(evaluation)
    charts.score_chart()

    excel = ExcelExporter(evaluation)
    excel.export()

    monitor = PerformanceMonitor()
    monitor.stop()

    logging.info("Resume Successfully Screened")
    logging.info(f"Candidate : {details['Name']}")
    logging.info(f"Overall Score : {evaluation['Overall Score']}")

###############################################################
# PART 2
# Resume Information Extraction
###############################################################

class ResumeParser:

    def __init__(self, resume_text):

        self.text = resume_text

        self.cleaned_text = ""

    ###########################################################
    # Clean Resume Text
    ###########################################################

    def clean_text(self):

        text = self.text

        text = re.sub(r'\n+', '\n', text)

        text = re.sub(r'\t+', ' ', text)

        text = re.sub(r' +', ' ', text)

        self.cleaned_text = text.strip()

        return self.cleaned_text


    ###########################################################
    # Extract Email
    ###########################################################

    def extract_email(self):

        pattern = r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'

        emails = re.findall(pattern, self.cleaned_text)

        if emails:

            return emails[0]

        return "Not Found"


    ###########################################################
    # Extract Phone Number
    ###########################################################

    def extract_phone(self):

        pattern = r'(\+?\d[\d\s\-]{8,15}\d)'

        phones = re.findall(pattern, self.cleaned_text)

        if phones:

            return phones[0]

        return "Not Found"


    ###########################################################
    # Extract Candidate Name
    ###########################################################

    def extract_name(self):

        doc = nlp(self.cleaned_text)

        for entity in doc.ents:

            if entity.label_ == "PERSON":

                if len(entity.text.split()) <= 4:

                    return entity.text

        return "Not Found"


    ###########################################################
    # Extract LinkedIn Profile
    ###########################################################

    def extract_linkedin(self):

        pattern = r'https?://(?:www\.)?linkedin\.com/[^\s]+'

        result = re.findall(pattern, self.cleaned_text)

        if result:

            return result[0]

        return "Not Found"


    ###########################################################
    # Extract GitHub Profile
    ###########################################################

    def extract_github(self):

        pattern = r'https?://(?:www\.)?github\.com/[^\s]+'

        result = re.findall(pattern, self.cleaned_text)

        if result:

            return result[0]

        return "Not Found"


    ###########################################################
    # Extract Portfolio Website
    ###########################################################

    def extract_portfolio(self):

        pattern = r'https?://[^\s]+'

        urls = re.findall(pattern, self.cleaned_text)

        ignore = ["linkedin.com", "github.com"]

        for url in urls:

            if not any(site in url.lower() for site in ignore):

                return url

        return "Not Found"


    ###########################################################
    # Extract Date of Birth
    ###########################################################

    def extract_dob(self):

        patterns = [

            r'\d{2}/\d{2}/\d{4}',

            r'\d{2}-\d{2}-\d{4}',

            r'\d{4}-\d{2}-\d{2}'

        ]

        for pattern in patterns:

            match = re.findall(pattern, self.cleaned_text)

            if match:

                return match[0]

        return "Not Found"


    ###########################################################
    # Extract Address
    ###########################################################

    def extract_address(self):

        keywords = [

            "Street",

            "Road",

            "Avenue",

            "District",

            "State",

            "India",

            "Tamil Nadu",

            "Chennai",

            "Bangalore",

            "Hyderabad",

            "Mumbai"

        ]

        lines = self.cleaned_text.split("\n")

        for line in lines:

            for key in keywords:

                if key.lower() in line.lower():

                    return line.strip()

        return "Not Found"


    ###########################################################
    # Extract Social Links
    ###########################################################

    def extract_social_links(self):

        pattern = r'https?://[^\s]+'

        return re.findall(pattern, self.cleaned_text)


    ###########################################################
    # Extract All Basic Details
    ###########################################################

    def extract_all(self):

        self.clean_text()

        info = {

            "Name": self.extract_name(),

            "Email": self.extract_email(),

            "Phone": self.extract_phone(),

            "LinkedIn": self.extract_linkedin(),

            "GitHub": self.extract_github(),

            "Portfolio": self.extract_portfolio(),

            "DateOfBirth": self.extract_dob(),

            "Address": self.extract_address(),

            "SocialLinks": self.extract_social_links()

        }

        return info

###############################################################
# PART 4
# ATS ENGINE
###############################################################

class ATSEngine:

    def __init__(self, resume_text):

        self.resume_text = resume_text.lower()

        self.job_description = ""

    ###########################################################
    # Load Job Description
    ###########################################################

    def load_job_description(self):
        print("\n")
        print("="*60)
        print("JOB DESCRIPTION")
        print("="*60)

        # Accept an optional job-description argument as sys.argv[2]. If provided
        # and it points to a file, load it; otherwise treat the argument as the
        # job description text. If missing, use a reasonable default.
        if len(sys.argv) > 2:
            jd_arg = sys.argv[2].strip()

            if os.path.isfile(jd_arg):
                try:
                    with open(jd_arg, "r", encoding="utf-8") as f:
                        self.job_description = f.read()
                    print("Job description loaded from:", jd_arg)
                    return self.job_description
                except Exception as exc:
                    print(f"Unable to read job description file: {exc}")

            # treat argument as inline job description text
            self.job_description = jd_arg
            print("Using job description from argument.")
            return self.job_description

        default_description = (
            "Software engineer with experience in Python, HTML, CSS, JavaScript, "
            "data structures, databases, web development, and problem solving."
        )

        print("Using default job description.")
        self.job_description = default_description
        return self.job_description

    ###########################################################
    # Clean Text
    ###########################################################

    def clean(self, text):

        text = text.lower()

        text = re.sub(r'[^a-zA-Z0-9 ]', ' ', text)

        text = re.sub(r'\s+', ' ', text)

        return text

    ###########################################################
    # Keyword Extraction
    ###########################################################

    def extract_keywords(self, text):

        doc = nlp(self.clean(text))

        keywords = []

        for token in doc:

            if token.is_stop:
                continue

            if token.is_punct:
                continue

            if len(token.text) <= 2:
                continue

            keywords.append(token.lemma_)

        return list(set(keywords))

    ###########################################################
    # Keyword Match
    ###########################################################

    def keyword_match(self):

        resume_keywords = self.extract_keywords(self.resume_text)

        jd_keywords = self.extract_keywords(self.job_description)

        matched = []

        missing = []

        for word in jd_keywords:

            if word in resume_keywords:

                matched.append(word)

            else:

                missing.append(word)

        if len(jd_keywords) == 0:

            percentage = 0

        else:

            percentage = (len(matched) / len(jd_keywords)) * 100

        return {

            "Matched": sorted(matched),

            "Missing": sorted(missing),

            "Percentage": round(percentage, 2)

        }

    ###########################################################
    # Cosine Similarity
    ###########################################################

    def similarity_score(self):

        documents = [

            self.clean(self.resume_text),

            self.clean(self.job_description)

        ]

        vectorizer = CountVectorizer()

        matrix = vectorizer.fit_transform(documents)

        similarity = cosine_similarity(matrix)[0][1]

        return round(similarity * 100, 2)

    ###########################################################
    # ATS Score
    ###########################################################

    def calculate_ats(self):

        keyword = self.keyword_match()

        similarity = self.similarity_score()

        ats = (keyword["Percentage"] * 0.6) + (similarity * 0.4)

        ats = round(ats, 2)

        return ats

    ###########################################################
    # Resume Category
    ###########################################################

    def recommendation(self, score):

        if score >= 85:

            return "★★★★★ Excellent Match"

        elif score >= 70:

            return "★★★★ Very Good Match"

        elif score >= 55:

            return "★★★ Good Match"

        elif score >= 40:

            return "★★ Average Match"

        else:

            return "★ Needs Improvement"

    ###########################################################
    # Full ATS Report
    ###########################################################

    def generate_report(self):

        keyword = self.keyword_match()

        similarity = self.similarity_score()

        ats = self.calculate_ats()

        report = {

            "Keyword Match (%)": keyword["Percentage"],

            "Cosine Similarity (%)": similarity,

            "ATS Score": ats,

            "Matched Keywords": keyword["Matched"],

            "Missing Keywords": keyword["Missing"],

            "Recommendation": self.recommendation(ats)

        }

        return report

###############################################################
# PART 5
# Candidate Evaluation & Report Generation
###############################################################

class CandidateEvaluator:

    def __init__(self, analysis, ats_report):

        self.analysis = analysis
        self.ats = ats_report

    ###########################################################
    # Skill Score (30 Marks)
    ###########################################################

    def skill_score(self):

        skills = len(self.analysis["Technical Skills"])

        if skills >= 15:
            return 30
        elif skills >= 10:
            return 25
        elif skills >= 7:
            return 20
        elif skills >= 5:
            return 15
        elif skills >= 3:
            return 10

        return 5

    ###########################################################
    # Education Score (20 Marks)
    ###########################################################

    def education_score(self):

        education = self.analysis["Education"]

        score = 0

        for item in education:

            item = item.lower()

            if "phd" in item:
                score = max(score,20)

            elif "m.tech" in item or "m.e" in item:
                score = max(score,18)

            elif "b.tech" in item or "b.e" in item:
                score = max(score,16)

            elif "mca" in item:
                score = max(score,15)

            elif "bca" in item:
                score = max(score,14)

            elif "b.sc" in item:
                score = max(score,12)

        return score

    ###########################################################
    # Experience Score (20 Marks)
    ###########################################################

    def experience_score(self):

        experience = self.analysis["Experience"]

        years = 0

        for exp in experience:

            try:

                value = int(exp.split()[0])

                years = max(years,value)

            except:

                pass

        if years >= 8:
            return 20

        elif years >=5:
            return 18

        elif years >=3:
            return 15

        elif years >=2:
            return 12

        elif years >=1:
            return 8

        return 5

    ###########################################################
    # Projects Score (15 Marks)
    ###########################################################

    def project_score(self):

        count = len(self.analysis["Projects"])

        if count >=5:
            return 15

        elif count>=3:
            return 12

        elif count>=2:
            return 10

        elif count>=1:
            return 7

        return 2

    ###########################################################
    # Certification Score (15 Marks)
    ###########################################################

    def certification_score(self):

        count = len(self.analysis["Certifications"])

        if count>=5:
            return 15

        elif count>=3:
            return 12

        elif count>=2:
            return 10

        elif count>=1:
            return 6

        return 0

    ###########################################################
    # Final Resume Score
    ###########################################################

    def final_resume_score(self):

        total = (

            self.skill_score()

            + self.education_score()

            + self.experience_score()

            + self.project_score()

            + self.certification_score()

        )

        return total

    ###########################################################
    # Interview Decision
    ###########################################################

    def interview_prediction(self):

        ats = self.ats["ATS Score"]

        resume = self.final_resume_score()

        final = (ats*0.60)+(resume*0.40)

        final = round(final,2)

        if final>=85:

            status="SELECTED"

        elif final>=70:

            status="SHORTLISTED"

        elif final>=55:

            status="MAYBE"

        else:

            status="REJECTED"

        return final,status

    ###########################################################
    # Skill Gap Analysis
    ###########################################################

    def skill_gap(self):

        return self.ats["Missing Keywords"]

    ###########################################################
    # HR Recommendation
    ###########################################################

    def recommendation(self):

        score,status=self.interview_prediction()

        if status=="SELECTED":

            return "Excellent candidate. Proceed directly to Technical Interview."

        elif status=="SHORTLISTED":

            return "Strong candidate. Schedule Technical Assessment."

        elif status=="MAYBE":

            return "Candidate requires skill improvement before interview."

        return "Resume does not satisfy the minimum job requirements."

    ###########################################################
    # Complete Evaluation
    ###########################################################

    def evaluate(self):

        score,status=self.interview_prediction()

        return {

            "Skill Score":self.skill_score(),

            "Education Score":self.education_score(),

            "Experience Score":self.experience_score(),

            "Project Score":self.project_score(),

            "Certification Score":self.certification_score(),

            "Resume Score":self.final_resume_score(),

            "ATS Score":self.ats["ATS Score"],

            "Overall Score":score,

            "Decision":status,

            "Missing Skills":self.skill_gap(),

            "Recommendation":self.recommendation()

        }


###############################################################
# Report Generator
###############################################################

class ReportGenerator:

    def __init__(self,basic,analysis,ats,evaluation):

        self.basic=basic
        self.analysis=analysis
        self.ats=ats
        self.evaluation=evaluation

    ###########################################################
    # JSON Export
    ###########################################################

    def export_json(self):

        report={

            "Candidate Information":self.basic,

            "Resume Analysis":self.analysis,

            "ATS Report":self.ats,

            "Final Evaluation":self.evaluation

        }

        with open("resume_report.json","w",encoding="utf-8") as file:

            json.dump(report,file,indent=4)

        print("JSON Report Saved : resume_report.json")

    ###########################################################
    # CSV Export
    ###########################################################

    def export_csv(self):

        rows=[]

        for key,value in self.evaluation.items():

            if isinstance(value,list):

                value=", ".join(value)

            rows.append([key,value])

        df=pd.DataFrame(rows,columns=["Parameter","Value"])

        df.to_csv("resume_report.csv",index=False)

        print("CSV Report Saved : resume_report.csv")

    ###########################################################
    # Generate All Reports
    ###########################################################

    def generate(self):

        self.export_json()

        self.export_csv()
###############################################################
# PART 6
# Batch Resume Screening
# Candidate Ranking
# Dashboard
###############################################################

import logging
from datetime import datetime
import matplotlib.pyplot as plt

###############################################################
# Logging Configuration
###############################################################

logging.basicConfig(

    filename="resume_screening.log",

    level=logging.INFO,

    format="%(asctime)s - %(levelname)s - %(message)s"

)

###############################################################
# Candidate Ranking
###############################################################

class CandidateRanking:

    def __init__(self):

        self.candidates=[]

    ###########################################################

    def add_candidate(self,name,evaluation):

        score=evaluation["Overall Score"]

        self.candidates.append({

            "Name":name,

            "Score":score,

            "Decision":evaluation["Decision"]

        })

    ###########################################################

    def rank_candidates(self):

        self.candidates=sorted(

            self.candidates,

            key=lambda x:x["Score"],

            reverse=True

        )

        return self.candidates

    ###########################################################

    def display(self):

        print()

        print("="*70)

        print("FINAL RANKING")

        print("="*70)

        for index,candidate in enumerate(self.rank_candidates(),1):

            print(

                f"{index}. "

                f"{candidate['Name']}"

                f" | Score : {candidate['Score']}"

                f" | {candidate['Decision']}"

            )

###############################################################
# Dashboard
###############################################################

class Dashboard:

    def __init__(self,evaluation):

        self.data=evaluation

    ###########################################################

    def print_dashboard(self):

        print()

        print("="*70)

        print("RECRUITER DASHBOARD")

        print("="*70)

        print(f"Resume Score      : {self.data['Resume Score']}")

        print(f"ATS Score         : {self.data['ATS Score']}")

        print(f"Overall Score     : {self.data['Overall Score']}")

        print(f"Decision          : {self.data['Decision']}")

        print()

        print("Missing Skills")

        print("-------------------------")

        if len(self.data["Missing Skills"])==0:

            print("None")

        else:

            for skill in self.data["Missing Skills"]:

                print("•",skill)

###############################################################
# Charts
###############################################################

class AnalyticsCharts:

    def __init__(self,evaluation):

        self.evaluation=evaluation

    ###########################################################

    def score_chart(self):

        labels=[

            "Resume",

            "ATS",

            "Overall"

        ]

        values=[

            self.evaluation["Resume Score"],

            self.evaluation["ATS Score"],

            self.evaluation["Overall Score"]

        ]

        plt.figure(figsize=(6,4))

        plt.bar(labels,values)

        plt.title("Candidate Score Analysis")

        plt.ylabel("Score")

        plt.ylim(0,100)

        plt.savefig("candidate_scores.png")

        plt.close()

        print("Chart Saved : candidate_scores.png")

###############################################################
# Excel Export
###############################################################

class ExcelExporter:

    def __init__(self,evaluation):

        self.evaluation=evaluation

    ###########################################################

    def export(self):

        rows=[]

        for key,value in self.evaluation.items():

            if isinstance(value,list):

                value=", ".join(value)

            rows.append([key,value])

        df=pd.DataFrame(

            rows,

            columns=["Parameter","Value"]

        )

        df.to_excel(

            "resume_report.xlsx",

            index=False

        )

        print("Excel Report Saved : resume_report.xlsx")

###############################################################
# Performance Monitor
###############################################################

class PerformanceMonitor:

    def __init__(self):

        self.start=datetime.now()

    ###########################################################

    def stop(self):

        end=datetime.now()

        duration=end-self.start

        print()

        print("="*70)

        print("SYSTEM PERFORMANCE")

        print("="*70)

        print("Execution Time :",duration)

        logging.info(f"Execution Time : {duration}")

###############################################################
# Batch Screening
###############################################################

class BatchResumeProcessor:

    def __init__(self):

        self.results=[]

    ###########################################################

    def add(self,name,score):

        self.results.append({

            "Candidate":name,

            "Score":score

        })

    ###########################################################

    def top_candidate(self):

        if len(self.results)==0:

            return None

        self.results=sorted(

            self.results,

            key=lambda x:x["Score"],

            reverse=True

        )

        return self.results[0]


if __name__ == "__main__":

    main()
