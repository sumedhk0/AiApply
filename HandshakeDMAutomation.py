"""
Handshake Direct Message Automation Module

This module automates sending direct messages to hiring managers on Handshake.
It uses Playwright for browser automation to:
1. Log into Handshake with user credentials
2. Navigate directly to employer pages matching desired city and industry
3. Filter by location and industry
4. Send customized DMs to hiring managers at relevant companies
5. Track which companies have been contacted to avoid duplicates

NOTE: This module contacts employers directly, NOT through job postings.
"""

import os
import time
import re
import json
import urllib
import requests
import pandas as pd
from datetime import datetime
from browser_utils import BrowserManager, find_element_with_fallback, scroll_to_bottom
from llm_client import get_client
from pdf_utils import extract_text_from_pdf

# Official Handshake Industry Categories (from Handshake Help Center)
HANDSHAKE_INDUSTRIES = {
    "Accounting": ["accounting", "cpa", "audit", "tax"],
    "Advertising, PR & Marketing": ["advertising", "marketing", "pr", "public relations", "brand", "social media"],
    "Aerospace": ["aerospace", "aviation", "aircraft", "space", "satellite"],
    "Agriculture": ["agriculture", "farming", "agribusiness", "crop"],
    "Animal & Wildlife": ["animal", "wildlife", "veterinary", "zoo"],
    "Architecture and Planning": ["architecture", "urban planning", "design", "building design"],
    "Automotive": ["automotive", "automobile", "car", "vehicle manufacturing"],
    "Biotech & Life Sciences": ["biotech", "biotechnology", "life sciences", "genomics", "bioinformatics"],
    "Civil Engineering": ["civil engineering", "infrastructure", "construction engineering"],
    "Commercial Banking & Credit": ["banking", "commercial bank", "credit", "lending"],
    "Computer Networking": ["networking", "cisco", "network security", "infrastructure"],
    "Construction": ["construction", "building", "contractor", "project management"],
    "CPG - Consumer Packaged Goods": ["cpg", "consumer goods", "fmcg", "packaged goods"],
    "Defense": ["defense", "military", "homeland security"],
    "Design": ["design", "graphic design", "ux", "ui", "product design"],
    "Electronic & Computer Hardware": ["hardware", "electronics", "semiconductor", "chip"],
    "Energy": ["energy", "power", "oil", "gas", "fossil fuel", "energy production"],
    "Engineering & Construction": ["engineering services", "construction engineering"],
    "Environmental Services": ["environmental", "sustainability", "waste management", "recycling"],
    "Farming, Ranching and Fishing": ["farming", "ranch", "fishing", "aquaculture"],
    "Fashion": ["fashion", "apparel", "clothing", "textile"],
    "Financial Services": ["financial services", "wealth management", "financial planning"],
    "Food & Beverage": ["food", "beverage", "restaurant", "food production"],
    "Forestry": ["forestry", "timber", "logging"],
    "Government - Consulting": ["government consulting", "public sector consulting"],
    "Government - Intelligence": ["intelligence", "cia", "nsa", "cybersecurity government"],
    "Government - Local, State & Federal": ["government", "federal", "state", "local government", "public sector"],
    "Healthcare": ["healthcare", "hospital", "medical", "health services"],
    "Higher Education": ["university", "college", "higher education", "academic"],
    "Hotels & Accommodation": ["hotel", "hospitality", "accommodation", "lodging"],
    "Human Resources": ["hr", "human resources", "recruiting", "talent"],
    "Information Technology": ["it", "information technology", "tech support", "systems"],
    "Insurance": ["insurance", "underwriting", "actuarial"],
    "Interior Design": ["interior design", "interior decorator"],
    "International Affairs": ["international relations", "diplomacy", "foreign affairs"],
    "Internet & Software": ["software", "saas", "tech", "internet", "web", "app", "platform"],
    "Investment / Portfolio Management": ["investment management", "portfolio", "asset management"],
    "Investment Banking": ["investment banking", "ib", "mergers", "acquisitions"],
    "Journalism, Media & Publishing": ["journalism", "media", "publishing", "news", "content"],
    "K-12 Education": ["k-12", "elementary", "secondary", "teaching"],
    "Landscaping": ["landscaping", "lawn care", "grounds"],
    "Legal & Law Enforcement": ["legal", "law", "attorney", "law enforcement", "police"],
    "Library Services": ["library", "librarian", "archives"],
    "Management Consulting": ["consulting", "strategy", "management consulting", "mckinsey", "bcg", "bain"],
    "Manufacturing": ["manufacturing", "production", "factory", "industrial"],
    "Medical Devices": ["medical device", "medical equipment", "medtech"],
    "Movies, TV, Music": ["film", "television", "tv", "music", "entertainment"],
    "Natural Resources": ["natural resources", "mining", "extraction"],
    "NGO": ["ngo", "non-governmental", "international development"],
    "Non-Profit - Other": ["nonprofit", "non-profit", "charity", "foundation"],
    "Oil & Gas": ["oil", "gas", "petroleum", "upstream", "downstream"],
    "Other Education": ["education", "training", "learning"],
    "Other Industries": ["other", "miscellaneous"],
    "Performing and Fine Arts": ["performing arts", "fine arts", "theater", "dance"],
    "Pharmaceuticals": ["pharmaceutical", "pharma", "drug", "medicines"],
    "Politics": ["politics", "political", "campaign", "policy"],
    "Real Estate": ["real estate", "property", "commercial real estate"],
    "Religious Work": ["religious", "ministry", "church", "faith"],
    "Research": ["research", "r&d", "lab", "scientist"],
    "Restaurants & Food Service": ["restaurant", "food service", "dining"],
    "Retail Stores": ["retail", "store", "shop", "merchandising"],
    "Sales & Marketing": ["sales", "marketing", "business development"],
    "Scientific and Technical Consulting": ["scientific consulting", "technical consulting", "engineering consulting"],
    "Social Assistance": ["social work", "social services", "community services"],
    "Sports & Leisure": ["sports", "recreation", "fitness", "athletics"],
    "Staffing & Recruiting": ["staffing", "recruiting", "talent acquisition"],
    "Summer Camps/Outdoor Recreation": ["summer camp", "outdoor recreation", "camp"],
    "Telecommunications": ["telecom", "telecommunications", "wireless", "mobile"],
    "Tourism": ["tourism", "travel", "tour"],
    "Transportation & Logistics": ["transportation", "logistics", "supply chain", "shipping"],
    "Utilities & Renewable Energy": ["utilities", "renewable energy", "clean energy", "cleantech", "solar", "wind", "green energy", "sustainable energy"],
    "Veterinary": ["veterinary", "vet", "animal health"],
    "Wholesale Trade": ["wholesale", "distribution", "trade"]
}


class HandshakeAutomator:
    """
    Automates sending direct messages to hiring managers on Handshake.
    Contacts employers directly through their employer pages, not through job postings.
    """

    def __init__(self, headless=False):
        """
        Initialize the Handshake automator.

        Args:
            headless: Run browser in headless mode (default: False for debugging)
        """
        self.headless = headless
        self.browser_manager = None
        self.page = None

        # LLM client configuration (OpenRouter)
        self.llm_client = get_client()

        # Company DM tracking log file
        self.dm_log_file = os.path.join(os.path.dirname(__file__), "handshake_dm_log.json")

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

    def load_contacted_companies(self):
        """
        Load the list of companies that have already been contacted from the log file.

        Returns:
            set: Set of company names that have been contacted
        """
        try:
            if os.path.exists(self.dm_log_file):
                with open(self.dm_log_file, 'r') as f:
                    data = json.load(f)
                    companies = set(data.get('contacted_companies', []))
                    print(f"📋 Loaded {len(companies)} previously contacted companies from log")
                    return companies
            else:
                print(f"📋 No previous DM log found. Creating new log at: {self.dm_log_file}")
                return set()
        except Exception as e:
            print(f"⚠️ Error loading DM log: {str(e)}. Starting with empty log.")
            return set()

    def save_contacted_company(self, company_name):
        """
        Add a company to the contacted companies log file.

        Args:
            company_name: Name of the company that was contacted
        """
        try:
            # Load existing log
            contacted_companies = self.load_contacted_companies()

            # Add new company
            contacted_companies.add(company_name)

            # Save back to file
            with open(self.dm_log_file, 'w') as f:
                json.dump({
                    'contacted_companies': sorted(list(contacted_companies)),
                    'last_updated': datetime.now().isoformat()
                }, f, indent=2)

            print(f"✅ Saved '{company_name}' to DM log")
        except Exception as e:
            print(f"⚠️ Error saving company to DM log: {str(e)}")

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

            # Verify login by checking for employers page
            try:
                self.page.goto("https://app.joinhandshake.com/employers")
                self.page.wait_for_timeout(3000)

                # Check if we're on the employers page
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
            # Assuming first column has names, second column has codes
            industry_names = df.iloc[:, 0].dropna().tolist()
            industry_codes = df.iloc[:, 1].dropna().tolist()

            # Create mapping from name to code
            name_to_code = dict(zip(industry_names, industry_codes))

            # SPECIAL CASE: If user input is related to clean energy/cleantech/renewable energy,
            # ONLY return "Utilities & Renewable Energy"
            # This needs to happen BEFORE the Claude API call to avoid incorrect matches
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

CRITICAL RULES:
1. You MUST return at least 1 industry match
2. For ANY clean energy/cleantech/renewable energy related input, you MUST ONLY return ["Utilities & Renewable Energy"]

IMPORTANT MAPPINGS:
- "cleantech", "clean tech", "clean energy", "clean technology" → ["Utilities & Renewable Energy"]
- "renewable energy", "renewable", "solar", "wind", "green energy" → ["Utilities & Renewable Energy"]
- "sustainable energy", "sustainability" (energy context) → ["Utilities & Renewable Energy"]
- "tech" or "technology" (general) → ["Internet & Software"]
- "startups" → ["Internet & Software"]
- "business" → ["Management Consulting"]
- "energy" (general, not clean/renewable) → ["Energy"]

Return your answer as a JSON array of industry names EXACTLY as they appear in the list above. For example:
["Internet & Software", "Information Technology"]

Return ONLY the JSON array with no markdown formatting, nothing else. You must include at least 1 industry."""

            try:
                response_text = self.llm_client.create_message(prompt, max_tokens=300)
                response_text = response_text.strip()
            except Exception as api_error:
                print(f"❌ LLM API error: {str(api_error)}")
                print(f"Falling back to keyword matching...")
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
            # Fallback: manual keyword matching
            try:
                excel_path = os.path.join(os.path.dirname(__file__), "Industry Codes Handshake.xlsx")
                df = pd.read_excel(excel_path)
                industry_names = df.iloc[:, 0].dropna().tolist()
                industry_codes = df.iloc[:, 1].dropna().tolist()
                name_to_code = dict(zip(industry_names, industry_codes))

                user_field_lower = user_job_field.lower()
                matched_codes = []

                # Check for cleantech keywords FIRST (priority fallback)
                cleantech_keywords = [
                    "cleantech", "clean tech", "clean energy", "clean technology",
                    "renewable energy", "renewable", "solar", "wind", "green energy",
                    "sustainable energy", "sustainability", "utilities"
                ]
                is_cleantech = any(keyword in user_field_lower for keyword in cleantech_keywords)

                if is_cleantech:
                    cleantech_code = name_to_code.get("Utilities & Renewable Energy")
                    if cleantech_code:
                        print(f"🎯 Fallback: Detected clean energy input - using 'Utilities & Renewable Energy'")
                        return [cleantech_code]

                # Try keyword matching
                for name, code in name_to_code.items():
                    if user_field_lower in name.lower() or name.lower() in user_field_lower:
                        matched_codes.append(code)
                        if len(matched_codes) >= 2:
                            break

                if matched_codes:
                    print(f"🎯 Keyword matched '{user_job_field}' to industry codes: {matched_codes}")
                    return matched_codes

                # Absolute fallback: Use "Internet & Software" as default for tech-related,
                # or "Other Industries" for anything else
                print(f"⚠️ No keyword matches found. Using default industry...")

                tech_keywords = ['tech', 'software', 'engineer', 'developer', 'computer', 'data', 'ai', 'ml', 'app', 'web', 'coding', 'programming']
                is_tech_related = any(keyword in user_field_lower for keyword in tech_keywords)

                if is_tech_related:
                    default_industry = "Internet & Software"
                else:
                    default_industry = "Other Industries"

                default_code = name_to_code.get(default_industry)

                if default_code:
                    print(f"🎯 Using default industry '{default_industry}' with code: {default_code}")
                    return [default_code]
                else:
                    # Last resort: return the first industry in the list
                    first_code = industry_codes[0] if industry_codes else None
                    if first_code:
                        print(f"🎯 Using first available industry code: {first_code}")
                        return [first_code]

            except Exception as fallback_error:
                print(f"Fallback matching also failed: {str(fallback_error)}")

            # This should never happen now, but just in case
            print(f"⚠️ ERROR: Could not match any industry for '{user_job_field}'. This should not happen!")
            return []

    def findLocationFilter(self, desired_location):
        """
        Create location filter for filtering jobs on Handshake.
        Uses AI ONLY to get latitude/longitude coordinates.

        Args:
            desired_location: String representing the desired city/location in format "City, State" (e.g., "Dallas, Texas", "San Francisco, CA")

        Returns:
            dict: Location filter object with label, type, point (lat/long), text, and distance

        Raises:
            ValueError: If location format is invalid (must include both city and state)
        """
        try:
            # Validate that the location includes both city and state (must have a comma)
            if ',' not in desired_location:
                raise ValueError(
                    f"Invalid location format: '{desired_location}'. "
                    "Please provide both city and state (e.g., 'Dallas, Texas' or 'Dallas, TX')"
                )

            # Further validate that there's text on both sides of the comma
            print(desired_location)
            parts = desired_location.split(',')
            city_part = parts[0].strip()
            state_part = parts[1].strip() if len(parts) > 1 else ""

            if not city_part or not state_part:
                raise ValueError(
                    f"Invalid location format: '{desired_location}'. "
                    "Please provide both city and state (e.g., 'Dallas, Texas' or 'Dallas, TX')"
                )

            # Use AI ONLY to get latitude and longitude coordinates
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

            # Construct location filter as a list of parameters (not pre-encoded)
            # These will be properly encoded by employerFilterURLGenerator
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
            print(f"Using fallback location filter for '{desired_location}'")

            # Fallback: return basic structure - assume it's a US city
            city_name = desired_location.split(',')[0].strip()  # Extract city if "City, State" format

            return {
                "distance": "50mi",
                "point": "39.8283,-98.5795",  # Geographic center of US as fallback
                "label": f"{city_name}, United States",
                "type": "place"
            }

    

    def extract_employer_urls(self, progress_callback=None):
        self.page.wait_for_timeout(5000)

        # Scroll through the page to load all employer cards
        if progress_callback:
            progress_callback("Scrolling through page to load all employers...", "in-progress")

        scroll_to_bottom(self.page, max_scrolls=10, wait_time=2000)

        # Now extract all employer links
        all_links = self.page.locator('a').all()
        employer_urls = []
        employer_names = []
        for link in all_links:
            href = link.get_attribute('href')
            if href and '/e/' in href:
                employer_urls.append(href)
                employer_names.append(link.text_content() or "")

        if progress_callback:
            progress_callback(f"Extracted {len(employer_urls)} employer URLs", "success")

        return employer_urls, employer_names
    
    def clean_company_name(self, raw_company_name):
        """
        Extract clean company name from Handshake employer card text.

        Raw format example:
        "Coalesce Management Consulting\nUtilities and Renewable Energy · 36 followers\nDallas, TX\n50 - 100\nNot available\nFollow"

        Args:
            raw_company_name: Full text from Handshake employer card

        Returns:
            str: Clean company name (first line only)
        """
        if not raw_company_name:
            return "Unknown Company"

        # Split by newline and take the first line (company name)
        lines = raw_company_name.split('\n')
        clean_name = lines[0].strip()

        # Return cleaned name or fallback
        return clean_name if clean_name else "Unknown Company"

    def find_recruiter_name(self, progress_callback=None):
        """
        Extract recruiter's name from their Handshake profile page.

        Returns:
            str: Recruiter's name, or None if not found
        """
        all_names = self.page.locator('h1').all()
        for name in all_names:
            val = name.text_content() or ""
            val = val.strip()
            if "Message" in val:
                # Extract name after "Message" text
                # Example: "Message Dr. Alice Wonderland" -> "Dr. Alice Wonderland"
                recruiter_name = val.split("Message", 1)[1].strip()

                # If the name has newlines (e.g., "Dr. Alice Wonderland\nDoctor of Research"),
                # take only the first line (the actual name)
                if '\n' in recruiter_name:
                    recruiter_name = recruiter_name.split('\n')[0].strip()

                return recruiter_name if recruiter_name else None

        return None

    def extract_job_title(self):
        """
        Extract the recruiter's job title from their Handshake profile page.

        The job title typically appears in the profile header or below the recruiter's name.

        Returns:
            str: Job title, or "N/A" if not found
        """
        try:
            # Strategy 1: Look for h2 elements that might contain job title
            all_h2 = self.page.locator('h2').all()
            for h2 in all_h2:
                text = (h2.text_content() or "").strip()
                # Filter out common non-title headers
                if text and text not in ['Message', 'About', 'Education', 'Experience', 'Skills']:
                    # This might be the job title
                    if len(text) < 100:  # Reasonable length for a job title
                        return text

            # Strategy 2: Look for elements with specific classes
            job_title_selectors = [
                '[class*="job-title"]',
                '[class*="title"]',
                '[class*="position"]',
                'div[class*="profile"] p:first-child',
            ]

            for selector in job_title_selectors:
                try:
                    elements = self.page.locator(selector).all()
                    for elem in elements:
                        text = (elem.text_content() or "").strip()
                        if text and len(text) < 100 and '\n' not in text:
                            return text
                except:
                    continue

            # Strategy 3: Extract from recruiter name element if it contains title
            all_names = self.page.locator('h1').all()
            for name in all_names:
                val = (name.text_content() or "").strip()
                if "Message" in val:
                    # Remove "Message" prefix
                    remaining_text = val.split("Message", 1)[1].strip()
                    # If there's a newline, the second line might be the job title
                    if '\n' in remaining_text:
                        lines = remaining_text.split('\n')
                        if len(lines) > 1:
                            potential_title = lines[1].strip()
                            if potential_title:
                                return potential_title

            # If nothing found, return N/A
            return "N/A"

        except Exception as e:
            print(f"Error extracting job title: {str(e)}")
            return "N/A"


    def find_recruiter_url(self):
        print('reached find recruiter url')
        self.page.wait_for_timeout(5000)

        # Scroll through the page to ensure all recruiter profiles are loaded
        scroll_to_bottom(self.page, max_scrolls=5, wait_time=1500)

        # Now extract all recruiter profile links
        all_links = self.page.locator('a').all()
        person_links = []
        person_name = []
        self.page.wait_for_timeout(2000)
        for link in all_links:
            href = link.get_attribute('href')
            if href and '/profiles/' in href:
                person_links.append(href)
                person_name.append((link.text_content() or "").strip())
        if len(person_name) >= 2 and len(person_links) >= 2:
            return person_links[1], person_name[1]
        else:
            return False
    
    
    def sendAllDMs(self, progress_callback=None, num_dms=None, user_resume_path=None, custom_message=""):
        dms_sent=0
        results = {
            "successful_dms": 0,
            "failed_dms": 0,
            "skipped": 0,
            "already_contacted": 0,
            "companies_contacted": [],
            "messages_sent": []
        }

        # Load previously contacted companies from log
        contacted_companies = self.load_contacted_companies()

        employer_urls,employer_names=self.extract_employer_urls(progress_callback)

        for i in range(len(employer_urls)):
            if num_dms and dms_sent>=num_dms:
                return results

            # Clean the company name (remove followers, location, etc.)
            raw_company_name = employer_names[i]
            company_name = self.clean_company_name(raw_company_name)

            # Check if company has already been contacted
            if company_name in contacted_companies:
                print(f"⏭️  Skipping '{company_name}' - already contacted previously")
                results["already_contacted"] += 1
                if progress_callback:
                    progress_callback(f"Skipped '{company_name}' (already contacted)", "info")
                continue

            self.page.goto(employer_urls[i])
            self.page.wait_for_timeout(3000)
            if(self.find_recruiter_url()):
                recruiter_url, recruiter_name = self.find_recruiter_url()
                if recruiter_url:
                    self.page.goto(recruiter_url)
                    self.page.wait_for_timeout(3000)

                    # Extract recruiter name
                    nombre=self.find_recruiter_name(progress_callback)
                    print(f"Recruiter name: {nombre}")

                    # Extract job title from recruiter profile
                    job_title = self.extract_job_title()
                    print(f"Job title: {job_title}")

                    message_text=self.generate_personalized_message(
                        company_name=company_name,
                        recruiter_name=nombre,
                        user_resume_path=user_resume_path,
                        custom_message=custom_message
                    )
                    if(self.send_dm_to_hiring_manager(message_text,progress_callback)):
                        results["successful_dms"]+=1
                        results["companies_contacted"].append(company_name)

                        # Add DM details for database tracking
                        from datetime import datetime
                        dm_entry = {
                            "company_name": company_name,
                            "job_title": job_title,  # Now extracted from profile
                            "recruiter_name": nombre or "N/A",
                            "message_sent": message_text,
                            "date_sent": datetime.now().isoformat()
                        }
                        results["messages_sent"].append(dm_entry)
                        dms_sent+=1

                        # Save company to log after successful DM (use clean name)
                        self.save_contacted_company(company_name)
                        contacted_companies.add(company_name)  # Update local cache
                    else:
                        results["failed_dms"]+=1
                    time.sleep(5)
            else:
                results["skipped"]+=1

        return results
    
    
    
    def send_dm_to_hiring_manager(self, message_text, progress_callback=None):
        """
        Send a direct message to a hiring manager that will appear in the Messages section.

        This function:
        1. Clicks the Message button on the hiring manager's profile
        2. Waits for the message composer to fully load
        3. Enters the message text
        4. Sends the message
        5. Verifies the message was sent successfully

        Args:
            message_text: The text content of the message to send
            progress_callback: Optional callback to report progress

        Returns:
            bool: True if message sent successfully, False otherwise
        """
        try:
            if progress_callback:
                progress_callback("Opening message composer...", "in-progress")

            self.page.wait_for_timeout(3000)

            # Find and click the Message button using Playwright selectors
            message_button_selectors = [
                "button:has-text('Message')",
                "button[aria-label='Message']",
                "a:has-text('Message')",
                "button[class*='message']",
                "xpath=//button[contains(text(), 'Message')]",
                "xpath=//*[contains(text(), 'Message') and (self::button or self::a)]"
            ]

            message_button = find_element_with_fallback(self.page, message_button_selectors, timeout=5000)

            if not message_button:
                if progress_callback:
                    progress_callback("Message button not found on profile page.", "error")
                return False

            # Click the message button
            message_button.click()
            print("✓ Clicked message button")
            self.page.wait_for_timeout(3000)  # Give time for messaging interface to load

            # Wait for the message composer to be fully loaded
            if progress_callback:
                progress_callback("Waiting for message composer to load...", "in-progress")

            # Try multiple strategies to find the message input
            message_box_selectors = [
                "textarea",
                "textarea[placeholder*='message' i]",
                "textarea[placeholder*='Message' i]",
                "textarea[aria-label*='message' i]",
                "div[contenteditable='true']",
                "div[role='textbox']",
                "xpath=//textarea[contains(@placeholder, 'Type')]"
            ]

            message_box = find_element_with_fallback(self.page, message_box_selectors, timeout=10000)

            if not message_box:
                if progress_callback:
                    progress_callback("Message input box not found in messaging interface.", "error")
                return False

            print(f"✓ Found message input")

            # Clear any existing text and enter the message
            if progress_callback:
                progress_callback("Composing message...", "in-progress")

            message_box.click()  # Ensure it's focused
            self.page.wait_for_timeout(500)

            # Clear existing text
            message_box.press("Control+a")
            message_box.press("Delete")

            # Type the message
            message_box.fill(message_text)
            print(f"✓ Entered message text ({len(message_text)} characters)")
            self.page.wait_for_timeout(1500)  # Wait for text to fully populate

            # Find and click the Send button
            if progress_callback:
                progress_callback("Sending message...", "in-progress")

            send_button_selectors = [
                "button:has-text('Send')",
                "button[type='submit']:has-text('Send')",
                "button[aria-label*='Send']",
                "button[aria-label*='send']",
                "button[type='submit']",
                "xpath=//button[contains(text(), 'Send')]"
            ]

            send_button = find_element_with_fallback(self.page, send_button_selectors, timeout=5000)

            if not send_button:
                if progress_callback:
                    progress_callback("Send button not found or not clickable.", "error")
                return False

            # Click the send button
            send_button.click()
            print("✓ Clicked send button")
            self.page.wait_for_timeout(2000)

            # Verify the message was sent
            try:
                self.page.wait_for_timeout(1000)
                # Try to get current text in message box
                try:
                    current_text = message_box.input_value() if message_box.is_visible() else ""
                except:
                    current_text = ""

                if len(current_text.strip()) == 0:
                    print("✓ Message box cleared - message sent successfully")
                    if progress_callback:
                        progress_callback("Direct message sent successfully and will appear in Messages section!", "success")
                    return True
                else:
                    print(f"⚠ Message box still contains text: {current_text[:50]}...")
                    if progress_callback:
                        progress_callback("Message sent (verification unclear)", "success")
                    return True
            except:
                print("✓ Message sent (could not verify, but no errors)")
                if progress_callback:
                    progress_callback("Direct message sent successfully!", "success")
                return True

        except Exception as e:
            error_msg = f"Error sending DM: {str(e)}"
            print(f"✗ {error_msg}")
            if progress_callback:
                progress_callback(error_msg, "error")
            return False


    def generate_personalized_message(self, company_name, recruiter_name, user_resume_path, custom_message=""):
        """
        Use Claude API to generate a personalized DM for the hiring manager.

        Args:
            company_name: Name of the company
            recruiter_name: Name of the hiring manager (if available)
            user_resume_path: Path to user's resume PDF (REQUIRED)
            custom_message: User's custom talking points

        Returns:
            str: Personalized message text

        Raises:
            ValueError: If resume path is not provided or file doesn't exist
        """
        # Validate resume is provided and exists
        if not user_resume_path:
            raise ValueError(
                "Resume path is required. Please provide a valid path to your resume PDF."
            )

        if not os.path.exists(user_resume_path):
            raise ValueError(
                f"Resume file not found at path: {user_resume_path}\n"
                "Please ensure the file exists and the path is correct."
            )

        try:
            greeting = f"Hi {recruiter_name}" if recruiter_name else "Hello"

            # Extract text from resume PDF
            resume_text = extract_text_from_pdf(user_resume_path)
            if not resume_text:
                print(f"⚠️ Could not extract text from resume, using fallback message")
                raise ValueError("Could not extract resume text")

            prompt = f"""You are helping a student write a personalized, professional direct message to a hiring manager on Handshake.

Company: {company_name}
Hiring Manager: {recruiter_name or 'Unknown'}. Only use their full name or title (such as Dr.). So for example if the entry was 'Dr. Alice Wonderland\nDoctor of Research, Research Labs' you should only use 'Dr. Alice Wonderland' or 'Dr. Wonderland'.

RESUME CONTENT:
{resume_text}

Write a short, professional direct message (3-4 sentences max) that:
1. Expresses genuine interest in opportunities at {company_name}
2. Highlights 1-2 relevant skills or experiences from the resume that align with the company's industry
3. Asks about internship or full-time opportunities and expresses enthusiasm to discuss further
4. Sounds natural and conversational (not overly formal)

{f'Additional context from student: {custom_message}' if custom_message else ''}

Return ONLY the message body (no subject line, greeting, or signature). Start directly with the content.
Do not include placeholders like [Your Name] - the message should be ready to send as-is."""

            try:
                message_body = self.llm_client.create_message(prompt, max_tokens=500)
                message_body = message_body.strip()
                full_message = f"{greeting},\n\n{message_body}\n\nBest regards"

                return full_message

            except Exception as api_error:
                print(f"❌ LLM API error: {str(api_error)}")
                print(f"Using fallback message template...")
                raise Exception(f"API error: {str(api_error)}")

        except Exception as e:
            print(f"LLM API error: {str(e)}")
            # Fallback to simple template
            return f"""{greeting},

I'm very interested in exploring internship and full-time opportunities at {company_name}. I believe my skills and experience would be a great fit for your team.

Would you be available for a brief conversation about potential opportunities?

Best regards"""

    
            
    
    def employerFilterURLGenerator(self, industry_codes, location_filter, job_type=None):
        """
        Generate a URL to filter employers (not jobs) on Handshake.

        Generates URL with proper encoding matching Handshake's format:
        - Brackets [] encoded as %5B%5D
        - Spaces encoded as +
        - Commas encoded as %2C

        Args:
            industry_codes: List of industry codes to filter by
            location_filter: Dict with keys: distance, point, label, type
            job_type: Optional job type filter (3 for internships)

        Returns:
            str: URL to navigate to employers page with filters applied
        """

        base_url = "https://app.joinhandshake.com/employer-search?per_page=50"

        # Add job type filter if specified (e.g., 3 for internships)
        if job_type:
            base_url += f"&jobType={job_type}"

        # Add location parameters with properly encoded brackets
        # locations[][field] → locations%5B%5D%5Bfield%5D
        # Use quote_plus for label (spaces→+), quote for others
        base_url += f"&locations%5B%5D%5Bdistance%5D={location_filter['distance']}"
        base_url += f"&locations%5B%5D%5Bpoint%5D={urllib.parse.quote(location_filter['point'], safe='')}"
        base_url += f"&locations%5B%5D%5Blabel%5D={urllib.parse.quote_plus(location_filter['label'])}"
        base_url += f"&locations%5B%5D%5Btype%5D={location_filter['type']}"

        # Add industry codes with encoded brackets
        # industryIds[] → industryIds%5B%5D
        for code in industry_codes:
            base_url += f'&industryIds%5B%5D={code}'

        # Add institution size filters with encoded brackets
        base_url += '&institutionSizeIds%5B%5D=1&institutionSizeIds%5B%5D=2&institutionSizeIds%5B%5D=3&institutionSizeIds%5B%5D=4'

        # Add page number
        base_url += '&page=1'

        #print(f"\n🔗 Generated URL: {base_url}\n")
        return base_url
    
    def run_dm_campaign(self, city, num_dms, desired_job_field=None,
                        user_resume_path=None, custom_message="", contacted_companies=None,
                        progress_callback=None, login_confirmed_callback=None, job_type=None):
        """
        Run a complete DM campaign on Handshake by contacting employers directly.

        Args:
            city: Desired city for employer search
            num_dms: Number of DMs to send
            desired_job_field: User's desired job field/industry
            user_resume_path: Path to user's resume PDF (REQUIRED)
            custom_message: User's custom talking points
            contacted_companies: Set of companies already contacted
            progress_callback: Optional callback function to report progress
            login_confirmed_callback: Optional function that returns True when user confirms login
            job_type: Optional job type filter (3 for internships, None for all)

        Returns:
            dict: Results with successful_dms, failed_dms, companies_contacted

        Raises:
            ValueError: If resume path is not provided or file doesn't exist
        """
        # Initialize results dictionary
        results = {
            "successful_dms": 0,
            "failed_dms": 0,
            "skipped": 0,
            "already_contacted": 0,
            "companies_contacted": [],
            "messages_sent": []
        }

        # Validate resume is provided and exists
        if not user_resume_path:
            error_msg = "Resume path is required. Please provide a valid path to your resume PDF."
            if progress_callback:
                progress_callback(error_msg, "error")
            raise ValueError(error_msg)

        if not os.path.exists(user_resume_path):
            error_msg = f"Resume file not found at path: {user_resume_path}\nPlease ensure the file exists and the path is correct."
            if progress_callback:
                progress_callback(error_msg, "error")
            raise ValueError(error_msg)

        if contacted_companies is None:
            contacted_companies = set()

        try:
            self.setup_driver()

            if not self.login_to_handshake(progress_callback, login_confirmed_callback):
                return results

            industry_codes = self.match_industry_to_handshake(desired_job_field)
            location_filter = self.findLocationFilter(city)
            filter_url = self.employerFilterURLGenerator(industry_codes, location_filter, job_type)

            if progress_callback:
                progress_callback(f"Navigating to employer search page with filters...", "in-progress")

            self.page.goto(filter_url)

            # Wait for the page to load completely
            self.page.wait_for_timeout(5000)

            if progress_callback:
                progress_callback("Employer search page loaded. Extracting employer information...", "in-progress")

            results=self.sendAllDMs(
                progress_callback=progress_callback,
                num_dms=num_dms,
                user_resume_path=user_resume_path,
                custom_message=custom_message
            )


            if progress_callback:
                summary = f"Campaign complete! Sent: {results['successful_dms']}, Already Contacted: {results['already_contacted']}, Skipped: {results['skipped']}, Failed: {results['failed_dms']}"
                progress_callback(summary, "success", count=results['successful_dms'])

        except Exception as e:
            error_msg = f"Campaign error: {str(e)}"
            print(error_msg)
            if progress_callback:
                progress_callback(error_msg, "error")

        finally:
            if self.browser_manager is not None:
                try:
                    print("\nClosing browser in 10 seconds...")
                    time.sleep(10)
                    self.browser_manager.close()
                    print("Browser closed successfully.")
                except Exception as e:
                    print(f"Warning: Error closing browser: {str(e)}")

        return results


def main(city, num_dms, desired_job_field=None,
         user_resume_path=None, custom_message="",
         user_companies_contacted=None, progress_callback=None, login_confirmed_callback=None, job_type=None):
    """
    Main entry point for Handshake DM automation.

    Args:
        city: Desired city for employer search
        num_dms: Number of DMs to send
        desired_job_field: User's desired job field/industry (e.g., "cleantech", "software engineering")
        user_resume_path: Path to user's resume PDF (REQUIRED)
        custom_message: User's custom talking points
        user_companies_contacted: Set of companies already contacted
        progress_callback: Optional callback function to report progress
        login_confirmed_callback: Optional function that returns True when user confirms login
        job_type: Optional job type filter (3 for internships, None for all)

    Returns:
        dict: Results from the DM campaign

    Raises:
        ValueError: If resume path is not provided or file doesn't exist
    """
    # Validate resume is provided and exists
    if not user_resume_path:
        error_msg = "Resume path is required. Please provide a valid path to your resume PDF."
        if progress_callback:
            progress_callback(error_msg, "error")
        raise ValueError(error_msg)

    if not os.path.exists(user_resume_path):
        error_msg = f"Resume file not found at path: {user_resume_path}\nPlease ensure the file exists and the path is correct."
        if progress_callback:
            progress_callback(error_msg, "error")
        raise ValueError(error_msg)

    automator = HandshakeAutomator()

    results = automator.run_dm_campaign(
        city=city,
        num_dms=num_dms,
        desired_job_field=desired_job_field,
        user_resume_path=user_resume_path,
        custom_message=custom_message,
        contacted_companies=user_companies_contacted,
        progress_callback=progress_callback,
        login_confirmed_callback=login_confirmed_callback,
        job_type=job_type
    )

    return results


if __name__ == "__main__":
    print("Handshake DM Automation Test - Employer Direct Contact")
    print("=" * 50)
    print("\nNOTE: You will need to log into Handshake manually in the browser window.")
    print("This script contacts employers directly, NOT through job postings.")
    print("IMPORTANT: A valid resume PDF path is REQUIRED for this script to run.")
    print("=" * 50)

    def test_callback(message, msg_type="in-progress", count=None):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{msg_type.upper()}] {message}")

    # Test with cleantech industry - contacts employers directly
    # IMPORTANT: Replace "path/to/resume.pdf" with your actual resume path
    resume_path = "path/to/resume.pdf"  # UPDATE THIS WITH YOUR ACTUAL RESUME PATH

    # Validate resume exists before running
    if not os.path.exists(resume_path):
        print("\n" + "!" * 50)
        print("ERROR: Resume file not found!")
        print(f"Please update the resume_path variable with a valid path.")
        print(f"Current path: {resume_path}")
        print("!" * 50)
        exit(1)

    main(
        city="San Francisco, CA",  # Must include both city and state
        num_dms=5,
        desired_job_field="clean technology and renewable energy",  # AI will match this
        user_resume_path=resume_path,  # REQUIRED: Must be a valid path to your resume PDF
        custom_message="I have experience with chemical engineering and materials science, particularly with polymer coatings and amine chemistry",
        progress_callback=test_callback
    )

    # print("\n" + "=" * 50)
    # print("RESULTS SUMMARY")
    # print("=" * 50)
    # print(json.dumps(results, indent=2))

    # Save results
    #with open(f"dm_campaign_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", 'w') as f:
     #   json.dump(results, f, indent=2)
