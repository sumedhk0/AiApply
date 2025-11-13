"""
Resume Generation Module for ATS Optimization

This module uses Claude API to analyze job descriptions and tailor resumes
to be ATS-optimized. It generates professional LaTeX resumes using PyLaTeX.
"""

import os
import re
import json
import shutil
import anthropic
import setup
import subprocess
from datetime import datetime
from pathlib import Path
from pylatex import Document, Section, Subsection, Command, Package
from pylatex.utils import NoEscape, bold, italic
from PyPDF2 import PdfReader


def check_latex_installation():
    """
    Check if pdflatex is installed and available.

    Returns:
        bool: True if pdflatex is available, False otherwise
    """
    return shutil.which('pdflatex') is not None


def print_latex_installation_instructions():
    """Print instructions for installing LaTeX."""
    print("\n" + "="*70)
    print("WARNING: LaTeX (pdflatex) is not installed on your system")
    print("="*70)
    print("\nTo generate PDF resumes, please install MiKTeX:")
    print("\n   1. Download from: https://miktex.org/download")
    print("   2. Run the installer (use default settings)")
    print("   3. Restart your terminal/IDE")
    print("   4. Run this script again")
    print("\nUntil then, LaTeX (.tex) files will be generated instead.")
    print("="*70 + "\n")


class ATSResumeGenerator:
    """
    Generates ATS-optimized resumes tailored to specific job descriptions.
    """

    def __init__(self, original_resume_path, warn_latex=True):
        """
        Initialize the resume generator.

        Args:
            original_resume_path: Path to the user's original PDF resume
            warn_latex: Whether to warn about missing LaTeX installation
        """
        self.original_resume_path = original_resume_path
        self.claude_api_key = setup.API_KEY

        if not self.claude_api_key or not self.claude_api_key.startswith('sk-ant-'):
            raise ValueError("Invalid API key in setup.py")

        self.claude_client = anthropic.Anthropic(api_key=self.claude_api_key)

        # Create directories for generated resumes
        self.generated_resumes_dir = os.path.join(os.path.dirname(__file__), "generated_resumes")
        os.makedirs(self.generated_resumes_dir, exist_ok=True)

        # Check LaTeX installation
        self.has_latex = check_latex_installation()
        if not self.has_latex and warn_latex:
            print_latex_installation_instructions()

    def extract_text_from_pdf(self, pdf_path):
        """
        Extract text content from a PDF file.

        Args:
            pdf_path: Path to PDF file

        Returns:
            str: Extracted text content
        """
        try:
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text.strip()
        except Exception as e:
            print(f"Error extracting PDF text: {str(e)}")
            return ""

    def analyze_and_tailor_resume(self, job_description, company_name, job_title):
        """
        Use Claude API to analyze job description and tailor resume content.

        Args:
            job_description: Full job description text
            company_name: Name of the company
            job_title: Title of the job position

        Returns:
            dict: Tailored resume data with structured sections
        """
        # Extract original resume text
        original_resume_text = self.extract_text_from_pdf(self.original_resume_path)

        if not original_resume_text:
            raise ValueError("Could not extract text from original resume")

        # Create prompt for Claude
        prompt = f"""You are an expert resume writer and ATS optimization specialist. Your task is to tailor a resume for a specific job application.

ORIGINAL RESUME:
{original_resume_text}

JOB DETAILS:
Company: {company_name}
Position: {job_title}

JOB DESCRIPTION:
{job_description}

TASK:
Analyze the job description and tailor the resume to be ATS-optimized for this specific position. Follow these guidelines:

1. **NO PROFESSIONAL SUMMARY**: Do not include a professional summary section. Incorporate keywords naturally into experience and project bullet points instead.
2. **Keyword Integration**: Identify key skills, technologies, and requirements from the job description and weave them naturally into bullet points
3. **Strategic Bolding**: Mark items to be bolded by wrapping them in **bold markers**. Bold the following:
   - Technologies and tools (e.g., **Python**, **React**, **AWS**)
   - Programming languages from tech stack
   - Frameworks and libraries
   - Key performance indicators and metrics (e.g., **50% improvement**, **$2M revenue**, **10,000 users**)
   - Important achievements that should pop to hiring managers
   - Quantifiable results and impact numbers
4. **Relevance**: Emphasize experiences and skills most relevant to this position
5. **ATS-Friendly**: Use standard section headings and formatting
6. **Achievements**: Quantify achievements where possible
7. **Keep it truthful**: Only include information that was in the original resume - do not fabricate experience

Return ONLY a JSON object with the following structure (no markdown, no code blocks):

{{
  "name": "Full Name",
  "contact": {{
    "email": "email@example.com",
    "phone": "phone number",
    "linkedin": "LinkedIn URL (optional)",
    "github": "GitHub URL (optional)",
    "location": "City, State (optional)"
  }},
  "education": [
    {{
      "degree": "Degree Name",
      "institution": "University Name",
      "graduation": "Graduation Date",
      "gpa": "GPA (if mentioned)",
      "relevant_coursework": "Relevant courses (optional)"
    }}
  ],
  "experience": [
    {{
      "title": "Job Title",
      "company": "Company Name",
      "duration": "Start Date - End Date",
      "bullets": [
        "Achievement-focused bullet with **bolded tech** and **bolded metrics**",
        "Another achievement with **important keywords bolded**",
        "Quantified result with **key numbers** highlighted"
      ]
    }}
  ],
  "skills": {{
    "technical": ["Skill1", "Skill2", "Skill3"],
    "tools": ["Tool1", "Tool2", "Tool3"],
    "programming_languages": ["ProgrammingLanguage1", "ProgrammingLanguage2"]
  }},
  "projects": [
    {{
      "name": "Project Name",
      "description": "Brief description",
      "technologies": "Technologies used",
      "bullets": [
        "Key achievement with **bolded technologies** and **metrics**",
        "Feature description with **important results bolded**"
      ]
    }}
  ],
  "certifications": [
    "Certification Name 1",
    "Certification Name 2"
  ],
  "keywords_added": ["keyword1", "keyword2", "keyword3"]
}}

IMPORTANT: Wrap items to be bolded with **double asterisks** in the bullet points. Include all relevant sections that exist in the original resume. If a section doesn't exist or isn't relevant, include it as an empty array or omit it. Focus on making this resume highly tailored to the {job_title} position at {company_name}."""

        try:
            response = self.claude_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse response
            response_text = response.content[0].text.strip()

            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            tailored_data = json.loads(response_text)

            print(f"[SUCCESS] Successfully tailored resume for {job_title} at {company_name}")
            print(f"[INFO] Added ATS keywords: {', '.join(tailored_data.get('keywords_added', []))}")

            return tailored_data

        except Exception as e:
            print(f"[ERROR] Error tailoring resume with Claude: {str(e)}")
            raise

    def escape_latex(self, text):
        """
        Escape special LaTeX characters in text.

        Args:
            text: Text to escape

        Returns:
            str: Escaped text safe for LaTeX
        """
        if not text:
            return ""

        # Dictionary of LaTeX special characters and their escaped versions
        replacements = {
            '&': r'\&',
            '%': r'\%',
            '$': r'\$',
            '#': r'\#',
            '_': r'\_',
            '{': r'\{',
            '}': r'\}',
            '~': r'\textasciitilde{}',
            '^': r'\textasciicircum{}',
        }

        for char, replacement in replacements.items():
            text = text.replace(char, replacement)

        return text

    def process_bold_text(self, text):
        """
        Process text with **bold markers** and convert to LaTeX bold formatting.
        Also escapes LaTeX special characters.

        Args:
            text: Text that may contain **bold** markers

        Returns:
            str: LaTeX-formatted text with \textbf{} for bolded sections
        """
        if not text:
            return ""

        # Split by ** markers
        parts = text.split('**')
        result = []

        for i, part in enumerate(parts):
            if i % 2 == 0:
                # Regular text - escape it
                result.append(self.escape_latex(part))
            else:
                # Text that should be bolded - escape then wrap in \textbf{}
                result.append(r'\textbf{' + self.escape_latex(part) + r'}')

        return ''.join(result)

    def generate_latex_resume(self, resume_data, company_name, job_title):
        """
        Generate a professional LaTeX resume from tailored data using custom template.

        Args:
            resume_data: Tailored resume data from Claude
            company_name: Company name for filename
            job_title: Job title for filename

        Returns:
            str: Path to generated PDF resume
        """
        # Extract data
        name = self.escape_latex(resume_data.get('name', 'Your Name'))
        contact = resume_data.get('contact', {})

        # Build contact line
        contact_parts = []
        if contact.get('email'):
            contact_parts.append(r'\href{mailto:' + contact['email'] + r'}{' + contact['email'] + r'}')
        if contact.get('phone'):
            contact_parts.append(contact['phone'])
        if contact.get('linkedin'):
            linkedin_url = contact['linkedin']
            if not linkedin_url.startswith('http'):
                linkedin_url = 'https://' + linkedin_url
            contact_parts.append(r'\href{' + linkedin_url + r'}{' + contact['linkedin'].replace('https://', '').replace('http://', '') + r'}')
        if contact.get('github'):
            github_url = contact['github']
            if not github_url.startswith('http'):
                github_url = 'https://' + github_url
            contact_parts.append(r'\href{' + github_url + r'}{' + contact['github'].replace('https://', '').replace('http://', '') + r'}')
        if contact.get('location'):
            contact_parts.append(contact['location'])

        contact_line = ' $|$ '.join(contact_parts)

        # Start building LaTeX document
        latex_content = r'''\documentclass[a4paper,9pt]{extarticle}

\usepackage[utf8]{inputenc}
\usepackage{geometry}
\geometry{a4paper, margin=0.5in}
\usepackage{titlesec}
\usepackage{enumitem}
\usepackage{hyperref}
\setlist{noitemsep,leftmargin=*}
\titleformat{\section}{\Large\bfseries}{\thesection}{1em}{}[\titlerule]
\titlespacing*{\section}{0pt}{0.5em}{0.5em}
\pagestyle{empty}

\begin{document}

\begin{center}
    \textbf{\Large ''' + name + r'''}\\[2pt]
    ''' + contact_line + r'''
\end{center}

'''

        # Add Education (Professional Summary section removed)
        if resume_data.get('education'):
            latex_content += r'''\section*{EDUCATION}
'''
            for edu in resume_data['education']:
                latex_content += r'''\noindent
\textbf{''' + self.escape_latex(edu.get('institution', '')) + r'''} \hfill \textbf{''' + self.escape_latex(edu.get('graduation', '')) + r'''}\\
''' + self.escape_latex(edu.get('degree', '')) + r'''
'''
                if edu.get('gpa') or edu.get('relevant_coursework'):
                    latex_content += r'''\begin{itemize}
'''
                    if edu.get('gpa'):
                        latex_content += r'''    \item \textbf{GPA: }''' + self.escape_latex(edu['gpa']) + r'''
'''
                    if edu.get('relevant_coursework'):
                        latex_content += r'''    \item \textbf{Relevant Coursework: }''' + self.escape_latex(edu['relevant_coursework']) + r'''
'''
                    latex_content += r'''\end{itemize}
'''
                latex_content += '\n'

        # Add Experience
        if resume_data.get('experience'):
            latex_content += r'''\section*{EXPERIENCE}
'''
            for exp in resume_data['experience']:
                latex_content += r'''\noindent
\textbf{''' + self.escape_latex(exp.get('company', '')) + r'''} \hfill ''' + self.escape_latex(exp.get('location', '')) + r'''\\
\textit{''' + self.escape_latex(exp.get('title', '')) + r'''} \hfill ''' + self.escape_latex(exp.get('duration', '')) + r'''
'''
                if exp.get('bullets'):
                    latex_content += r'''\begin{itemize}
'''
                    for bullet in exp['bullets']:
                        latex_content += r'''    \item ''' + self.process_bold_text(bullet) + r'''
'''
                    latex_content += r'''\end{itemize}
'''
                latex_content += '\n'

        # Add Projects
        if resume_data.get('projects'):
            latex_content += r'''\section*{PROJECTS}
'''
            for proj in resume_data['projects']:
                location = self.escape_latex(proj.get('location', ''))
                latex_content += r'''\noindent
\textbf{''' + self.escape_latex(proj.get('name', '')) + r'''} \hfill ''' + location + r'''\\
'''
                if proj.get('technologies') or proj.get('duration'):
                    latex_content += r'''\textit{''' + self.escape_latex(proj.get('technologies', '')) + r'''} \hfill ''' + self.escape_latex(proj.get('duration', '')) + r'''
'''
                if proj.get('description'):
                    latex_content += self.escape_latex(proj['description']) + r'''
'''
                if proj.get('bullets'):
                    latex_content += r'''\begin{itemize}
'''
                    for bullet in proj['bullets']:
                        latex_content += r'''    \item ''' + self.process_bold_text(bullet) + r'''
'''
                    latex_content += r'''\end{itemize}
'''
                latex_content += '\n'

        # Add Skills
        if resume_data.get('skills'):
            latex_content += r'''\section*{SKILLS}
\begin{itemize}
'''
            skills = resume_data['skills']
            if skills.get('technical'):
                latex_content += r'''    \item \textbf{Technical: }''' + ', '.join([self.escape_latex(s) for s in skills['technical']]) + r'''
'''
            if skills.get('tools'):
                latex_content += r'''    \item \textbf{Tools \& Frameworks: }''' + ', '.join([self.escape_latex(s) for s in skills['tools']]) + r'''
'''
            if skills.get('programming_languages'):
                latex_content += r'''    \item \textbf{Programming Languages: }''' + ', '.join([self.escape_latex(s) for s in skills['programming_languages']]) + r'''
'''
            latex_content += r'''\end{itemize}

'''

        # Add Certifications
        if resume_data.get('certifications'):
            latex_content += r'''\section*{CERTIFICATIONS}
\begin{itemize}
'''
            for cert in resume_data['certifications']:
                latex_content += r'''    \item ''' + self.escape_latex(cert) + r'''
'''
            latex_content += r'''\end{itemize}

'''

        # End document
        latex_content += r'''\end{document}
'''

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_company = re.sub(r'[^\w\s-]', '', company_name).strip().replace(' ', '_')
        safe_title = re.sub(r'[^\w\s-]', '', job_title).strip().replace(' ', '_')
        filename = f"Resume_{safe_company}_{safe_title}_{timestamp}"

        # Save to generated_resumes folder
        local_path = os.path.join(self.generated_resumes_dir, filename)
        tex_file = f"{local_path}.tex"

        # Write LaTeX file
        try:
            with open(tex_file, 'w', encoding='utf-8') as f:
                f.write(latex_content)
            print(f"[SUCCESS] LaTeX source saved: {tex_file}")

            # If LaTeX is not installed, return .tex file
            if not self.has_latex:
                print(f"[INFO] LaTeX file saved at: {tex_file}")
                print("   You can manually compile it with: pdflatex " + os.path.basename(tex_file))
                return tex_file

            # Compile to PDF using pdflatex
            print("[INFO] Compiling LaTeX to PDF...")

            # Run pdflatex twice for proper formatting (references, etc.)
            for i in range(2):
                result = subprocess.run(
                    ['pdflatex', '-interaction=nonstopmode', '-output-directory', self.generated_resumes_dir, os.path.basename(tex_file)],
                    capture_output=True,
                    text=True,
                    cwd=self.generated_resumes_dir,
                    timeout=30
                )

            pdf_path = f"{local_path}.pdf"
            if os.path.exists(pdf_path):
                # Clean up auxiliary files
                for ext in ['.aux', '.log', '.out', '.tex']:
                    aux_file = f"{local_path}{ext}"
                    if os.path.exists(aux_file):
                        try:
                            os.remove(aux_file)
                        except:
                            pass  # Ignore if file is locked or doesn't exist

                print(f"[SUCCESS] Generated resume PDF: {pdf_path}")
                return pdf_path
            else:
                print(f"[ERROR] Error generating PDF. LaTeX compilation failed.")
                print(f"[INFO] Check the log file for details: {local_path}.log")
                if result.stderr:
                    print(f"LaTeX Error: {result.stderr[:500]}")
                return tex_file

        except subprocess.TimeoutExpired:
            print(f"[ERROR] LaTeX compilation timed out after 30 seconds.")
            print(f"[INFO] LaTeX source saved: {tex_file}")
            return tex_file
        except Exception as e:
            print(f"[ERROR] Error generating PDF: {str(e)}")
            print("[INFO] Make sure MiKTeX is installed: https://miktex.org/download")
            print(f"[INFO] LaTeX source saved: {tex_file}")
            return tex_file

    def save_to_downloads(self, resume_path):
        """
        Copy the generated resume to the user's Downloads folder.

        Args:
            resume_path: Path to the generated resume file

        Returns:
            str: Path to the file in Downloads folder
        """
        try:
            # Get user's Downloads folder
            downloads_folder = str(Path.home() / "Downloads")

            # Get filename
            filename = os.path.basename(resume_path)

            # Copy to Downloads
            dest_path = os.path.join(downloads_folder, filename)
            shutil.copy2(resume_path, dest_path)

            print(f"[SUCCESS] Copied resume to Downloads: {dest_path}")
            return dest_path

        except Exception as e:
            print(f"[WARNING] Error copying to Downloads folder: {str(e)}")
            return None

    def generate_tailored_resume(self, job_description, company_name, job_title):
        """
        Main method to generate a complete ATS-optimized tailored resume.

        Args:
            job_description: Full job description text
            company_name: Name of the company
            job_title: Title of the job position

        Returns:
            dict: {
                'local_path': Path to resume in generated_resumes folder,
                'downloads_path': Path to resume in Downloads folder,
                'keywords_added': List of ATS keywords added
            }
        """
        print(f"\n{'='*60}")
        print(f"Generating ATS-Optimized Resume")
        print(f"Position: {job_title} at {company_name}")
        print(f"{'='*60}\n")

        # Step 1: Analyze and tailor resume content
        print("[STEP 1] Analyzing job description and tailoring resume...")
        tailored_data = self.analyze_and_tailor_resume(job_description, company_name, job_title)

        # Step 2: Generate LaTeX resume
        print("[STEP 2] Generating professional LaTeX resume...")
        local_path = self.generate_latex_resume(tailored_data, company_name, job_title)

        # Step 3: Copy to Downloads folder
        print("[STEP 3] Saving to Downloads folder...")
        downloads_path = self.save_to_downloads(local_path)

        print(f"\n{'='*60}")
        print(f"[SUCCESS] Resume Generation Complete!")
        print(f"{'='*60}\n")

        return {
            'local_path': local_path,
            'downloads_path': downloads_path,
            'keywords_added': tailored_data.get('keywords_added', [])
        }


def main(original_resume_path, job_description, company_name, job_title):
    """
    Main entry point for resume generation.

    Args:
        original_resume_path: Path to user's original resume PDF
        job_description: Full job description text
        company_name: Name of the company
        job_title: Job title

    Returns:
        dict: Result with paths to generated resume
    """
    generator = ATSResumeGenerator(original_resume_path)
    return generator.generate_tailored_resume(job_description, company_name, job_title)


if __name__ == "__main__":
    # Test the resume generator
    print("Resume Generator Test")
    print("="*60)

    # Example usage
    test_resume_path = "user_resumes/user_1_1761611176088_Sumedh_Kothari_Resume.pdf"
    test_job_desc = """
    We are seeking a Software Engineer Intern to join our team.
    Responsibilities include developing web applications using Python, Flask,
    and React. Experience with REST APIs, databases, and version control is required.
    """
    test_company = "Tech Company Inc"
    test_title = "Software Engineer Intern"

    if os.path.exists(test_resume_path):
        result = main(test_resume_path, test_job_desc, test_company, test_title)
        print(f"\nResult: {json.dumps(result, indent=2)}")
    else:
        print(f"Test resume not found at: {test_resume_path}")
