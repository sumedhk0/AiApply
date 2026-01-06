"""
Handshake Job Application Automation Module

This module automates applying to jobs on Handshake.
It uses Playwright for browser automation to:
1. Log into Handshake with user credentials
2. Navigate to job listings matching desired criteria
3. Apply to relevant positions
4. Track which jobs have been applied to avoid duplicates
"""

import os
import time
import json
import urllib
import pandas as pd
import ResumeGenerator
import CoverLetterGenerator
from PyPDF2 import PdfReader
from datetime import datetime
from browser_utils import BrowserManager, find_element_with_fallback, scroll_to_bottom
from llm_client import get_client
from pdf_utils import extract_text_from_pdf


class HandshakeJobApplicator:
    """
    Automates applying to jobs on Handshake.
    """

    def __init__(self, headless=False, resume_path=None, user_id=None):
        """
        Initialize the Handshake job applicator.

        Args:
            headless: Run browser in headless mode (default: False for debugging)
            resume_path: Path to user's resume for tailoring
            user_id: User ID for database tracking
        """
        self.headless = headless
        self.browser_manager = None
        self.page = None
        self.resume_path = resume_path
        self.user_id = user_id

        # LLM client configuration (OpenRouter)
        self.llm_client = get_client()

        # Job application tracking log file
        self.application_log_file = os.path.join(os.path.dirname(__file__), "handshake_applications_log.json")

    def setup_driver(self):
        """Set up Playwright browser with appropriate options."""
        try:
            browserless_url = os.getenv('BROWSERLESS_URL')

            if browserless_url:
                # Connect to remote browser (Browserless.io for cloud deployment)
                print("Connecting to remote browser (Browserless.io)...")
                self.browser_manager = BrowserManager(headless=False)
                self.page = self.browser_manager.setup(remote_url=browserless_url)
                print("Connected to remote browser successfully")
            else:
                # Launch local browser
                self.browser_manager = BrowserManager(headless=self.headless)
                self.page = self.browser_manager.setup()
                print("Playwright browser initialized successfully")

        except Exception as e:
            print(f"Error setting up Playwright browser: {str(e)}")
            print("Troubleshooting tips:")
            print("1. Run: pip install playwright")
            print("2. Run: playwright install chromium")
            print("3. Close any existing browser instances")
            print("4. For cloud deployment, set BROWSERLESS_URL environment variable")
            raise

    def load_applied_jobs(self):
        """
        Load the list of jobs that have already been applied to from the log file.

        Returns:
            set: Set of job IDs that have been applied to
        """
        try:
            if os.path.exists(self.application_log_file):
                with open(self.application_log_file, 'r') as f:
                    data = json.load(f)
                    jobs = set(data.get('applied_jobs', []))
                    print(f"📋 Loaded {len(jobs)} previously applied jobs from log")
                    return jobs
            else:
                print(f"📋 No previous application log found. Creating new log at: {self.application_log_file}")
                return set()
        except Exception as e:
            print(f"⚠️ Error loading application log: {str(e)}. Starting with empty log.")
            return set()

    def save_applied_job(self, job_id, job_title, company_name):
        """
        Add a job to the applied jobs log file.

        Args:
            job_id: Unique ID of the job
            job_title: Title of the job
            company_name: Name of the company
        """
        try:
            # Load existing log
            applied_jobs = {}
            if os.path.exists(self.application_log_file):
                with open(self.application_log_file, 'r') as f:
                    data = json.load(f)
                    applied_jobs = data.get('applied_jobs_details', {})

            # Add new job
            applied_jobs[job_id] = {
                'job_title': job_title,
                'company_name': company_name,
                'applied_date': datetime.now().isoformat()
            }

            # Save back to file
            with open(self.application_log_file, 'w') as f:
                json.dump({
                    'applied_jobs': list(applied_jobs.keys()),
                    'applied_jobs_details': applied_jobs,
                    'last_updated': datetime.now().isoformat()
                }, f, indent=2)

            print(f"✅ Saved '{job_title}' at '{company_name}' to application log")
        except Exception as e:
            print(f"⚠️ Error saving job to application log: {str(e)}")

    def login_to_handshake(self, progress_callback=None, login_confirmed_callback=None):
        """
        Log into Handshake using manual login.
        Handles case where user is already logged in from previous session.

        Args:
            progress_callback: Optional callback function to report progress
            login_confirmed_callback: Optional function that returns True when user confirms login

        Returns:
            bool: True if login successful, False otherwise
        """
        try:
            if progress_callback:
                progress_callback("Navigating to Handshake login page...", "in-progress")

            self.page.goto("https://app.joinhandshake.com/login")
            self.page.wait_for_timeout(3000)

            if progress_callback:
                progress_callback("Please log into Handshake in the browser window, then click 'I'm Logged In' button below.", "login-wait")

            # Wait for user to confirm login via UI button
            print("\n" + "="*60)
            print("PLEASE LOG INTO HANDSHAKE IN THE BROWSER WINDOW")
            print("="*60)
            print("Click 'I'm Logged In' button in the web interface once you've logged in...")

            # Poll for login confirmation from UI
            max_wait_time = 300  # 5 minutes
            elapsed = 0
            poll_interval = 1  # Check every second

            while elapsed < max_wait_time:
                if login_confirmed_callback and login_confirmed_callback():
                    print("Login confirmed by user via UI button!")
                    break
                time.sleep(poll_interval)
                elapsed += poll_interval
            else:
                # Timeout - user didn't confirm login
                if progress_callback:
                    progress_callback("Login timeout - please try again and click the button after logging in", "error")
                return False

            # Verify login by checking for jobs page
            try:
                self.page.goto("https://app.joinhandshake.com/stu/postings")
                self.page.wait_for_timeout(3000)

                # Check if we're on the jobs page
                self.page.wait_for_selector("body", timeout=20000)

                if progress_callback:
                    progress_callback("Successfully logged into Handshake!", "success")

                return True

            except Exception:
                if progress_callback:
                    progress_callback("Login verification failed. Please ensure you're logged in.", "error")
                return False

        except Exception as e:
            error_msg = f"Login failed: {str(e)}"
            error_type = type(e).__name__
            print(f"DEBUG: Login error ({error_type}): {str(e)}")

            if progress_callback:
                progress_callback(error_msg, "error")
            return False

    def match_industry_to_handshake(self, user_job_field):
        """
        Use AI to match user's desired job field to Handshake's industry categories.
        Uses the same logic as HandshakeDMAutomation.

        Args:
            user_job_field: User's description of desired job field/industry

        Returns:
            list: List of 1-2 matching Handshake industry codes
        """
        try:
            # Read industry names and codes from Excel file
            excel_path = os.path.join(os.path.dirname(__file__), "Industry Codes Handshake.xlsx")
            df = pd.read_excel(excel_path)

            # Extract industry names from first column and codes from second column
            industry_names = df.iloc[:, 0].dropna().tolist()
            industry_codes = df.iloc[:, 1].dropna().tolist()

            # Create mapping from name to code
            name_to_code = dict(zip(industry_names, industry_codes))

            # SPECIAL CASE: If user input is related to clean energy/cleantech/renewable energy,
            # ONLY return "Utilities & Renewable Energy"
            user_field_lower = user_job_field.lower()

            # Check for clean tech/energy keywords
            cleantech_keywords = [
                "cleantech", "Clean Tech", "clean tech", "clean energy", "clean technology",
                "renewable energy", "renewable", "solar", "wind", "green energy",
                "sustainable energy", "sustainability", "utilities"
            ]

            is_cleantech = any(keyword in user_field_lower for keyword in cleantech_keywords)

            if is_cleantech:
                matched_industry_names = ["Utilities & Renewable Energy"]
                matched_codes = [name_to_code.get(name) for name in matched_industry_names if name in name_to_code]
                print(f"🎯 Detected clean energy/cleantech input - forcing ONLY 'Utilities & Renewable Energy'")
                print(f"🎯 User input: '{user_job_field}' → Industry: {matched_industry_names}")
                print(f"🎯 Corresponding industry codes: {matched_codes}")
                return matched_codes

            # Create a prompt for Claude to match industries
            industries_list = "\n".join([f"- {name}" for name in industry_names])

            prompt = f"""You are helping match a user's desired job field to Handshake's predefined industry categories.

User's desired job field: "{user_job_field}"

Here are all available Handshake industry categories:
{industries_list}

Based on the user's input, select the 1-2 MOST RELEVANT industry categories from the list above that best match their interests.

Return your answer as a JSON array of industry names EXACTLY as they appear in the list above. For example:
["Internet & Software", "Information Technology"]

Return ONLY the JSON array with no markdown formatting, nothing else. You must include at least 1 industry."""

            try:
                response_text = self.llm_client.create_message(prompt, max_tokens=300)
                response_text = response_text.strip()
            except Exception as api_error:
                print(f"❌ LLM API error: {str(api_error)}")
                raise Exception(f"API error: {str(api_error)}")

            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            matched_industry_names = json.loads(response_text)

            # Convert industry names to codes
            matched_codes = [name_to_code.get(name) for name in matched_industry_names if name in name_to_code]

            # Limit to maximum of 2 industries
            matched_codes = matched_codes[:2]

            # Ensure we have at least 1 match
            if not matched_codes:
                print(f"⚠️ Claude returned industry names that don't match our codes. Falling back...")
                raise ValueError("No valid industry codes found from Claude response")

            print(f"\n🎯 AI matched '{user_job_field}' to industries: {matched_industry_names}")
            print(f"🎯 Corresponding industry codes: {matched_codes}")

            return matched_codes

        except Exception as e:
            print(f"Industry matching error: {str(e)}")
            # Return empty list on error - will show all industries
            return []

    def findLocationFilter(self, desired_location):
        """
        Create location filter for filtering jobs on Handshake.
        Uses AI to get latitude/longitude coordinates.

        Args:
            desired_location: String representing the desired city/location in format "City, State"

        Returns:
            dict: Location filter object with label, type, point (lat/long), text, and distance
        """
        try:
            # Validate that the location includes both city and state (must have a comma)
            if ',' not in desired_location:
                raise ValueError(
                    f"Invalid location format: '{desired_location}'. "
                    "Please provide both city and state (e.g., 'Dallas, Texas' or 'Dallas, TX')"
                )

            # Further validate that there's text on both sides of the comma
            parts = desired_location.split(',')
            city_part = parts[0].strip()
            state_part = parts[1].strip() if len(parts) > 1 else ""

            if not city_part or not state_part:
                raise ValueError(
                    f"Invalid location format: '{desired_location}'. "
                    "Please provide both city and state (e.g., 'Dallas, Texas' or 'Dallas, TX')"
                )

            # Use AI to get latitude and longitude coordinates
            prompt = f"""You are helping find the latitude and longitude coordinates for a US city.

City: "{city_part}, {state_part}"

Return ONLY the latitude and longitude coordinates in this EXACT format:
"latitude,longitude"

For example:
- Dallas, Texas → "32.781339,-96.799759"
- San Francisco, CA → "37.7749,-122.4194"

Return ONLY the coordinates string in quotes, nothing else. No JSON, no markdown, just the string "lat,long"."""

            try:
                coordinates = self.llm_client.create_message(prompt, max_tokens=100)
                coordinates = coordinates.strip()
            except Exception as api_error:
                raise ValueError(
                    f"LLM API error: {str(api_error)}\n"
                    f"Please check your API key and internet connection."
                )

            # Remove quotes if AI added them
            coordinates = coordinates.replace('"', '').replace("'", "")

            # Construct location filter
            location_filter = {
                'distance': '50mi',
                'point': coordinates,  # Already in format: "lat,long"
                'label': f'{city_part}, {state_part}, United States',
                'type': 'place'
            }

            print(f"\n📍 Location filter for '{desired_location}': {location_filter}")

            return location_filter

        except Exception as e:
            print(f"Location filter error: {str(e)}")
            # Return basic fallback
            city_name = desired_location.split(',')[0].strip()
            return {
                "distance": "50mi",
                "point": "39.8283,-98.5795",  # Geographic center of US
                "label": f"{city_name}, United States",
                "type": "place"
            }

    def jobFilterURLGenerator(self, location_filter,role_keyword,industry_codes=None):
        """
        Generate a URL to filter jobs on Handshake.

        Generates URL with proper encoding matching Handshake's format:
        - Brackets [] encoded as %5B%5D
        - Spaces encoded as +
        - Commas encoded as %2C

        Args:
            industry_codes: List of industry codes to filter by
            location_filter: Dict with keys: distance, point, label, type
            role_keyword: Optional keyword to search for in job title/description

        Returns:
            str: URL to navigate to jobs page with filters applied
        """

        base_url = "https://app.joinhandshake.com/stu/postings?page=1&per_page=25&sort_direction=desc&sort_column=default"

        # Add location parameters with properly encoded brackets
        base_url += f"&locations%5B%5D%5Bdistance%5D={location_filter['distance']}"
        base_url += f"&locations%5B%5D%5Bpoint%5D={urllib.parse.quote(location_filter['point'], safe='')}"
        base_url += f"&locations%5B%5D%5Blabel%5D={urllib.parse.quote_plus(location_filter['label'])}"
        base_url += f"&locations%5B%5D%5Btype%5D={location_filter['type']}"

        # Add industry codes with encoded brackets
        if industry_codes:
            for code in industry_codes:
                base_url += f'&industries={code}'

        # Add job type filter (jobType=3 for internships/co-ops)
        base_url += '&jobType=3'
        # Add role keyword if provided
        #if role_keyword and role_keyword.strip():
        #    base_url += f'&search_term={urllib.parse.quote_plus(role_keyword)}'

        print(f"\n🔗 Generated jobs URL with filters")
        return base_url

    def run_application_session(self, industry=None, location=None, role=None,
                                 progress_callback=None, login_confirmed_callback=None):
        """
        Run a job application session on Handshake.
        Filters jobs by industry, location, and optionally role.

        Args:
            industry: Target industry (will be matched to Handshake categories)
            location: Target location in format "City, State"
            role: Optional target role/job title keyword
            progress_callback: Optional callback function to report progress
            login_confirmed_callback: Optional function that returns True when user confirms login

        Returns:
            dict: Results with login status and any applications made
        """
        results = {
            "login_successful": False,
            "applications_submitted": 0,
            "message": ""
            
        }

        try:
            self.setup_driver()

            if not self.login_to_handshake(progress_callback, login_confirmed_callback):
                results["message"] = "Login failed"
                return results

            results["login_successful"] = True
            print("reached")
            # Apply filters if provided
            if role and location:
                if progress_callback:
                    progress_callback(f"Matching industry '{industry}' to Handshake categories...", "in-progress")

                if industry:
                    industry_codes = self.match_industry_to_handshake(industry)

                if progress_callback:
                    progress_callback(f"Finding location coordinates for '{location}'...", "in-progress")

                location_filter = self.findLocationFilter(location)

                if progress_callback:
                    progress_callback("Generating filtered jobs URL...", "in-progress")
                if industry:
                    filter_url=self.jobFilterURLGenerator(location_filter,role,industry_codes)
                else:
                    filter_url = self.jobFilterURLGenerator(location_filter,role,industry_codes=None)
                if progress_callback:
                    progress_callback(f"Navigating to filtered jobs (Industry: {industry}, Location: {location}" +
                                      (f", Role: {role}" if role else "") + ")...", "in-progress")

                self.page.goto(filter_url)
                self.page.wait_for_timeout(5000)
                currUrl = self.page.url
                if industry:
                    for code in industry_codes:
                        currUrl += f'&industries={code}'

                currUrl = currUrl + '&jobType=3'
                self.page.goto(currUrl)
                self.page.wait_for_timeout(3000)
                if(role):
                    jobTypeField = self.page.locator("input[placeholder='Search jobs']")
                    jobTypeField.fill("")
                    jobTypeField.fill(role)
                    jobTypeField.press("Enter")
                    self.page.wait_for_timeout(4000)

                
                results["message"] = f"Successfully navigated to filtered jobs page. Filters applied - Industry: {industry}, Location: {location}" + (f", Role: {role}" if role else "")
                if progress_callback:
                    progress_callback(results["message"], "success")
                    progress_callback("Job application automation coming soon! Browser will remain open for manual review.", "info")
            else:
                results["message"] = "Login successful! Job application functionality coming soon."

                if progress_callback:
                    progress_callback("Login successful! Ready for job applications (functionality coming soon).", "success")

                
            print('reached applying to selected jobs')
            self.page.wait_for_timeout(3000)
            jobsHook = self.page.locator("[aria-label='Jobs List']")
            jobsHookElements = jobsHook.locator("> *").all()
            if len(jobsHookElements) > 2:
                clickableJobLinks = jobsHookElements[2]
                iterativeJobLinks = clickableJobLinks.locator("> *").all()

                for index, element in enumerate(iterativeJobLinks):
                    try:
                        print(f"Index Value: {index}")
                        # Re-fetch elements to avoid stale references
                        jobsHook = self.page.locator("[aria-label='Jobs List']")
                        jobsHookElements = jobsHook.locator("> *").all()
                        clickableJobLinks = jobsHookElements[2]
                        iterativeJobLinks = clickableJobLinks.locator("> *").all()
                        currentJob = iterativeJobLinks[index]

                        currentJob.scroll_into_view_if_needed()
                        print(f"Clicking element {index + 1}...")
                        jobText = currentJob.text_content() or ""
                        print(jobText)
                        currentJob.click()

                        jobName = jobText.split('\n')[0]

                        self.page.wait_for_timeout(1000)
                        value = self.applyToSelectedJob(jobName, progress_callback)
                        if not value:
                            continue
                        else:
                            results["applications_submitted"] += 1
                    except Exception as e:
                        if progress_callback:
                            progress_callback(f"Could not click element {index + 1}: {e}")
                        continue
        except Exception as e:
            error_msg = f"Session error: {str(e)}"
            print(error_msg)
            results["message"] = error_msg
            if progress_callback:
                progress_callback(error_msg, "error")

        finally:
            if self.browser_manager is not None:
                try:
                    print("\nClosing browser in 30 seconds...")
                    time.sleep(30)
                    self.browser_manager.close()
                    print("Browser closed successfully.")
                except Exception as e:
                    print(f"Warning: Error closing browser: {str(e)}")

        return results

    
        
        
    def applyToSelectedJob(self, job_name,progress_callback=None):
        """
        Apply to the currently selected job.

        This method:
        1. Extracts job details (title, company, description)
        2. Generates ATS-optimized tailored resume
        3. Saves resume locally and to Downloads
        4. Tracks application in both JSON log and user database

        Args:
            progress_callback: Optional callback for progress updates

        Returns:
            bool: True if application successful, False otherwise
        """
        try:
            # ADD FUNCTIONALITY TO SEE IF APPLY BUTTON IS THE RIGHT ONE. RETURN FALSE IF NOT.
            applyButton = self.page.locator("button[class^='sc-hhOBVt']").first
            if applyButton.text_content() == "Apply":
                print("Correct Apply Button Found")

            # Expand job description to get full details
                print('📋 Extracting job details...')
                if progress_callback:
                    progress_callback("Extracting job details...", "in-progress")
                expandJobDescriptionElements = self.page.locator("button[class^='sc-kAuIVs']").all()
                if len(expandJobDescriptionElements) > 1:
                    expandJobDescription = expandJobDescriptionElements[1]
                    print(expandJobDescription.text_content())

                    expandJobDescription.scroll_into_view_if_needed()
                    expandJobDescription.click()
                    self.page.wait_for_timeout(2000)
                    print('✅ Job description expanded')

                try:
                    job_title_element = self.page.locator("h1[class^='sc-']").first
                    job_title = (job_title_element.text_content() or "").strip()
                except:
                    job_title = "Unknown Position"

                # FIX THIS PART
                company_name = job_name

                # Extract job description
                try:
                    job_description = self.page.locator("xpath=//*[text()='At a glance']/ancestor::div[3]/div[5]/div[1]").text_content() or ""
                except:
                    # Fallback: try to get any visible job description
                    try:
                        job_description = self.page.locator("[class*='description']").first.text_content() or ""
                    except:
                        job_description = "No job description available"

                # Extract job ID from URL
                current_url = self.page.url
                job_id = current_url.split('/')[-1].split('?')[0] if '/' in current_url else f"{company_name}_{job_title}_{int(time.time())}"

                print(f'\n✅ Job Details Extracted:')
                print(f'   Title: {job_title}')
                print(f'   Company: {company_name}')
                print(f'   Job ID: {job_id}')
                print(f'   Description Length: {len(job_description)} characters\n')

                # Check if already applied (from local log)
                applied_jobs = self.load_applied_jobs()
                if job_id in applied_jobs:
                    print(f'⏭️  Already applied to this job (ID: {job_id}). Skipping...')
                    if progress_callback:
                        progress_callback(f"Already applied to {job_title} at {company_name}. Skipping...", "info")
                    return False

                # Check if already applied (from user database)
                if self.user_id:
                    from app import app, db
                    from models import User

                    with app.app_context():
                        user = db.session.get(User, self.user_id)
                        if user:
                            applied_job_ids = user.get_handshake_applied_job_ids()
                            if job_id in applied_job_ids:
                                print(f'⏭️  Already applied to this job (in user DB). Skipping...')
                                if progress_callback:
                                    progress_callback(f"Already applied to {job_title} at {company_name}. Skipping...", "info")
                                return False

                # Generate tailored resume
                if self.resume_path and os.path.exists(self.resume_path):
                    print(f'📝 Generating ATS-optimized resume for {job_title} at {company_name}...')
                    if progress_callback:
                        progress_callback(f"Generating tailored resume for {job_title}...", "in-progress")

                    try:
                        resume_generator = ResumeGenerator.ATSResumeGenerator(self.resume_path)
                        resume_result = resume_generator.generate_tailored_resume(
                            job_description=job_description,
                            company_name=company_name,
                            job_title=job_title
                        )

                        tailored_resume_path = resume_result.get('local_path')
                        downloads_path = resume_result.get('downloads_path')
                        keywords_added = resume_result.get('keywords_added', [])

                        print(f'✅ Resume generated successfully!')
                        print(f'   Local path: {tailored_resume_path}')
                        print(f'   Downloads: {downloads_path}')
                        print(f'   Keywords added: {", ".join(keywords_added)}')

                        if progress_callback:
                            progress_callback(f"Resume tailored with keywords: {', '.join(keywords_added[:3])}...", "success")

                    except Exception as e:
                        print(f'⚠️  Error generating resume: {str(e)}')
                        if progress_callback:
                            progress_callback(f"Resume generation error: {str(e)}", "error")
                        # CRITICAL: Skip this job if resume generation fails
                        return False
                else:
                    print(f'⚠️  No resume path provided or file not found')
                    return False

                # Generate cover letter
                cover_letter_path = None
                try:
                    print(f'📝 Generating cover letter for {job_title} at {company_name}...')
                    if progress_callback:
                        progress_callback(f"Generating cover letter for {job_title}...", "in-progress")

                    # Extract resume text for context
                    resume_reader = PdfReader(self.resume_path)
                    resume_text = ""
                    for page in resume_reader.pages:
                        resume_text += page.extract_text() + "\n"

                    # Extract candidate info from resume (basic extraction)
                    # This is a simple approach - you might want to enhance this
                    from app import app, db
                    from models import User
                    with app.app_context():
                        user = db.session.get(User, self.user_id)
                        candidate_name = user.username if user else "Candidate"
                        candidate_email = user.email if user else "candidate@email.com"

                    # Generate cover letter
                    cover_letter_generator = CoverLetterGenerator.ATSCoverLetterGenerator(
                        resume_text=resume_text,
                        candidate_name=candidate_name,
                        candidate_email=candidate_email,
                        warn_latex=False  # Suppress LaTeX warnings during automation
                    )

                    cover_letter_result = cover_letter_generator.generate_cover_letter(
                        job_description=job_description,
                        company_name=company_name,
                        job_title=job_title
                    )

                    cover_letter_path = cover_letter_result.get('local_path')
                    print(f'✅ Cover letter generated successfully!')
                    print(f'   Local path: {cover_letter_path}')

                    if progress_callback:
                        progress_callback(f"Cover letter generated and saved to Downloads", "success")

                except Exception as e:
                    print(f'⚠️  Error generating cover letter: {str(e)}')
                    if progress_callback:
                        progress_callback(f"Cover letter generation error: {str(e)}", "error")
                    # CRITICAL: Skip this job if cover letter generation fails (per user preference)
                    return False

                # Click Apply button and fill out application form
                print(f'🖱️  Clicking Apply button...')
                if progress_callback:
                    progress_callback("Clicking Apply button...", "in-progress")

                try:
                    # Click the Apply button
                    self.driver.execute_script("arguments[0].scrollIntoView();", applyButton)

                    applyButton.click()
                    time.sleep(2)  # Wait for modal to appear

                    # Wait for application form/modal to load
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//input[@type='file'] | //button[contains(text(), 'Submit')]"))
                    )

                    print(f'📋 Application form detected')
                    if progress_callback:
                        progress_callback("Application form opened", "info")

                    # Upload resume
                    try:
                        resume_x = self.driver.find_element(By.CSS_SELECTOR,"button[class^='sc-dTjBdT kFcsFs sc-hZNxer sc-bXijXC lchFil kaMwWt']")
                        print('aria label of the x button for resume')
                        print(resume_x.get_attribute('aria-label'))
                        resume_x.click()
                        time.sleep(2)
                        resume_input=self.driver.find_element(By.NAME,"file-Resume")
                        resume_input.send_keys(os.path.abspath(tailored_resume_path))
                        time.sleep(10)
                        print(f'📎 Uploaded tailored resume')
                        if progress_callback:
                            progress_callback("Uploaded tailored resume", "info")
                    except NoSuchElementException:
                        print(f'⚠️  No resume upload field found')

                    # Upload transcript (if user has one and field exists)
                    try:
                        transcript_input = self.driver.find_element(By.NAME, "file-Transcript")
                        
                        # Get user's transcript
                        from app import app, db
                        from models import User
                        with app.app_context():
                            user = db.session.get(User, self.user_id)
                            if user and user.transcript_filename:
                                transcript_path = os.path.join('user_transcripts', user.transcript_filename)
                                if os.path.exists(transcript_path):
                                    transcript_input.send_keys(os.path.abspath(transcript_path))
                                    time.sleep(10)
                                    print(f'📎 Uploaded transcript')
                                    if progress_callback:
                                        progress_callback("Uploaded transcript", "info")
                                else:
                                    print(f'⚠️  Transcript file not found at {transcript_path}')
                            else:
                                print(f'ℹ️  No transcript uploaded by user - skipping')
                    except NoSuchElementException:
                        print(f'ℹ️  No transcript upload field found')

                    # Upload cover letter (if field exists)
                    try:
                        cover_letter_input = self.driver.find_element(By.NAME, "file-Cover Letter")
                        if cover_letter_path and os.path.exists(cover_letter_path):
                            cover_letter_input.send_keys(os.path.abspath(cover_letter_path))
                            time.sleep(10)
                            print(f'📎 Uploaded cover letter')
                            if progress_callback:
                                progress_callback("Uploaded cover letter", "info")
                    except NoSuchElementException:
                        print(f'ℹ️  No cover letter upload field found')

                    # Submit the application
                    print(f'🚀 Submitting application...')
                    if progress_callback:
                        progress_callback("Submitting application...", "in-progress")

                    submit_button = self.driver.find_element(By.XPATH,
                        "//button[contains(text(), 'Submit Application')]")
                    self.driver.execute_script("arguments[0].scrollIntoView();", submit_button)
                    submit_button.click()
                    time.sleep(5)  # Wait for submission

                    try:
                        xButton=self.driver.find_element(By.CSS_SELECTOR,"button[aria-label='Cancel application']")
                        if xButton:
                            xButton.click()
                            time.sleep(2)
                            print(f'Application unsuccessful')
                            if progress_callback:
                                progress_callback("Application submission failed", "error")
                    except NoSuchElementException:
                        pass

                    print(f'✅ Application submitted successfully!')
                    if progress_callback:
                        progress_callback(f"Application submitted for {job_title} at {company_name}!", "success")

                except TimeoutException:
                    print(f'⚠️  Application form did not load in time')
                    if progress_callback:
                        progress_callback("Application form timeout - skipping job", "error")
                    return False
                except NoSuchElementException as e:
                    print(f'⚠️  Could not find required form element: {str(e)}')
                    if progress_callback:
                        progress_callback("Form element not found - skipping job", "error")
                    return False
                except Exception as e:
                    print(f'⚠️  Error during form submission: {str(e)}')
                    if progress_callback:
                        progress_callback(f"Form submission error: {str(e)}", "error")
                    return False

                # Save to local JSON log
                self.save_applied_job(job_id, job_title, company_name)

                # Save to user database
                if self.user_id:
                    from app import app, db
                    from models import User

                    with app.app_context():
                        user = db.session.get(User, self.user_id)
                        if user:
                            user.add_handshake_application(
                                job_id=job_id,
                                job_title=job_title,
                                company_name=company_name,
                                tailored_resume_path=tailored_resume_path,
                                cover_letter_path=cover_letter_path
                            )
                            db.session.commit()
                            print(f'✅ Application saved to user database')

                if progress_callback:
                    progress_callback(f"Application submitted for {job_title} at {company_name}", "success")

                print(f'✅ Application completed successfully!\n')
                time.sleep(2)
                return True
            else:
                print("❌ No internal Apply button available. Skipping this job.")
                if progress_callback:
                    progress_callback(f"No internal Apply button for {job_name}. Skipping...", "error")
                return False
        except Exception as e:
            print(f'❌ Error applying to job: {str(e)}')
            if progress_callback:
                progress_callback(f"Error applying to job: {str(e)}", "error")
            return False


def main(industry=None, location=None, role=None,
         progress_callback=None, login_confirmed_callback=None,
         resume_path=None, user_id=None):
    """
    Main entry point for Handshake job application automation.

    Args:
        industry: Target industry (will be matched to Handshake categories)
        location: Target location in format "City, State"
        role: Optional target role/job title keyword
        progress_callback: Optional callback function to report progress
        login_confirmed_callback: Optional function that returns True when user confirms login
        resume_path: Path to user's resume for tailoring
        user_id: User ID for database tracking

    Returns:
        dict: Results from the application session
    """
    applicator = HandshakeJobApplicator(
        resume_path=resume_path,
        user_id=user_id
    )

    results = applicator.run_application_session(
        industry=industry,
        location=location,
        role=role,
        progress_callback=progress_callback,
        login_confirmed_callback=login_confirmed_callback
    )

    return results


if __name__ == "__main__":
    print("Handshake Job Application Automation Test")
    print("=" * 50)
    print("\nNOTE: You will need to log into Handshake manually in the browser window.")
    print("Currently only implements login functionality.")
    print("=" * 50)

    def test_callback(message, msg_type="in-progress"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{msg_type.upper()}] {message}")

    results = main(progress_callback=test_callback)

    print("\n" + "=" * 50)
    print("RESULTS SUMMARY")
    print("=" * 50)
    print(json.dumps(results, indent=2))
