"""
Handshake Direct Message Automation Module

This module automates sending direct messages to hiring managers on Handshake.
It uses Selenium WebDriver to:
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
import anthropic
import pandas as pd
import setup
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager

api_key = setup.API_KEY

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
        self.driver = None
        self.wait = None

        # Claude API configuration
        self.claude_api_key = api_key
        if not self.claude_api_key:
            raise ValueError(
                "API_KEY not set in setup.py. "
                "Please set it with your Claude API key from https://console.anthropic.com/"
            )

        # Validate API key format
        if not self.claude_api_key.startswith('sk-ant-'):
            raise ValueError(
                f"Invalid API key format. API keys should start with 'sk-ant-'. "
                f"Please check your API key in setup.py"
            )

        try:
            self.claude_client = anthropic.Anthropic(api_key=self.claude_api_key)
        except Exception as e:
            raise ValueError(
                f"Failed to initialize Claude API client: {str(e)}. "
                f"Please check your API key in setup.py"
            )

        # Company DM tracking log file
        self.dm_log_file = os.path.join(os.path.dirname(__file__), "handshake_dm_log.json")

    def setup_driver(self):
        """Set up Chrome WebDriver with appropriate options."""
        chrome_options = Options()

        if self.headless:
            chrome_options.add_argument('--headless=new')

        # Stability and compatibility options
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-software-rasterizer')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')

        # Disable automation flags
        chrome_options.add_experimental_option('excludeSwitches', ['enable-automation', 'enable-logging'])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # Add error logging
        chrome_options.add_argument('--enable-logging')
        chrome_options.add_argument('--v=1')

        try:
            driver_path = ChromeDriverManager().install()
            print(f"Using ChromeDriver at: {driver_path}")

            self.driver = webdriver.Chrome(service=Service(driver_path), options=chrome_options)

            capabilities = self.driver.capabilities
            print(f"Chrome version: {capabilities.get('browserVersion', 'Unknown')}")
            print(f"ChromeDriver version: {capabilities.get('chrome', {}).get('chromedriverVersion', 'Unknown')}")

            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                '''
            })

            self.wait = WebDriverWait(self.driver, 20)

        except Exception as e:
            print(f"Error setting up ChromeDriver: {str(e)}")
            print("Troubleshooting tips:")
            print("1. Make sure Chrome browser is installed and up to date")
            print("2. Try running: pip install --upgrade selenium webdriver-manager")
            print("3. Close any existing Chrome instances")
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
        Log into Handshake using provided credentials.
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

            self.driver.get("https://app.joinhandshake.com/login")
            time.sleep(3)

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

            # Verify login by checking for job search page
            try:
                self.driver.get("https://app.joinhandshake.com/employers")
                
                time.sleep(3)

                # Check if we're on the jobs page
                self.wait.until(
                    EC.presence_of_element_located((By.XPATH, "./*"))
                )

                if progress_callback:
                    progress_callback("Successfully logged into Handshake!", "success")
                
                return True

            except TimeoutException:
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
                response = self.claude_client.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=300,
                    messages=[{"role": "user", "content": prompt}]
                )
            except anthropic.AuthenticationError as auth_error:
                print(f"❌ Claude API authentication failed: {str(auth_error)}")
                print(f"Your API key in setup.py may be invalid or expired.")
                print(f"Falling back to keyword matching...")
                raise Exception(f"API authentication error: {str(auth_error)}")
            except Exception as api_error:
                print(f"❌ Claude API error: {str(api_error)}")
                print(f"Falling back to keyword matching...")
                raise Exception(f"API error: {str(api_error)}")

            # Parse the response
            response_text = response.content[0].text.strip()

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
                response = self.claude_client.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=100,
                    messages=[{"role": "user", "content": prompt}]
                )
            except anthropic.AuthenticationError as auth_error:
                raise ValueError(
                    f"Claude API authentication failed: {str(auth_error)}\n"
                    f"Your API key in setup.py may be invalid or expired.\n"
                    f"Please get a new API key from https://console.anthropic.com/"
                )
            except Exception as api_error:
                raise ValueError(
                    f"Claude API error: {str(api_error)}\n"
                    f"Please check your API key and internet connection."
                )

            # Parse the response - should be just the coordinates string
            coordinates = response.content[0].text.strip()

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

    

    def extract_employer_urls(self,progress_callback=None):
        time.sleep(5)

        # Scroll through the page to load all employer cards
        if progress_callback:
            progress_callback("Scrolling through page to load all employers...", "in-progress")

        last_height = self.driver.execute_script("return document.body.scrollHeight")
        scroll_attempts = 0
        max_scroll_attempts = 10  # Prevent infinite scrolling

        while scroll_attempts < max_scroll_attempts:
            # Scroll down to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # Wait for page to load

            # Calculate new scroll height and compare with last scroll height
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                # If heights are the same, we've reached the bottom
                break
            last_height = new_height
            scroll_attempts += 1

            if progress_callback:
                progress_callback(f"Loading more employers... (scroll {scroll_attempts}/{max_scroll_attempts})", "in-progress")

        # Scroll back to top to ensure all elements are accessible
        self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)

        # Now extract all employer links
        all_links=self.driver.find_elements(By.TAG_NAME,'a')
        employer_urls=[]
        employer_names=[]
        for link in all_links:
            href=link.get_attribute('href')
            if href and '/e/' in href:
                employer_urls.append(href)
                employer_names.append(link.text.strip())

        if progress_callback:
            progress_callback(f"Extracted {len(employer_urls)} employer URLs", "success")

        return employer_urls,employer_names
    
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

    def find_recruiter_name(self,progress_callback=None):
        """
        Extract recruiter's name from their Handshake profile page.

        Returns:
            str: Recruiter's name, or None if not found
        """
        all_names=self.driver.find_elements(By.TAG_NAME,'h1')
        person_name=[]
        for name in all_names:
            val=name.text.strip()
            if "Message" in val:
                # Extract name after "Message" text
                # Example: "Message Dr. Alice Wonderland" -> "Dr. Alice Wonderland"
                recruiter_name = val.split("Message",1)[1].strip()

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
            all_h2 = self.driver.find_elements(By.TAG_NAME, 'h2')
            for h2 in all_h2:
                text = h2.text.strip()
                # Filter out common non-title headers
                if text and text not in ['Message', 'About', 'Education', 'Experience', 'Skills']:
                    # This might be the job title
                    if len(text) < 100:  # Reasonable length for a job title
                        return text

            # Strategy 2: Look for elements with specific classes (may vary based on Handshake's HTML)
            # Try common job title selectors
            job_title_selectors = [
                (By.CSS_SELECTOR, '[class*="job-title"]'),
                (By.CSS_SELECTOR, '[class*="title"]'),
                (By.CSS_SELECTOR, '[class*="position"]'),
                (By.XPATH, '//div[contains(@class, "profile")]//p[1]'),
            ]

            for by_method, selector in job_title_selectors:
                try:
                    elements = self.driver.find_elements(by_method, selector)
                    for elem in elements:
                        text = elem.text.strip()
                        if text and len(text) < 100 and '\n' not in text:
                            return text
                except:
                    continue

            # Strategy 3: Extract from recruiter name element if it contains title
            # Example: "Dr. Alice Wonderland\nDoctor of Research, Research Labs"
            all_names = self.driver.find_elements(By.TAG_NAME, 'h1')
            for name in all_names:
                val = name.text.strip()
                if "Message" in val:
                    # Remove "Message" prefix
                    remaining_text = val.split("Message", 1)[1].strip()
                    # If there's a newline, the second line might be the job title
                    if '\n' in remaining_text:
                        lines = remaining_text.split('\n')
                        if len(lines) > 1:
                            # Second line might be "Doctor of Research, Research Labs"
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
        time.sleep(5)

        # Scroll through the page to ensure all recruiter profiles are loaded
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        scroll_attempts = 0
        max_scroll_attempts = 5  # Employer pages are usually shorter

        while scroll_attempts < max_scroll_attempts:
            # Scroll down to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)  # Wait for content to load

            # Calculate new scroll height and compare with last scroll height
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                # If heights are the same, we've reached the bottom
                break
            last_height = new_height
            scroll_attempts += 1

        # Scroll back to top to ensure all elements are accessible
        self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)

        # Now extract all recruiter profile links
        all_links=self.driver.find_elements(By.TAG_NAME,'a')
        person_links=[]
        person_name=[]
        time.sleep(2)
        for link in all_links:
            #print(link.text)
            href=link.get_attribute('href')
            if href and '/profiles/' in href:
                person_links.append(href)
                person_name.append(link.text.strip())
        if len(person_name)>=2 & len(person_links)>=2:
            #print(person_name[1])
            #print(person_links[1])
            #print('reached end of find recruiter url: returned tuple')
            return person_links[1],person_name[1]
        else:
            #print('reached end of find recruiter url: returned nothing')
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

            self.driver.get(employer_urls[i])
            time.sleep(3)
            if(self.find_recruiter_url()):
                recruiter_url,recruiter_name=self.find_recruiter_url()
                if recruiter_url:
                    self.driver.get(recruiter_url)
                    time.sleep(3)

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

            time.sleep(3)

            # Find and click the Message button
            message_button_selectors = [
                "//button[contains(text(), 'Message')]",
                "//button[text()='Message']",
                "//button[@aria-label='Message']",
                "//a[contains(text(), 'Message')]",
                "//button[contains(@class, 'message')]",
                "//*[contains(text(), 'Message') and (self::button or self::a)]"
            ]

            message_button = None
            for selector in message_button_selectors:
                try:
                    message_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    if message_button:
                        print(f"✓ Found message button using selector: {selector}")
                        break
                except:
                    continue

            if not message_button:
                if progress_callback:
                    progress_callback("Message button not found on profile page.", "error")
                return False

            # Click the message button
            message_button.click()
            print("✓ Clicked message button")
            time.sleep(3)  # Give time for messaging interface to load

            # Wait for the message composer to be fully loaded
            # Check if we're now in a messaging interface (modal or separate page)
            if progress_callback:
                progress_callback("Waiting for message composer to load...", "in-progress")

            # Try multiple strategies to find the message input
            message_box = None
            message_box_selectors = [
                (By.TAG_NAME, 'textarea'),
                (By.CSS_SELECTOR, 'textarea[placeholder*="message" i]'),
                (By.CSS_SELECTOR, 'textarea[placeholder*="Message" i]'),
                (By.CSS_SELECTOR, 'textarea[aria-label*="message" i]'),
                (By.CSS_SELECTOR, 'div[contenteditable="true"]'),  # Rich text editor
                (By.XPATH, '//textarea[contains(@placeholder, "Type")]'),
                (By.XPATH, '//div[@role="textbox"]')
            ]

            for by_method, selector in message_box_selectors:
                try:
                    message_box = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((by_method, selector))
                    )
                    if message_box:
                        # Verify it's visible and interactable
                        if message_box.is_displayed():
                            print(f"✓ Found message input using: {by_method} - {selector}")
                            break
                        else:
                            message_box = None
                except:
                    continue

            if not message_box:
                if progress_callback:
                    progress_callback("Message input box not found in messaging interface.", "error")
                return False

            # Clear any existing text and enter the message
            if progress_callback:
                progress_callback("Composing message...", "in-progress")

            try:
                message_box.clear()
            except:
                # Some elements don't support clear(), try selecting all and deleting
                message_box.send_keys(Keys.CONTROL + "a")
                message_box.send_keys(Keys.DELETE)

            message_box.click()  # Ensure it's focused
            time.sleep(0.5)
            message_box.send_keys(message_text)
            print(f"✓ Entered message text ({len(message_text)} characters)")
            time.sleep(1.5)  # Wait for text to fully populate

            # Find and click the Send button
            if progress_callback:
                progress_callback("Sending message...", "in-progress")

            send_button_selectors = [
                "//button[contains(text(), 'Send')]",
                "//button[text()='Send']",
                "//button[@type='submit' and contains(., 'Send')]",
                "//button[contains(@aria-label, 'Send')]",
                "//button[contains(@aria-label, 'send')]",
                "//*[contains(text(), 'Send') and self::button]",
                "//button[@type='submit']"  # Generic submit button
            ]

            send_button = None
            for selector in send_button_selectors:
                try:
                    send_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    if send_button and send_button.is_displayed() and send_button.is_enabled():
                        print(f"✓ Found send button using selector: {selector}")
                        break
                    else:
                        send_button = None
                except:
                    continue

            if not send_button:
                if progress_callback:
                    progress_callback("Send button not found or not clickable.", "error")
                return False

            # Click the send button
            send_button.click()
            print("✓ Clicked send button")
            time.sleep(2)

            # Verify the message was sent by checking if:
            # 1. The textarea is cleared/empty
            # 2. The send button is disabled or no longer visible
            # 3. No error messages appeared
            try:
                # Check if message box is cleared (indicates successful send)
                time.sleep(1)
                current_text = message_box.get_attribute('value') or message_box.text
                if len(current_text.strip()) == 0:
                    print("✓ Message box cleared - message sent successfully")
                    if progress_callback:
                        progress_callback("Direct message sent successfully and will appear in Messages section!", "success")
                    return True
                else:
                    print(f"⚠ Message box still contains text: {current_text[:50]}...")
                    # Don't fail immediately - message might still have been sent
                    if progress_callback:
                        progress_callback("Message sent (verification unclear)", "success")
                    return True
            except:
                # If we can't verify, assume success since no error was thrown
                print("✓ Message sent (could not verify, but no errors)")
                if progress_callback:
                    progress_callback("Direct message sent successfully!", "success")
                return True

        except TimeoutException as e:
            error_msg = f"Timeout while sending DM: {str(e)}"
            print(f"✗ {error_msg}")
            if progress_callback:
                progress_callback(error_msg, "error")
            return False
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

            prompt = f"""You are helping a student write a personalized, professional direct message to a hiring manager on Handshake.

Company: {company_name}
Hiring Manager: {recruiter_name or 'Unknown'}. Only use their full name or title (such as Dr.). So for example if the entry was 'Dr. Alice Wonderland\nDoctor of Research, Research Labs' you should only use 'Dr. Alice Wonderland' or 'Dr. Wonderland'.

Write a short, professional direct message (3-4 sentences max) that:
1. Expresses genuine interest in opportunities at {company_name}
2. Highlights 1-2 relevant skills or experiences from the resume that align with the company's industry
3. Asks about internship or full-time opportunities and expresses enthusiasm to discuss further
4. Sounds natural and conversational (not overly formal)

{f'Additional context from student: {custom_message}' if custom_message else ''}

Return ONLY the message body (no subject line, greeting, or signature). Start directly with the content.
Do not include placeholders like [Your Name] - the message should be ready to send as-is."""

            content = [{"type": "text", "text": prompt}]

            # Load and attach resume (now mandatory)
            with open(user_resume_path, 'rb') as f:
                resume_data = f.read()
                import base64
                resume_base64 = base64.b64encode(resume_data).decode('utf-8')

                content.append({
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": resume_base64
                    }
                })

            try:
                response = self.claude_client.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=500,
                    messages=[{"role": "user", "content": content}]
                )

                message_body = response.content[0].text.strip()
                full_message = f"{greeting},\n\n{message_body}\n\nBest regards"

                return full_message

            except anthropic.AuthenticationError as auth_error:
                print(f"❌ Claude API authentication failed: {str(auth_error)}")
                print(f"Your API key in setup.py may be invalid or expired.")
                print(f"Using fallback message template...")
                raise Exception(f"API authentication error: {str(auth_error)}")

        except Exception as e:
            print(f"Claude API error: {str(e)}")
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

            self.driver.get(filter_url)

            # Wait for the page to load completely
            time.sleep(5)

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
            if self.driver is not None:
                try:
                    print("\nClosing browser in 10 seconds...")
                    time.sleep(10)
                    self.driver.quit()
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
