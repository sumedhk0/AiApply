"""
Cover Letter Generation Module for ATS Optimization

This module uses OpenRouter API (MiMo v2 Flash) to analyze job descriptions
and generate tailored cover letters as professional LaTeX PDFs.
"""

import os
import re
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from PyPDF2 import PdfReader
from llm_client import get_client


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
    print("\nTo generate PDF cover letters, please install MiKTeX:")
    print("\n   1. Download from: https://miktex.org/download")
    print("   2. Run the installer (use default settings)")
    print("   3. Restart your terminal/IDE")
    print("   4. Run this script again")
    print("\nUntil then, LaTeX (.tex) files will be generated instead.")
    print("="*70 + "\n")


class ATSCoverLetterGenerator:
    """
    Generates ATS-optimized cover letters tailored to specific job descriptions.
    """

    def __init__(self, resume_text, candidate_name, candidate_email, warn_latex=True):
        """
        Initialize the cover letter generator.

        Args:
            resume_text: Text content from the user's resume
            candidate_name: Full name of the candidate
            candidate_email: Email address of the candidate
            warn_latex: Whether to warn about missing LaTeX installation
        """
        self.resume_text = resume_text
        self.candidate_name = candidate_name
        self.candidate_email = candidate_email
        self.llm_client = get_client()

        # Create directories for generated cover letters
        self.generated_letters_dir = os.path.join(os.path.dirname(__file__), "generated_cover_letters")
        os.makedirs(self.generated_letters_dir, exist_ok=True)

        # Check LaTeX installation
        self.has_latex = check_latex_installation()
        if not self.has_latex and warn_latex:
            print_latex_installation_instructions()

    def generate_cover_letter_content(self, job_description, company_name, job_title):
        """
        Use Claude API to generate cover letter content.

        Args:
            job_description: Full job description text
            company_name: Name of the company
            job_title: Title of the job position

        Returns:
            dict: Cover letter data with structured paragraphs
        """
        # Create prompt for Claude
        prompt = f"""You are an expert cover letter writer. Generate a professional, compelling cover letter for this job application.

RESUME CONTENT:
{self.resume_text}

COMPANY: {company_name}
POSITION: {job_title}

JOB DESCRIPTION:
{job_description}

GUIDELINES:
1. 3-4 paragraphs, ~250-350 words total
2. Opening: Express enthusiasm for the specific role and company
3. Body (1-2 paragraphs): Highlight 2-3 relevant experiences from resume that match job requirements
4. Closing: Express interest in discussing the opportunity, thank them
5. Professional but authentic tone - avoid clichés
6. Incorporate keywords from job description naturally
7. Stay truthful to resume content - DO NOT fabricate experience
8. Focus on what you can contribute, not just what you want to learn
9. Be specific - mention actual projects, technologies, or achievements from the resume
10. DO NOT FABRICATE ANY INFORMATION, STAY TRUTHFUL TO THE RESUME. This includes information such as major, degree, experience, skills, projects, etc.

Return ONLY a JSON object with the following structure (no markdown, no code blocks):

{{
  "opening_paragraph": "Professional opening paragraph expressing enthusiasm...",
  "body_paragraph_1": "First body paragraph highlighting relevant experience...",
  "body_paragraph_2": "Second body paragraph with additional relevant experience (optional, can be empty string if not needed)...",
  "closing_paragraph": "Professional closing paragraph...",
  "keywords_incorporated": ["keyword1", "keyword2", "keyword3"]
}}

IMPORTANT: Each paragraph should be a complete, grammatically correct paragraph. Do not use placeholder text."""

        try:
            response_text = self.llm_client.create_message(prompt, max_tokens=2000)
            response_text = response_text.strip()

            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            letter_data = json.loads(response_text)

            print(f"[SUCCESS] Successfully generated cover letter content for {job_title} at {company_name}")
            print(f"[INFO] Incorporated keywords: {', '.join(letter_data.get('keywords_incorporated', []))}")

            return letter_data

        except Exception as e:
            print(f"[ERROR] Error generating cover letter with Claude: {str(e)}")
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

    def generate_latex_cover_letter(self, letter_data, company_name, job_title):
        """
        Generate a professional LaTeX cover letter from content data.

        Args:
            letter_data: Cover letter data from Claude
            company_name: Company name for filename
            job_title: Job title for filename

        Returns:
            str: Path to generated PDF cover letter
        """
        # Extract data
        opening = self.escape_latex(letter_data.get('opening_paragraph', ''))
        body_1 = self.escape_latex(letter_data.get('body_paragraph_1', ''))
        body_2 = self.escape_latex(letter_data.get('body_paragraph_2', ''))
        closing = self.escape_latex(letter_data.get('closing_paragraph', ''))

        # Build LaTeX document - professional business letter
        latex_content = r'''\documentclass[11pt]{letter}
\usepackage[utf8]{inputenc}
\usepackage{geometry}
\geometry{margin=1in}
\usepackage{hyperref}

\signature{}
\address{''' + self.escape_latex(self.candidate_email) + r'''}

\begin{document}

\begin{letter}{''' + self.escape_latex(company_name) + r'''\\
Hiring Team}

\opening{Dear Hiring Manager,}

''' + opening + r'''

''' + body_1 + r'''

'''
        # Add second body paragraph if provided
        if body_2.strip():
            latex_content += body_2 + r'''

'''

        latex_content += closing + r'''

\closing{Sincerely,\\
Sumedh Kothari}

\end{letter}
\end{document}
'''

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_company = re.sub(r'[^\w\s-]', '', company_name).strip().replace(' ', '_')
        safe_title = re.sub(r'[^\w\s-]', '', job_title).strip().replace(' ', '_')
        filename = f"CoverLetter_{safe_company}_{safe_title}_{timestamp}"

        # Save to generated_cover_letters folder
        local_path = os.path.join(self.generated_letters_dir, filename)
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

            # Run pdflatex twice for proper formatting
            for i in range(2):
                result = subprocess.run(
                    ['pdflatex', '-interaction=nonstopmode', '-output-directory', self.generated_letters_dir, os.path.basename(tex_file)],
                    capture_output=True,
                    text=True,
                    cwd=self.generated_letters_dir,
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

                print(f"[SUCCESS] Generated cover letter PDF: {pdf_path}")
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

    def save_to_downloads(self, letter_path):
        """
        Copy the generated cover letter to the user's Downloads folder.

        Args:
            letter_path: Path to the generated cover letter file

        Returns:
            str: Path to the file in Downloads folder
        """
        try:
            # Get user's Downloads folder
            downloads_folder = str(Path.home() / "Downloads")

            # Get filename
            filename = os.path.basename(letter_path)

            # Copy to Downloads
            dest_path = os.path.join(downloads_folder, filename)
            shutil.copy2(letter_path, dest_path)

            print(f"[SUCCESS] Copied cover letter to Downloads: {dest_path}")
            return dest_path

        except Exception as e:
            print(f"[WARNING] Error copying to Downloads folder: {str(e)}")
            return None

    def generate_cover_letter(self, job_description, company_name, job_title):
        """
        Main method to generate a complete ATS-optimized tailored cover letter.

        Args:
            job_description: Full job description text
            company_name: Name of the company
            job_title: Title of the job position

        Returns:
            dict: {
                'local_path': Path to cover letter in generated_cover_letters folder,
                'downloads_path': Path to cover letter in Downloads folder,
                'keywords_incorporated': List of keywords incorporated
            }
        """
        print(f"\n{'='*60}")
        print(f"Generating ATS-Optimized Cover Letter")
        print(f"Position: {job_title} at {company_name}")
        print(f"{'='*60}\n")

        # Step 1: Generate cover letter content
        print("[STEP 1] Generating cover letter content with Claude...")
        letter_data = self.generate_cover_letter_content(job_description, company_name, job_title)

        # Step 2: Generate LaTeX cover letter
        print("[STEP 2] Generating professional LaTeX cover letter...")
        local_path = self.generate_latex_cover_letter(letter_data, company_name, job_title)

        # Step 3: Copy to Downloads folder
        print("[STEP 3] Saving to Downloads folder...")
        downloads_path = self.save_to_downloads(local_path)

        print(f"\n{'='*60}")
        print(f"[SUCCESS] Cover Letter Generation Complete!")
        print(f"{'='*60}\n")

        return {
            'local_path': local_path,
            'downloads_path': downloads_path,
            'keywords_incorporated': letter_data.get('keywords_incorporated', [])
        }


def main(resume_text, candidate_name, candidate_email, job_description, company_name, job_title):
    """
    Main entry point for cover letter generation.

    Args:
        resume_text: Text content from resume
        candidate_name: Full name of candidate
        candidate_email: Email address of candidate
        job_description: Full job description text
        company_name: Name of the company
        job_title: Job title

    Returns:
        dict: Result with paths to generated cover letter
    """
    generator = ATSCoverLetterGenerator(resume_text, candidate_name, candidate_email)
    return generator.generate_cover_letter(job_description, company_name, job_title)


if __name__ == "__main__":
    # Test the cover letter generator
    print("Cover Letter Generator Test")
    print("="*60)

    # Example usage
    test_resume_text = """
    John Doe
    Software Engineer with 3 years of experience in Python, Flask, React
    Experience: Developed web applications, REST APIs, worked with databases
    """
    test_name = "John Doe"
    test_email = "john.doe@email.com"
    test_job_desc = """
    We are seeking a Software Engineer to join our team.
    Responsibilities include developing web applications using Python, Flask,
    and React. Experience with REST APIs and databases is required.
    """
    test_company = "Tech Company Inc"
    test_title = "Software Engineer"

    result = main(test_resume_text, test_name, test_email, test_job_desc, test_company, test_title)
    print(f"\nResult: {json.dumps(result, indent=2)}")
