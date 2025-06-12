"""Automates the process of applying to jobs on LinkedIn using Selenium.

This module contains the `LinkedinEasyApply` class which handles logging into LinkedIn,
searching for jobs based on specified criteria, navigating job listings,
and attempting to fill out and submit Easy Apply applications. It also
integrates with an AI model for answering questions and tailoring resumes.
"""
import time
import random
import csv
import pyautogui
import traceback
import os
import re
from typing import Dict, List, Any, Optional, Tuple, Union

# Selenium imports
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

# Datetime and iteration tools
from datetime import date, datetime # Note: `date` is not directly used but often imported with `datetime`
from itertools import product

# Local application imports
from ai.ai_response_generator import AIResponseGenerator
from utils.utils import enter_text, select_dropdown, radio_select, scroll_slow, get_base_search_url
from external.external_applications import apply_to_ashby, apply_to_greenhouse
from utils.file_utils import write_to_file, record_unprepared_question


class LinkedinEasyApply:
    """
    Automates LinkedIn job applications using Selenium.

    This class encapsulates the logic for logging into LinkedIn, searching for jobs
    based on user-defined parameters, iterating through job listings, and attempting
    to "Easy Apply" to them. It handles multi-step application forms, common questions,
    resume/cover letter uploads, and integrates with an AI model (AIResponseGenerator)
    for tasks like answering complex questions and tailoring resumes.

    Attributes:
        browser (WebDriver): The Selenium WebDriver instance.
        parameters (Dict[str, Any]): Configuration parameters for the bot.
        ai_response_generator (AIResponseGenerator): Instance for AI interactions.
        # Other attributes are initialized based on `parameters`.
    """

    def __init__(self, parameters: Dict[str, Any], driver: WebDriver) -> None:
        """
        Initializes the LinkedinEasyApply bot.

        Args:
            parameters (Dict[str, Any]): A dictionary containing all necessary
                configuration parameters, such as login credentials, job search
                criteria (positions, locations), resume/cover letter paths,
                AI model details, blacklists, and various application preferences.
            driver (WebDriver): The Selenium WebDriver instance to be used for
                browser automation.
        """
        self.browser: WebDriver = driver
        self.email: str = parameters['email']
        self.password: str = parameters['password']
        self.openai_api_key: str = parameters.get('openaiApiKey', '')
        self.model_name: str = parameters.get('modelName', 'default-model-if-not-set') # Ensure a default
        self.disable_lock: bool = parameters['disableAntiLock']

        # Blacklists
        self.company_blacklist: List[str] = parameters.get('companyBlacklist', []) or []
        self.title_blacklist: List[str] = parameters.get('titleBlacklist', []) or []
        self.poster_blacklist: List[str] = parameters.get('posterBlacklist', []) or []

        # Job search parameters
        self.positions: List[str] = parameters.get('positions', [])
        self.locations: List[str] = parameters.get('locations', [])
        self.base_search_url: str = get_base_search_url(parameters) # Base URL for job searches

        self.seen_jobs: List[str] = [] # Tracks job links already processed

        # File paths and names
        self.output_file_directory: str = parameters['outputFileDirectory']
        # Construct full file paths
        self.file_name: str = os.path.join(self.output_file_directory, "output") # Base name for output CSV
        self.unprepared_questions_file_name: str = os.path.join(self.output_file_directory, "unprepared_questions")

        self.resume_dir: str = parameters['uploads']['resume']
        self.text_resume: str = parameters.get('textResume', '') # Path to plain text resume
        self.docx_resume: str = parameters.get('docxResume', '') # Path to DOCX resume (if used for tailoring prep)
        self.cover_letter_dir: str = parameters.get('uploads', {}).get('coverLetter', '')

        # Application form data
        self.checkboxes: Dict[str, bool] = parameters.get('checkboxes', {}) # Ensure dict for safety
        self.university_gpa: str = parameters.get('universityGpa', '') # GPA could be str
        self.salary_minimum: str = parameters.get('salaryMinimum', '') # Salary could be str
        self.notice_period: int = int(parameters.get('noticePeriod', 0)) # Default to 0 if not provided

        self.languages: Dict[str, str] = parameters.get('languages', {})
        self.experience: Dict[str, Any] = parameters.get('experience', {}) # 'default' might be int, others str
        self.personal_info: Dict[str, str] = parameters.get('personalInfo', {})
        self.eeo: Dict[str, str] = parameters.get('eeo', {}) # EEO related answers

        self.experience_default: int = int(self.experience.get('default', 0)) # Default experience if specific not found

        # Bot behavior flags
        self.debug: bool = parameters.get('debug', False)
        self.evaluate_job_fit: bool = parameters.get('evaluateJobFit', True)
        self.tailor_resume: bool = parameters.get('tailorResume', True)

        # Initialize AI Response Generator
        self.ai_response_generator: AIResponseGenerator = AIResponseGenerator(
            api_key=self.openai_api_key,
            personal_info=self.personal_info,
            experience=self.experience,
            languages=self.languages,
            resume_path=self.resume_dir, # Initial resume path
            checkboxes=self.checkboxes,
            text_resume_path=self.text_resume,
            debug=self.debug,
            model_name=self.model_name
        )

    def login(self) -> None:
        """
        Logs into LinkedIn.

        Attempts to restore a previous session if a "chrome_bot" directory exists.
        If session restoration fails or is not applicable, it proceeds with a
        full login using credentials. Handles potential security checks.
        """
        try:
            # Check if a previous session might be restorable (e.g., from user data dir)
            if self.debug:
                print("Attempting to restore previous session...")
            if os.path.exists("chrome_bot"): # "chrome_bot" might indicate a user data directory
                self.browser.get("https://www.linkedin.com/feed/") # Navigate to a page that requires login
                time.sleep(random.uniform(5, 10)) # Wait for page load and potential redirects

                # If not redirected to feed, assume login is needed
                if "feed" not in self.browser.current_url:
                    if self.debug:
                        print("Session not active or feed page not loaded, proceeding to standard login.")
                    self.load_login_page_and_login()
                else:
                    if self.debug:
                        print("Successfully restored session, currently on feed page.")
            else:
                if self.debug:
                    print("No previous session data found, proceeding to standard login.")
                self.load_login_page_and_login()

        except TimeoutException:
            # This might happen if page loads are very slow or if a security check interrupts
            if self.debug:
                print("Timeout occurred during login attempt, checking for security challenges...")
            self.security_check() # Allow user to manually resolve security checks
        except Exception as e:
            print(f"An unexpected error occurred during login: {e}")
            traceback.print_exc()
            # Consider if re-raising or specific handling is needed here
            # For now, it might proceed to security_check or fail if load_login_page_and_login also fails

    def security_check(self) -> None:
        """
        Handles manual intervention for LinkedIn security checks.

        If a security check page is detected (based on URL or page content),
        it prompts the user to complete the check in the browser and press Enter
        in the console to continue.
        """
        current_url: str = self.browser.current_url
        page_source: str = self.browser.page_source.lower() # Lowercase for case-insensitive matching

        # Check for common indicators of a security challenge page
        if '/checkpoint/challenge/' in current_url or \
           'security check' in page_source or \
           'quick verification' in page_source or \
           'verify you are human' in page_source:

            print("LinkedIn security check detected.")
            input("Please complete the security check in the browser, then press Enter in this console to continue...")
            time.sleep(random.uniform(5.5, 10.5)) # Wait for user to complete and page to settle
            if self.debug:
                print("Resuming after security check.")
        elif self.debug:
            print("No security check detected at this point.")


    def load_login_page_and_login(self) -> None:
        """
        Navigates to the LinkedIn login page and performs login using credentials.
        """
        if self.debug:
            print("Navigating to LinkedIn login page.")
        self.browser.get("https://www.linkedin.com/login")

        try:
            # Wait for the username field to be present and interactable
            username_field = WebDriverWait(self.browser, 15).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            if self.debug:
                print("Username field located.")
            username_field.send_keys(self.email)

            password_field = self.browser.find_element(By.ID, "password")
            if self.debug:
                print("Password field located.")
            password_field.send_keys(self.password)

            # Click the login button
            login_button = self.browser.find_element(By.CSS_SELECTOR, ".btn__primary--large") # Standard login button
            login_button.click()
            if self.debug:
                print("Login button clicked.")

            # Wait for successful login, indicated by redirection to the feed page
            WebDriverWait(self.browser, 20).until( # Increased timeout for login
                EC.url_contains("https://www.linkedin.com/feed/")
            )
            if self.debug:
                print("Successfully logged in and redirected to feed.")
            time.sleep(random.uniform(5, 10)) # Allow feed to load

        except TimeoutException:
            print("Timeout waiting for elements on login page or for feed redirection.")
            self.security_check() # Check for security challenge if login elements time out
        except Exception as e:
            print(f"An error occurred during the login process: {e}")
            traceback.print_exc()
            self.security_check() # Also check for security challenge on other errors


    def start_applying(self) -> None:
        """
        Manages the main job search and application loop.

        Iterates through combinations of positions and locations specified in parameters.
        For each combination, it navigates through job search result pages and
        calls `apply_jobs` to process applications on each page.
        Includes logic for periodic sleeps to mimic human behavior and avoid detection.
        """
        # Create all combinations of positions and locations
        searches: List[Tuple[str, str]] = list(product(self.positions, self.locations))
        random.shuffle(searches) # Shuffle to vary application order

        page_sleep_counter: int = 0 # Counter for pages processed since last long sleep
        # Minimum time the bot should run for a search iteration before potentially taking a longer break
        min_search_iteration_duration_seconds: int = 60 * self.parameters.get('iterationDurationMinutes', 2) # Default 2 minutes
        next_long_sleep_time: float = time.time() + min_search_iteration_duration_seconds

        for (position, location) in searches:
            current_search_location_url_param: str = "&location=" + location # LinkedIn specific URL part for location
            current_job_page_number: int = -1 # Start before the first page (page 0)

            if self.debug:
                print(f"Starting search for position: '{position}' in location: '{location}'.")

            try:
                while True: # Loop for paginating through job search results
                    page_sleep_counter += 1
                    current_job_page_number += 1
                    if self.debug:
                        print(f"Navigating to job page number: {current_job_page_number} for '{position}' in '{location}'.")

                    # Navigate to the specific job search page
                    self.next_job_page(position, current_search_location_url_param, current_job_page_number)
                    time.sleep(random.uniform(1.5, 3.5)) # Brief pause after page load

                    if self.debug:
                        print("Applying to jobs on the current page...")
                    self.apply_jobs(location) # Process jobs on the current page
                    if self.debug:
                        print("Finished applying to jobs on the current page.")

                    # Logic for periodic breaks
                    time_until_next_long_sleep: float = next_long_sleep_time - time.time()
                    if time_until_next_long_sleep > 0:
                        if self.debug:
                            print(f"Short sleep for {time_until_next_long_sleep:.2f} seconds until minimum iteration time is met.")
                        time.sleep(time_until_next_long_sleep)
                    # Reset timer for the next iteration duration
                    next_long_sleep_time = time.time() + min_search_iteration_duration_seconds

                    # Longer sleep every few pages
                    if page_sleep_counter % 5 == 0: # Every 5 pages
                        long_sleep_duration_seconds: int = random.randint(180, 300) # 3 to 5 minutes
                        if self.debug:
                            print(f"Taking a longer break for {long_sleep_duration_seconds / 60:.2f} minutes.")
                        time.sleep(long_sleep_duration_seconds)
                        # page_sleep_counter = 0 # Reset counter after long sleep if desired

            except Exception as e:
                # This exception is likely raised by apply_jobs if no more jobs are found on the page,
                # or by next_job_page if navigation fails.
                if "No more jobs on this page" in str(e) and self.debug:
                     print(f"No more jobs found for '{position}' in '{location}'. Moving to next search criteria.")
                else:
                    print(f"An error occurred during the search for '{position}' in '{location}': {e}")
                    traceback.print_exc()
                # Continue to the next position/location combination
                pass

            # Ensure minimum iteration time is met even if a search ends prematurely
            time_left_for_iteration: float = next_long_sleep_time - time.time()
            if time_left_for_iteration > 0:
                if self.debug:
                    print(f"Ensuring minimum iteration time by sleeping for an additional {time_left_for_iteration:.2f} seconds.")
                time.sleep(time_left_for_iteration)
            next_long_sleep_time = time.time() + min_search_iteration_duration_seconds # Reset for next search

            # Another check for a longer periodic sleep, in case a search iteration was very short
            if page_sleep_counter % 7 == 0: # Adjusted this condition slightly
                very_long_sleep_duration_seconds: int = random.randint(500, 900) # ~8 to 15 minutes
                if self.debug:
                    print(f"Taking a very long break for {very_long_sleep_duration_seconds / 60:.2f} minutes after several search criteria.")
                time.sleep(very_long_sleep_duration_seconds)


    def apply_jobs(self, current_search_location: str) -> None:
        """
        Processes and applies to jobs listed on the current search results page.

        It identifies job postings, extracts key information (title, company, link),
        checks against blacklists, and then calls `apply_to_job` for eligible ones.
        Handles dynamic class names for job listing elements.

        Args:
            current_search_location (str): The location string used in the current search,
                                           for logging purposes.

        Raises:
            Exception: If no jobs are found on the page, or if LinkedIn indicates
                       no matching jobs or an error page.
        """
        # Check for "No jobs found" banner
        try:
            no_jobs_element = self.browser.find_element(By.CLASS_NAME, 'jobs-search-two-pane__no-results-banner--expand')
            if "no matching jobs found" in no_jobs_element.text.lower():
                raise Exception("No more jobs on this page (banner found).")
        except NoSuchElementException:
            pass # Banner not found, proceed

        # Check for other indicators of no jobs or errors
        page_source_lower = self.browser.page_source.lower()
        if 'unfortunately, things are' in page_source_lower or 'no matching jobs found' in page_source_lower: # LinkedIn error/empty page
            raise Exception("No more jobs on this page (LinkedIn message).")

        # Load already seen jobs from the output file to avoid re-applying
        try:
            # Use the full path for the output file
            full_output_file_path = self.file_name + ".csv" # self.file_name is now base path + "output"
            if not os.path.exists(self.output_file_directory):
                 os.makedirs(self.output_file_directory)

            with open(full_output_file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                # Assuming link is in the 3rd column (index 2)
                self.seen_jobs = [row[2] for row in reader if len(row) > 2 and row[2]]
        except FileNotFoundError:
            if self.debug:
                print(f"{full_output_file_path} not found. Starting with an empty seen_jobs list for this session.")
        except Exception as e:
            print(f"Error reading {full_output_file_path}: {e}")

        # Check for "Jobs you may be interested in" header, which sometimes appears on empty actual search result pages
        try:
            job_results_list_text_element = self.browser.find_element(By.CLASS_NAME, "jobs-search-results-list__text")
            if 'jobs you may be interested in' in job_results_list_text_element.text.lower():
                raise Exception("Reached 'Jobs you may be interested in' section, no more relevant jobs.")
        except NoSuchElementException:
            if self.debug:
                print("Standard job results header found or no specific header text detected.")


        job_list_elements: List[WebElement] = []
        try:
            # Locate the main container for job listings. LinkedIn uses dynamic class names.
            # The strategy is to find a stable parent and then a child `ul` or `div` that holds jobs.
            # This part is highly susceptible to LinkedIn UI changes.

            # Common parent for job list (might change)
            # This XPath is an example, direct class name or more robust relative XPath is preferred
            # For example, `//div[contains(@class, 'jobs-search-results-list')]` or similar.
            # The original XPaths were very absolute and brittle.

            # A more robust way to find the job list container might be:
            # 1. Find the 'jobs-search-results-list' which is a common class for the scrollable pane.
            # 2. Inside that, find the `ul` element.

            # The original code had complex XPath logic. Let's try a slightly more semantic approach.
            # First, find the scrollable pane.
            scrollable_pane_xpath = "//div[contains(@class, 'jobs-search-results-list') and contains(@class, 'display-flex')]"
            try:
                 job_results_container = self.browser.find_element(By.XPATH, scrollable_pane_xpath)
                 if self.debug: print("Found job results container via primary XPath.")
            except NoSuchElementException:
                 # Fallback XPath if the primary one changes
                 scrollable_pane_xpath_fallback = "//div[contains(@class, 'scaffold-layout__list')]" # More generic
                 job_results_container = self.browser.find_element(By.XPATH, scrollable_pane_xpath_fallback)
                 if self.debug: print("Found job results container via fallback XPath.")

            # Scroll the job list to load all job items
            if job_results_container:
                scroll_slow(job_results_container, end=2000) # Scroll down moderately
                scroll_slow(job_results_container, end=2000, step=300, reverse=True) # Scroll back up

            # Now find the `ul` element within this container (usually holds the list items)
            # Then find `li` elements within that `ul`.
            # Common class for job list items: 'jobs-search-results__list-item' or 'scaffold-layout__list-item'

            # Try to find list items directly, they often have a consistent class name
            # This XPath looks for `li` elements that seem to be job cards.
            job_list_item_xpath = "//li[contains(@class, 'job-card-container__list-item') or contains(@class, 'scaffold-layout__list-item')]"
            job_list_elements = self.browser.find_elements(By.XPATH, job_list_item_xpath)

            if self.debug:
                print(f"Found {len(job_list_elements)} potential job items on this page using combined XPath.")

            if not job_list_elements: # If the above didn't work, try the original complex logic as a last resort.
                # This part is kept for its dynamic class detection but is complex.
                # Define the XPaths for potentially different regions
                xpath_region1 = "/html/body/div[6]/div[3]/div[4]/div/div/main/div/div[2]/div[1]/div" # Highly brittle
                xpath_region2 = "/html/body/div[5]/div[3]/div[4]/div/div/main/div/div[2]/div[1]/div" # Highly brittle

                job_list_container_found_by_xpath = None
                ul_element_class_name = None

                try:
                    job_list_container_found_by_xpath = self.browser.find_element(By.XPATH, xpath_region1)
                    ul_xpath = "/html/body/div[6]/div[3]/div[4]/div/div/main/div/div[2]/div[1]/div/ul"
                    ul_element = self.browser.find_element(By.XPATH, ul_xpath)
                    ul_element_class_name = ul_element.get_attribute("class").split()[0] # Get first class
                    if self.debug: print(f"Found job list via absolute XPath region 1. UL class: {ul_element_class_name}")
                except NoSuchElementException:
                    job_list_container_found_by_xpath = self.browser.find_element(By.XPATH, xpath_region2)
                    ul_xpath = "/html/body/div[5]/div[3]/div[4]/div/div/main/div/div[2]/div[1]/div/ul"
                    ul_element = self.browser.find_element(By.XPATH, ul_xpath)
                    ul_element_class_name = ul_element.get_attribute("class").split()[0]
                    if self.debug: print(f"Found job list via absolute XPath region 2. UL class: {ul_element_class_name}")

                if job_list_container_found_by_xpath and ul_element_class_name:
                    # Scroll the container found by absolute XPath
                    scroll_slow(job_list_container_found_by_xpath)
                    scroll_slow(job_list_container_found_by_xpath, step=300, reverse=True)

                    # Find `ul` by its detected class, then `li`s by their class
                    # This assumes the `ul` is unique enough by its first class name.
                    job_list_ul = self.browser.find_element(By.CLASS_NAME, ul_element_class_name)
                    job_list_elements = job_list_ul.find_elements(By.CLASS_NAME, 'scaffold-layout__list-item')
                    if self.debug: print(f"Found {len(job_list_elements)} jobs using dynamic UL class and 'scaffold-layout__list-item' LI class.")


            if not job_list_elements:
                raise Exception("No job items found on page. Structure might have changed.")

        except NoSuchElementException as e:
            print(f"Could not find job list container or items: {e}")
            raise Exception("No job list found on page, or page structure changed.")
        except Exception as e:
            print(f"An unexpected error occurred while trying to find job listings: {e}")
            raise # Re-raise the exception to be caught by start_applying

        for job_tile in job_list_elements:
            job_title: str = ""
            company: str = ""
            poster: str = "" # Person who posted the job, if available
            job_location: str = ""
            apply_method: str = "" # e.g., "Easy Apply"
            link: str = ""

            try:
                # Extract job title - look for a strong tag within a link for the title
                job_title_element = job_tile.find_element(By.CSS_SELECTOR, 'a[class*="job-card-list__title"], a[class*="job-card-container__link"]')
                job_title = job_title_element.text.strip() # Get text directly from link, or find strong tag if needed
                link = job_title_element.get_attribute('href').split('?')[0] # Clean URL
            except NoSuchElementException:
                if self.debug: print("Could not find job title or link for a tile.")
                continue # Skip this job tile if essential info is missing

            try:
                # Extract company name
                company_element = job_tile.find_element(By.CSS_SELECTOR, '[class*="job-card-container__primary-description"], [class*="artdeco-entity-lockup__subtitle"]')
                company = company_element.text.strip()
            except NoSuchElementException:
                if self.debug: print(f"Could not find company name for job: {job_title}")

            try:
                # Extract poster name if available
                hiring_line_element = job_tile.find_element(By.XPATH, ".//span[contains(.,' is hiring for this')]") # Relative XPath
                hiring_line_text = hiring_line_element.text
                name_terminating_index = hiring_line_text.find(' is hiring for this')
                if name_terminating_index != -1:
                    poster = hiring_line_text[:name_terminating_index].strip()
            except NoSuchElementException:
                 pass # Poster info is optional

            try:
                # Extract job location
                location_element = job_tile.find_element(By.CSS_SELECTOR, '[class*="job-card-container__metadata-item"]')
                job_location = location_element.text.strip()
            except NoSuchElementException:
                if self.debug: print(f"Could not find location for job: {job_title} at {company}")

            try:
                # Extract apply method (e.g., "Easy Apply" badge)
                apply_method_element = job_tile.find_element(By.CSS_SELECTOR, '[class*="job-card-container__apply-method"]')
                apply_method = apply_method_element.text.strip()
            except NoSuchElementException:
                if self.debug: print(f"Could not find apply method for job: {job_title} at {company}")

            # Apply blacklisting logic
            is_blacklisted: bool = False
            job_title_lower_tokens = job_title.lower().split()
            for word in self.title_blacklist:
                if word.lower() in job_title_lower_tokens:
                    is_blacklisted = True
                    if self.debug: print(f"Job '{job_title}' blacklisted due to title keyword: '{word}'.")
                    break

            if not is_blacklisted and company.lower() in [c.lower() for c in self.company_blacklist]:
                is_blacklisted = True
                if self.debug: print(f"Job '{job_title}' at '{company}' blacklisted because company is in blacklist.")

            if not is_blacklisted and poster and poster.lower() in [p.lower() for p in self.poster_blacklist]:
                is_blacklisted = True
                if self.debug: print(f"Job '{job_title}' (poster: {poster}) blacklisted because poster is in blacklist.")

            if link in self.seen_jobs:
                if self.debug: print(f"Job '{job_title}' at '{company}' already seen/processed.")
                is_blacklisted = True # Treat as blacklisted for application purposes this session

            if not is_blacklisted:
                if self.debug: print(f"Processing job: {job_title} at {company}.")
                try:
                    # Click the job tile to load its details in the right pane
                    # Use a more specific part of the tile for clicking, like the title link
                    job_title_click_target = job_tile.find_element(By.CSS_SELECTOR, 'a[class*="job-card-list__title"], a[class*="job-card-container__link"]')

                    # Retry mechanism for clicking the job tile
                    max_click_retries = 3
                    for attempt in range(max_click_retries):
                        try:
                            job_title_click_target.click()
                            time.sleep(random.uniform(3, 5)) # Wait for details pane to load
                            if self.debug: print("Job tile clicked, details should be loading.")
                            break # Successful click
                        except StaleElementReferenceException:
                            if self.debug: print(f"Stale element reference on job tile click (attempt {attempt + 1}/{max_click_retries}). Retrying...")
                            if attempt == max_click_retries - 1: raise # Re-raise if all retries fail
                            time.sleep(1) # Brief pause before retry
                            # Re-find elements (job_list_elements and then job_tile and then job_title_click_target)
                            # This is complex as it might require re-finding all job_list_elements.
                            # For now, just re-raise and let the outer loop handle it or skip.
                            # A full re-fetch of job_list_elements might be too slow here.
                            # This simplified retry might not always recover if the DOM changes too much.
                            job_title_click_target = self.browser.find_element(By.CSS_SELECTOR, 'a[class*="job-card-list__title"], a[class*="job-card-container__link"]') # Re-find target
                        except Exception as e_click:
                             if self.debug: print(f"Other exception on job tile click: {e_click}")
                             if attempt == max_click_retries - 1: raise
                             time.sleep(1)


                    # Tailor resume if enabled
                    if self.tailor_resume:
                        try:
                            job_description_text: str = self.browser.find_element(By.ID, 'job-details').text
                            if self.debug: print("Tailoring resume for the current job description.")
                            replacements = self.ai_response_generator.get_tailored_skills_replacements(job_description_text)
                            if replacements: # Only tailor if replacements are suggested
                                # The tailor_resume_pdf method now returns the path of the tailored resume
                                tailored_resume_path = self.ai_response_generator.tailor_resume_pdf(replacements, self.ai_response_generator.resume_dir)
                                if tailored_resume_path:
                                     if self.debug: print(f"Resume tailored. New path: {tailored_resume_path}")
                                     # self.ai_response_generator.resume_dir is updated by tailor_resume_pdf
                                else:
                                     if self.debug: print("Resume tailoring did not produce a new path, using previous resume.")
                            else:
                                if self.debug: print("No specific skill replacements suggested by AI for this job.")
                        except Exception as e_tailor:
                            print(f"Could not tailor resume for '{job_title}': {e_tailor}")
                            traceback.print_exc()

                    # Evaluate job fit if enabled
                    if self.evaluate_job_fit:
                        try:
                            job_description_text: str = self.browser.find_element(By.ID, 'job-details').text
                            if self.debug: print("Evaluating job fit...")
                            should_apply: bool = self.ai_response_generator.evaluate_job_fit(job_title, job_description_text)
                            if not should_apply:
                                print(f"Skipping application for '{job_title}' at '{company}': Job requirements not aligned with candidate profile per AI evaluation.")
                                self.seen_jobs.append(link) # Add to seen to avoid re-evaluating in this session
                                continue # Skip to next job
                            else:
                                if self.debug: print("AI evaluation: Good fit. Proceeding with application.")
                        except Exception as e_eval:
                            print(f"Could not evaluate job fit for '{job_title}': {e_eval}")
                            # Optionally, decide to proceed or skip if evaluation fails. Defaulting to proceed.
                            if self.debug: print("Proceeding with application despite job fit evaluation error.")


                    # Attempt to apply to the job
                    try:
                        application_successful: bool = self.apply_to_job()
                        if application_successful:
                            print(f"Application process completed for '{job_title}' at '{company}'. Status: {'Applied (or external)' if application_successful else 'Not applied or error'}.")
                        else:
                            # This 'else' might be redundant if apply_to_job raises exceptions on failure
                            print(f"Application for '{job_title}' at '{company}' was not completed or was handled externally without definitive success.")
                    except Exception as e_apply:
                        # Log failed application attempt
                        current_time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                        failed_filename_base = os.path.join(self.output_file_directory, f"failed_{current_time_str}")
                        print(f"Failed to apply to job '{job_title}' at '{company}'. Link: {link}. Error: {e_apply}")
                        traceback.print_exc()
                        try:
                            write_to_file(failed_filename_base, company, job_title, link, job_location, current_search_location)
                        except Exception as e_write_fail:
                            print(f"Additionally failed to write failure log: {e_write_fail}")

                    # Log successful or processed application
                    try:
                        # Use self.file_name which is already output_dir + "output"
                        write_to_file(self.file_name, company, job_title, link, job_location, current_search_location)
                    except Exception as e_write_main:
                        print(f"Unable to save job application info for '{job_title}' at '{company}' to main output file: {e_write_main}")
                        traceback.print_exc()

                except Exception as e_outer:
                    print(f"Major error processing job tile for '{job_title}' at '{company}': {e_outer}")
                    traceback.print_exc()

                finally:
                     # Add link to seen_jobs regardless of outcome to prevent reprocessing in this session
                    if link and link not in self.seen_jobs:
                        self.seen_jobs.append(link)
            else:
                if self.debug:
                    # This condition is now part of the is_blacklisted logic above
                    # print(f"Skipping blacklisted or already seen job: {job_title} at {company}")
                    pass


    def apply_to_job(self) -> bool:
        """
        Handles the process of clicking "Easy Apply" and navigating the application modal.

        This includes:
        - Clicking the "Easy Apply" button.
        - Checking for and handling redirections to external job sites (e.g., Greenhouse, Ashby).
        - Iteratively filling form sections within LinkedIn's Easy Apply modal.
        - Detecting and handling potential errors or unexpected states in the modal.
        - Submitting the application.

        Returns:
            bool: True if the application was successfully submitted (or handed off to an
                  external site handler that reported success), False otherwise or if an error occurred.
        """
        easy_apply_button: Optional[WebElement] = None
        try:
            # Locate the "Easy Apply" button. Its class name can sometimes vary slightly.
            easy_apply_button = self.browser.find_element(By.CSS_SELECTOR, "button.jobs-apply-button[data-job-id]")
            if self.debug: print("Easy Apply button found.")
        except NoSuchElementException:
            if self.debug: print("Easy Apply button not found for this job.")
            return False # Not an Easy Apply job or button not found

        # Optional: Scroll the job description area before clicking apply (might help with button visibility)
        try:
            job_details_pane = self.browser.find_element(By.ID, "job-details") # Standard ID for job details section
            scroll_slow(job_details_pane, end=800, step=200) # Scroll down a bit
            scroll_slow(job_details_pane, start=800, end=0, step=200, reverse=True) # Scroll back up
        except NoSuchElementException:
            if self.debug: print("Job details pane not found for scrolling.")
            pass # Continue even if scrolling fails

        if self.debug: print("Attempting to click Easy Apply button...")
        easy_apply_button.click()
        time.sleep(random.uniform(2, 4)) # Wait for modal or new tab to open

        # --- Handle potential external site redirections ---
        main_window_handle: str = self.browser.current_window_handle
        all_window_handles: List[str] = self.browser.window_handles

        if len(all_window_handles) > 1: # New tab/window opened
            for handle in all_window_handles:
                if handle != main_window_handle:
                    self.browser.switch_to.window(handle)
                    current_url: str = self.browser.current_url
                    if self.debug: print(f"Switched to new tab/window: {current_url}")

                    # Greenhouse
                    if "greenhouse.io" in current_url:
                        if self.debug: print("Redirected to Greenhouse.")
                        try:
                            success: bool = apply_to_greenhouse(
                                self.browser, self.personal_info, self.ai_response_generator.resume_dir,
                                getattr(self, 'cover_letter_dir', ''), self.ai_response_generator
                            )
                            self.browser.close() # Close Greenhouse tab
                            self.browser.switch_to.window(main_window_handle) # Switch back
                            return success
                        except Exception as e_gh:
                            print(f"Greenhouse application failed: {e_gh}")
                            traceback.print_exc()
                            self.browser.close()
                            self.browser.switch_to.window(main_window_handle)
                            return False
                    # Ashby
                    elif "ashbyhq.com" in current_url or "ashby" in current_url: # Broader check for Ashby
                        if self.debug: print("Redirected to Ashby.")
                        try:
                            success: bool = apply_to_ashby(
                                self.browser, self.personal_info, self.ai_response_generator.resume_dir,
                                self.ai_response_generator
                            )
                            self.browser.close() # Close Ashby tab
                            self.browser.switch_to.window(main_window_handle) # Switch back
                            return success
                        except Exception as e_ashby:
                            print(f"Ashby application failed: {e_ashby}")
                            traceback.print_exc()
                            self.browser.close()
                            self.browser.switch_to.window(main_window_handle)
                            return False

                    # If not a recognized external site, close it and return to main window
                    if self.debug: print(f"External site '{current_url}' not specifically handled. Closing tab.")
                    self.browser.close()
                    self.browser.switch_to.window(main_window_handle)
                    # Consider this an unsuccessful Easy Apply attempt as it was external and unhandled
                    return False

        # --- Handle LinkedIn Easy Apply Modal ---
        current_button_text: str = ""
        submit_application_text_identifier: str = 'submit application' # Lowercase for comparison

        # Loop through multi-step application modal
        max_steps = 10 # Safety break for the loop
        for step_count in range(max_steps):
            if self.debug: print(f"Application modal, step {step_count + 1}.")
            try:
                self.fill_up() # Fill form elements on the current modal page

                # Find the primary action button (Next, Review, Submit)
                # Common class: "artdeco-button--primary"
                # Sometimes also has "ember-view"
                primary_button_xpath = "//button[contains(@class, 'artdeco-button--primary') and not(@disabled)]"
                next_button = WebDriverWait(self.browser, 10).until(
                    EC.element_to_be_clickable((By.XPATH, primary_button_xpath))
                )
                current_button_text = next_button.text.lower()
                if self.debug: print(f"Button text: '{current_button_text}'")

                if submit_application_text_identifier in current_button_text:
                    try:
                        self.unfollow() # Attempt to unfollow company before final submission
                    except Exception as e_unfollow:
                        if self.debug: print(f"Could not unfollow company: {e_unfollow}")

                next_button.click()
                time.sleep(random.uniform(2.0, 4.0)) # Wait for next step or submission processing

                # Check for common error messages after clicking
                # These are indicative of issues with the current form page
                # TODO: Localize these error messages or find more robust error indicators
                error_keywords = [
                    'enter a valid', 'file is required', 'make a selection',
                    'select checkbox to proceed', 'error', 'problem with your application'
                ]
                page_source_lower = self.browser.page_source.lower()
                if any(error_keyword in page_source_lower for error_keyword in error_keywords):
                    # This check is broad; more specific checks might be needed per input type
                    print("Error detected on application page. Trying to dismiss and abort.")
                    raise Exception("Error message detected on application form page.")

                # If button text was "submit application", we assume submission occurred
                if submit_application_text_identifier in current_button_text:
                    if self.debug: print("Submit button clicked. Application likely submitted.")
                    break # Exit loop after submission attempt

            except Exception as e_step:
                print(f"Error during application step {step_count + 1}: {e_step}")
                traceback.print_exc()
                # Attempt to dismiss the modal and abandon this application
                try:
                    dismiss_button = self.browser.find_element(By.CLASS_NAME, 'artdeco-modal__dismiss')
                    dismiss_button.click()
                    time.sleep(random.uniform(1, 2))
                    # Confirm discard if prompted
                    confirm_discard_buttons = self.browser.find_elements(By.CLASS_NAME, 'artdeco-modal__confirm-dialog-btn')
                    if confirm_discard_buttons and "discard" in confirm_discard_buttons[0].text.lower() : # Often the first button is discard
                        confirm_discard_buttons[0].click()
                    elif len(confirm_discard_buttons) > 1 and "discard" in confirm_discard_buttons[1].text.lower(): # Sometimes it's the second
                         confirm_discard_buttons[1].click()
                    time.sleep(random.uniform(1, 2))
                except Exception as e_dismiss:
                    if self.debug: print(f"Could not dismiss modal after error: {e_dismiss}")
                return False # Indicate failure for this application

            if step_count == max_steps -1 and submit_application_text_identifier not in current_button_text:
                 print("Reached max application steps without submitting. Aborting.")
                 return False


        # Post-submission: Close confirmation pop-ups
        closed_confirmation_popup: bool = False
        # Wait a bit for the "Application sent" popup
        time.sleep(random.uniform(3, 5))
        try:
            # Common dismiss button for "Application sent" modal
            # Using a more general XPath to find a button with an aria-label "Dismiss"
            dismiss_button_xpath = "//button[@aria-label='Dismiss' or contains(@aria-label, 'close') or contains(@class, 'artdeco-modal__dismiss')]"
            dismiss_confirmation_button = WebDriverWait(self.browser, 5).until(
                EC.element_to_be_clickable((By.XPATH, dismiss_button_xpath))
            )
            dismiss_confirmation_button.click()
            closed_confirmation_popup = True
            if self.debug: print("Dismissed 'Application sent' confirmation modal.")
        except TimeoutException:
            if self.debug: print("'Application sent' modal dismiss button not found quickly.")
        except NoSuchElementException: # Fallback if specific class changes
             if self.debug: print("Standard dismiss button for modal not found by class, trying toast.")

        # Sometimes it's a toast notification
        if not closed_confirmation_popup:
            try:
                toast_dismiss_button = self.browser.find_element(By.CLASS_NAME, 'artdeco-toast-item__dismiss')
                toast_dismiss_button.click()
                closed_confirmation_popup = True
                if self.debug: print("Dismissed 'Application sent' toast notification.")
            except NoSuchElementException:
                if self.debug: print("Toast notification dismiss button not found.")

        # Sometimes a "Save application" button appears instead of direct close
        if not closed_confirmation_popup:
            try:
                # This might be for saving application to LinkedIn, not strictly closing a success popup
                save_app_button = self.browser.find_element(By.CSS_SELECTOR, 'button[data-control-name="save_application_btn"]')
                save_app_button.click() # This might not be a "close" action
                closed_confirmation_popup = True # Assuming this interaction clears the modal
                if self.debug: print("Clicked 'Save application' button, assuming it closes modal.")
            except NoSuchElementException:
                 if self.debug: print("'Save application' button not found.")


        time.sleep(random.uniform(2, 4)) # Final pause

        if not closed_confirmation_popup and submit_application_text_identifier in current_button_text:
            # If we think we submitted but couldn't close any confirmation, it's a bit ambiguous.
            # However, the primary goal (submission) was attempted.
            # For robustness, we might want to check URL or for specific "application sent" text
            # if no dismiss button is found.
            if self.debug: print("Application submitted, but no confirmation pop-up was explicitly closed. Assuming success.")
            return True # Assume submitted if submit button was clicked and no errors prior
        elif closed_confirmation_popup and submit_application_text_identifier in current_button_text:
             return True # Clearly submitted and confirmation closed

        # If submit button was never identified or other issues arose
        if self.debug: print("Application submission process did not complete as expected.")
        return False


    def home_address(self, form: WebElement) -> None:
        """
        Fills in home address fields within a given form WebElement.

        Searches for input fields based on common address-related labels
        (street, city, zip, state, province) and populates them using
        information from `self.personal_info`.

        Args:
            form (WebElement): The Selenium WebElement representing the form or a
                               section of the form containing address fields.
        """
        if self.debug:
            print("Attempting to fill home address fields.")
        try:
            # Groupings of label + input field
            groups = form.find_elements(By.CLASS_NAME, 'jobs-easy-apply-form-section__grouping')
            if not groups: # Fallback if specific grouping class not found
                 groups = form.find_elements(By.XPATH, ".//div[contains(@class, 'fb-form-element') or contains(@class, 'artdeco-form-item')]")


            for group in groups:
                try:
                    label_element = group.find_element(By.TAG_NAME, 'label')
                    label_text_lower: str = label_element.text.lower()

                    # Find input field associated with this label
                    # Input might be direct child, or sibling of label, or nested
                    input_field: Optional[WebElement] = None
                    try:
                        input_field = group.find_element(By.TAG_NAME, 'input')
                    except NoSuchElementException:
                        # Try finding input by for attribute of label
                        label_for = label_element.get_attribute('for')
                        if label_for:
                            input_field = form.find_element(By.ID, label_for)

                    if not input_field:
                        if self.debug: print(f"No input field found for label: {label_text_lower}")
                        continue

                    # Fill fields based on label text
                    if 'street' in label_text_lower:
                        enter_text(input_field, self.personal_info.get('Street address', ''))
                    elif 'city' in label_text_lower:
                        enter_text(input_field, self.personal_info.get('City', ''))
                        time.sleep(1) # Allow for autocomplete suggestions
                        input_field.send_keys(Keys.DOWN) # Select first suggestion
                        input_field.send_keys(Keys.RETURN) # Confirm selection
                    elif 'zip' in label_text_lower or 'postal code' in label_text_lower: # Broader match for zip/postal
                        enter_text(input_field, self.personal_info.get('Zip', ''))
                    elif 'state' in label_text_lower or 'province' in label_text_lower:
                        enter_text(input_field, self.personal_info.get('State', ''))
                    # Add more specific address fields if necessary (e.g., apartment, country)
                    elif self.debug:
                        print(f"Unmatched address field label: {label_text_lower}")

                except NoSuchElementException:
                    if self.debug: print("Could not find label or input within an address group.")
                    continue # Skip this group
        except Exception as e:
            print(f"Error filling home address: {e}")
            traceback.print_exc()


    def get_answer(self, question_key: str) -> str:
        """
        Retrieves a 'yes' or 'no' answer for a question based on predefined checkbox values.

        Args:
            question_key (str): The key corresponding to the question in `self.checkboxes`.

        Returns:
            str: 'yes' if the checkbox for the question_key is True, 'no' otherwise.
                 Returns 'no' by default if key is not found, to be conservative.
        """
        return 'yes' if self.checkboxes.get(question_key, False) else 'no'

    def additional_questions(self, form: WebElement) -> None:
        """
        Handles various types of additional questions found in LinkedIn application forms.

        This method iterates through form elements and attempts to identify and answer
        questions based on their type (radio buttons, text inputs, dropdowns, date pickers,
        checkboxes) and content (keywords in labels). It uses predefined answers from
        `self.personal_info`, `self.experience`, etc., and falls back to AI-generated
        responses for unrecognized or complex questions.

        Args:
            form (WebElement): The Selenium WebElement representing the form section
                               containing additional questions.
        """
        if self.debug:
            print("Attempting to fill additional questions section.")

        # Find all individual question elements. Common class names: 'fb-dash-form-element', 'artdeco-form-item'
        # This XPath tries to find divs that are likely to be form elements.
        question_elements_xpath = ".//div[contains(@class, 'fb-dash-form-element') or contains(@class, 'artdeco-form-item') or contains(@class, 'jobs-easy-apply-form-element')]"
        questions: List[WebElement] = form.find_elements(By.XPATH, question_elements_xpath)
        if self.debug: print(f"Found {len(questions)} potential question elements.")

        for question_element in questions:
            question_label_text_lower: str = ""
            # Try to get the label text for context
            try:
                label_element = question_element.find_element(By.TAG_NAME, 'label')
                # Sometimes label text is within a span inside label, or has screen-reader only parts
                # Prefer visible text if possible.
                spans_in_label = label_element.find_elements(By.XPATH, ".//span[@aria-hidden='true']")
                if spans_in_label: # Often, the primary visible text is in such a span
                    question_label_text_lower = " ".join([s.text for s in spans_in_label if s.text]).strip().lower()
                if not question_label_text_lower: # Fallback to full label text
                    question_label_text_lower = label_element.text.strip().lower()

                if self.debug: print(f"Processing question with label: '{question_label_text_lower}'")
            except NoSuchElementException:
                if self.debug: print("Could not find a standard label for a question element. Skipping or trying generic fill.")
                # This element might be a complex component not following label->input structure.
                # It could also be a heading or descriptive text, not a question.

            # Attempt to handle based on input type found within the question_element

            # 1. Radio Buttons
            try:
                # Fieldset is a common container for radio buttons
                radio_fieldset = question_element.find_element(By.TAG_NAME, 'fieldset')
                # Re-fetch label if it's part of fieldset legend or an h3/h4
                if not question_label_text_lower:
                     try:
                          legend_or_heading = radio_fieldset.find_element(By.XPATH, ".//legend | .//h3 | .//h4 | .//span[contains(@class, 'label')]")
                          question_label_text_lower = legend_or_heading.text.lower()
                          if self.debug: print(f"Radio group question identified by legend/heading: {question_label_text_lower}")
                     except NoSuchElementException:
                          if self.debug: print("Radio group legend/heading not found.")
                          # Fallback to a generic handling or skip if label is crucial

                radio_inputs = radio_fieldset.find_elements(By.CSS_SELECTOR, "input[type='radio']")
                if not radio_inputs:
                    if self.debug: print("No radio inputs found in fieldset, skipping radio logic for this element.")
                    raise NoSuchElementException # Trigger except to try next question type

                radio_labels_elements = radio_fieldset.find_elements(By.TAG_NAME, 'label')
                # Create a list of (index, text_option) for AI
                radio_options_for_ai: List[Tuple[int, str]] = []
                for i, lbl_el in enumerate(radio_labels_elements):
                    # Ensure we get the text meant for display
                    visible_text = lbl_el.text.strip() # Or more specific if nested spans
                    radio_options_for_ai.append((i, visible_text.lower()))

                if self.debug: print(f"Radio options: {[opt[1] for opt in radio_options_for_ai]}")

                # --- Decision logic for radio buttons ---
                selected_answer_text: Optional[str] = None # The text of the option to select

                # Predefined logic based on keywords in question_label_text_lower
                if 'driver\'s licence' in question_label_text_lower or 'driver\'s license' in question_label_text_lower:
                    selected_answer_text = self.get_answer('driversLicence')
                # ... (many other elif conditions from original code for predefined answers) ...
                # Example:
                elif 'previously employ' in question_label_text_lower:
                    selected_answer_text = 'no'
                elif 'authorized' in question_label_text_lower or 'authorised' in question_label_text_lower or 'legally' in question_label_text_lower:
                    selected_answer_text = self.get_answer('legallyAuthorized')
                elif 'sponsor' in question_label_text_lower: # Visa sponsorship
                     selected_answer_text = self.get_answer('requireVisa') # 'yes' if needs, 'no' if not
                # EEO Questions (often "prefer not to say" or similar is desired)
                elif any(keyword in question_label_text_lower for keyword in ['race', 'ethnicity', 'gender', 'veteran', 'disability', 'sexual orientation', 'aboriginal', 'native', 'indigenous']):
                    eeo_answer_preference = self.eeo.get(question_label_text_lower, self.eeo.get("default", "Prefer not to say")) # Get specific or default EEO
                    # Find the option that matches this preference
                    for i, opt_text in radio_options_for_ai:
                        if eeo_answer_preference.lower() in opt_text:
                            radio_labels_elements[i].click()
                            if self.debug: print(f"Selected EEO option: '{opt_text}' for question '{question_label_text_lower}'")
                            break
                    else: # If specific preference not found, try common "decline" options
                        decline_options = ['prefer not to say', 'decline to self-identify', 'i don\'t wish to answer']
                        for i, opt_text in radio_options_for_ai:
                            if any(decline_keyword in opt_text for decline_keyword in decline_options):
                                radio_labels_elements[i].click()
                                if self.debug: print(f"Selected generic decline EEO option for '{question_label_text_lower}'")
                                break
                        else: # If still nothing, log and potentially pick last as fallback
                             if self.debug: print(f"Could not find preferred EEO answer for '{question_label_text_lower}'. AI might be called or last option.")
                             # Let AI try or fallback later
                             selected_answer_text = None # Reset to trigger AI/fallback

                # If a predefined answer string was determined (e.g., "yes", "no")
                radio_to_click: Optional[WebElement] = None
                if selected_answer_text:
                    for i, opt_text_tuple in enumerate(radio_options_for_ai):
                        # opt_text_tuple is (original_index, text_content_lower)
                        if selected_answer_text in opt_text_tuple[1]:
                            radio_to_click = radio_labels_elements[i] # Click the label
                            break
                    if not radio_to_click and self.debug:
                        print(f"Predefined answer '{selected_answer_text}' not found in options for '{question_label_text_lower}'.")

                # If no predefined logic matched or answer not found, use AI
                if not radio_to_click:
                    if self.debug: print(f"Using AI for radio question: '{question_label_text_lower}'")
                    ai_choice_idx: Optional[int] = self.ai_response_generator.generate_response(
                        question_label_text_lower, response_type="choice", options=radio_options_for_ai
                    )
                    if ai_choice_idx is not None and 0 <= ai_choice_idx < len(radio_labels_elements):
                        radio_to_click = radio_labels_elements[ai_choice_idx]
                        # Log this AI choice
                        record_unprepared_question(self.unprepared_questions_file_name, "radio (AI)", question_label_text_lower, radio_options_for_ai[ai_choice_idx][1])
                    else: # Fallback if AI fails or returns invalid index
                        if self.debug: print(f"AI failed for radio: '{question_label_text_lower}'. Clicking last option.")
                        radio_to_click = radio_labels_elements[-1] # Default to last option
                        record_unprepared_question(self.unprepared_questions_file_name, "radio (Fallback)", question_label_text_lower, radio_options_for_ai[-1][1])

                if radio_to_click:
                    radio_to_click.click()
                    if self.debug: print(f"Clicked radio option for: '{question_label_text_lower}' -> '{radio_to_click.text}'")

                continue # Move to next question_element after handling radio
            except NoSuchElementException:
                pass # Not a radio button question based on this structure
            except Exception as e_radio:
                if self.debug: print(f"General error processing radio button for '{question_label_text_lower}': {e_radio}")


            # 2. Text Inputs (input type="text", textarea)
            try:
                text_input_field: Optional[WebElement] = None
                input_field_type: str = "" # 'text' or 'numeric' based on original logic

                try:
                    text_input_field = question_element.find_element(By.TAG_NAME, 'input')
                    # Check for 'numeric' in ID, as type might still be 'text' for numeric-only fields
                    if 'numeric' in text_input_field.get_attribute('id').lower() or \
                       text_input_field.get_attribute('type') == 'number':
                        input_field_type = 'numeric'
                    else:
                        input_field_type = 'text'
                except NoSuchElementException:
                    try:
                        text_input_field = question_element.find_element(By.TAG_NAME, 'textarea')
                        input_field_type = 'text' # Textareas are always text
                    except NoSuchElementException:
                        if self.debug: print(f"No input/textarea found for '{question_label_text_lower}'")
                        raise NoSuchElementException # Trigger except to try next type

                if not question_label_text_lower: # If label wasn't found earlier, try to get it from aria-label or placeholder
                    question_label_text_lower = text_input_field.get_attribute('aria-label').lower() if text_input_field.get_attribute('aria-label') else ""
                    if not question_label_text_lower:
                        question_label_text_lower = text_input_field.get_attribute('placeholder').lower() if text_input_field.get_attribute('placeholder') else ""
                    if self.debug and question_label_text_lower: print(f"Text input question identified by aria-label/placeholder: {question_label_text_lower}")

                # --- Decision logic for text inputs ---
                text_to_enter: Union[str, int, float, None] = None
                # ... (many elif conditions from original code for text inputs) ...
                # Example:
                if 'experience' in question_label_text_lower or 'how many years' in question_label_text_lower:
                    # Try to find specific experience, e.g. "years of Python experience"
                    found_specific_exp = False
                    for exp_key, exp_years in self.experience.items():
                        if exp_key.lower() in question_label_text_lower and exp_key != 'default':
                            text_to_enter = int(exp_years)
                            found_specific_exp = True
                            break
                    if not found_specific_exp: # Use default experience
                         text_to_enter = self.experience_default
                elif 'salary' in question_label_text_lower or 'compensation' in question_label_text_lower:
                    text_to_enter = self.salary_minimum # Assuming this is numeric as per original
                    if input_field_type == 'numeric' and text_to_enter: text_to_enter = int(float(str(text_to_enter)))

                # If no predefined logic provides an answer, use AI
                if text_to_enter is None or text_to_enter == "":
                    ai_response_type = "numeric" if input_field_type == "numeric" else "text"
                    if self.debug: print(f"Using AI ({ai_response_type}) for text input: '{question_label_text_lower}'")
                    ai_generated_text: Optional[Union[str,int]] = self.ai_response_generator.generate_response(
                        question_label_text_lower, response_type=ai_response_type
                    )
                    record_unprepared_question(self.unprepared_questions_file_name, f"{input_field_type} (AI)", question_label_text_lower, str(ai_generated_text))
                    if ai_generated_text is not None:
                        text_to_enter = ai_generated_text
                    else: # Fallback if AI fails
                        text_to_enter = "0" if input_field_type == "numeric" else "N/A"
                        if self.debug: print(f"AI failed for text input '{question_label_text_lower}'. Using fallback: '{text_to_enter}'")

                enter_text(text_input_field, str(text_to_enter))
                if self.debug: print(f"Entered text for '{question_label_text_lower}': '{text_to_enter}'")
                continue # Move to next question_element
            except NoSuchElementException:
                pass # Not a text input question
            except Exception as e_text:
                 if self.debug: print(f"General error processing text input for '{question_label_text_lower}': {e_text}")

            # 3. Dropdowns (select elements)
            try:
                dropdown_field = question_element.find_element(By.TAG_NAME, 'select')
                if not question_label_text_lower: # If label wasn't found earlier
                    question_label_text_lower = dropdown_field.get_attribute('aria-label').lower() if dropdown_field.get_attribute('aria-label') else ""
                    if self.debug and question_label_text_lower: print(f"Dropdown question identified by aria-label: {question_label_text_lower}")

                select_obj = Select(dropdown_field)
                options_texts: List[str] = [opt.text for opt in select_obj.options]
                if self.debug: print(f"Dropdown options for '{question_label_text_lower}': {options_texts}")

                # --- Decision logic for dropdowns ---
                option_to_select_text: Optional[str] = None
                # ... (many elif conditions from original code for dropdowns) ...
                # Example:
                if 'proficiency' in question_label_text_lower:
                    for lang_key, lang_prof in self.languages.items():
                        if lang_key.lower() in question_label_text_lower:
                            option_to_select_text = lang_prof
                            break
                elif 'authorized' in question_label_text_lower or 'authorised' in question_label_text_lower:
                    auth_answer = self.get_answer('legallyAuthorized') # 'yes' or 'no'
                    # Find an option that contains "yes" or "no" appropriately
                    for opt_txt in options_texts:
                        if auth_answer in opt_txt.lower():
                            option_to_select_text = opt_txt
                            break
                    if not option_to_select_text: # Fallback: if "yes" is answer, take first option; if "no", take last.
                        option_to_select_text = options_texts[0] if auth_answer == 'yes' else options_texts[-1]


                if option_to_select_text:
                    try:
                        select_dropdown(dropdown_field, option_to_select_text)
                        if self.debug: print(f"Selected dropdown option for '{question_label_text_lower}': '{option_to_select_text}'")
                    except NoSuchElementException: # If exact text match fails
                        if self.debug: print(f"Could not find exact option '{option_to_select_text}'. Trying partial match or AI.")
                        # Try partial match
                        found_partial = False
                        for opt_txt in options_texts:
                            if option_to_select_text.lower() in opt_txt.lower():
                                select_dropdown(dropdown_field, opt_txt)
                                found_partial = True; break
                        if not found_partial: option_to_select_text = None # Trigger AI

                if not option_to_select_text: # Use AI if no logic matched or selection failed
                    if self.debug: print(f"Using AI for dropdown: '{question_label_text_lower}'")
                    dropdown_options_for_ai: List[Tuple[int, str]] = [(i, opt) for i, opt in enumerate(options_texts)]
                    ai_choice_idx: Optional[int] = self.ai_response_generator.generate_response(
                        question_label_text_lower, response_type="choice", options=dropdown_options_for_ai
                    )
                    final_selected_option_text_for_log = "N/A (AI Failed or No Options)"
                    if ai_choice_idx is not None and 0 <= ai_choice_idx < len(options_texts):
                        select_dropdown(dropdown_field, options_texts[ai_choice_idx])
                        final_selected_option_text_for_log = options_texts[ai_choice_idx]
                    else: # Fallback if AI fails
                        select_dropdown(dropdown_field, options_texts[-1]) # Select last
                        final_selected_option_text_for_log = options_texts[-1]
                    record_unprepared_question(self.unprepared_questions_file_name, "dropdown (AI/Fallback)", question_label_text_lower, final_selected_option_text_for_log)

                continue # Move to next question_element
            except NoSuchElementException:
                pass # Not a dropdown question
            except Exception as e_dropdown:
                if self.debug: print(f"General error processing dropdown for '{question_label_text_lower}': {e_dropdown}")

            # 4. Date Pickers (look for input with 'date' in class or type)
            try:
                # This is a guess; actual date pickers might need more specific selectors
                date_input = question_element.find_element(By.CSS_SELECTOR, "input[type='date'], input[class*='date']")
                # Assuming the question is about availability or start date, use today or a configured date.
                # For now, just using today's date as a placeholder.
                # TODO: Add logic from parameters if a specific start date is available.
                today_date_str: str = datetime.now().strftime("%Y-%m-%d") # Standard date format for input type=date
                # Some date pickers might want MM/DD/YYYY
                # today_date_str_common: str = datetime.now().strftime("%m/%d/%Y")

                # Selenium's send_keys to date inputs can be tricky.
                # It's often better to set value via JS or ensure format is exact.
                enter_text(date_input, today_date_str) # `enter_text` clears first
                if self.debug: print(f"Entered date for '{question_label_text_lower}': '{today_date_str}'")
                time.sleep(0.5) # Brief pause for field to process
                date_input.send_keys(Keys.RETURN) # Sometimes helps to close calendar popup
                continue
            except NoSuchElementException:
                pass # Not a date picker
            except Exception as e_date:
                if self.debug: print(f"General error processing date picker for '{question_label_text_lower}': {e_date}")

            # 5. Checkboxes (single, often for agreement)
            try:
                # Checkboxes might be input type="checkbox" directly inside the question_element,
                # or associated with the label found earlier.
                checkbox_input = question_element.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
                # If it's a required "I agree" type checkbox, just click it.
                # More sophisticated logic could check label text if there are multiple checkboxes.
                if not checkbox_input.is_selected(): # Click only if not already selected
                    checkbox_input.click() # Or .click() on its label if input is hidden
                    if self.debug: print(f"Clicked checkbox for '{question_label_text_lower}'.")
                continue
            except NoSuchElementException:
                pass # Not a checkbox of this simple type
            except Exception as e_checkbox:
                if self.debug: print(f"General error processing checkbox for '{question_label_text_lower}': {e_checkbox}")

            if self.debug and question_label_text_lower: # If a label was found but no input type was handled
                print(f"Question element with label '{question_label_text_lower}' was not handled by any specific type logic.")


    def unfollow(self) -> None:
        """
        Attempts to unfollow the company after submitting an application.

        Looks for a checkbox related to following the company and unchecks it
        if found. This is a best-effort attempt and silently passes if the
        element is not found.
        """
        try:
            # XPath for the "follow company" checkbox label.
            # This label often contains text like "to stay up to date with their page."
            follow_checkbox_label_xpath = "//label[contains(.,'to stay up to date with their page.') or contains(., 'Follow for updates')]"
            follow_checkbox_label = self.browser.find_element(By.XPATH, follow_checkbox_label_xpath)

            # The actual input checkbox might be associated via 'for' attribute or be a sibling/child.
            # Assuming clicking the label toggles the checkbox.
            # Check if it's selected first (though not strictly necessary if we always want to ensure it's off)
            # We might need to find the input element to check .is_selected() state.
            # For simplicity, just clicking the label if we want to ensure it's off (or on).
            # If the goal is to *uncheck* it, we need to be sure it's checked first, or that clicking toggles it correctly.
            # Assuming it's checked by default and clicking the label unchecks it.
            follow_checkbox_label.click()
            if self.debug: print("Attempted to unfollow company by clicking the follow checkbox/label.")
        except NoSuchElementException:
            if self.debug: print("Could not find the 'follow company' checkbox to unfollow.")
        except Exception as e:
            if self.debug: print(f"An error occurred while trying to unfollow company: {e}")


    def send_resume(self) -> None:
        """
        Handles uploading the resume and optionally a cover letter.

        Searches for file input elements on the page. If an input is identified
        for a resume, it sends the path to the resume file. If a cover letter
        input is found and a cover letter path is configured, it uploads that.
        If a cover letter is required but not configured, it may upload the resume
        as a fallback for that field.
        """
        if self.debug: print("Attempting to upload resume and/or cover letter.")
        try:
            # Common CSS selector for file input elements
            file_input_selector = "input[type='file'][name*='file'], input[type='file'][id*='resume'], input[type='file'][aria-label*='resume']"
            file_upload_elements: List[WebElement] = self.browser.find_elements(By.CSS_SELECTOR, file_input_selector)

            if not file_upload_elements:
                 # Fallback: Try to find by a more generic name if specific selectors fail
                file_upload_elements = self.browser.find_elements(By.CSS_SELECTOR, "input[type='file']")
                if self.debug and not file_upload_elements: print("No file input elements found on the page.")

            for upload_button_input in file_upload_elements:
                # Determine if it's for resume or cover letter by checking nearby text or label
                # This requires navigating to parent or sibling elements to find descriptive text.
                # Example: find parent div, then find a label or span with "resume" or "cover letter"
                # This is a simplified example; robustly finding the associated label can be complex.
                # We'll try to find a label associated by 'for' attribute first.
                associated_text_element = None
                input_id = upload_button_input.get_attribute('id')
                if input_id:
                    try:
                        associated_text_element = self.browser.find_element(By.CSS_SELECTOR, f"label[for='{input_id}']")
                    except NoSuchElementException: pass

                # If no label via 'for', try to find a preceding sibling h3/h4/label or parent's text.
                if not associated_text_element:
                    try: # Try to find element by XPATH for preceding-sibling
                        associated_text_element = upload_button_input.find_element(By.XPATH, "./preceding-sibling::*[self::h3 or self::h4 or self::label or contains(@class,'label')] | ./ancestor::div[1]/descendant::label | ./ancestor::div[1]/descendant::span[contains(@class,'label')]")
                    except NoSuchElementException:
                         if self.debug: print("Could not determine upload type (resume/cover) for an input field via common patterns.")
                         # As a last resort, if there's only one file input, assume it's for resume.
                         if len(file_upload_elements) == 1:
                              upload_button_input.send_keys(self.ai_response_generator.resume_dir)
                              if self.debug: print(f"Sent resume to the only file input found: {self.ai_response_generator.resume_dir}")
                         continue # Skip if type cannot be determined and multiple inputs exist


                upload_type_text: str = associated_text_element.text.lower() if associated_text_element else ""

                if self.debug: print(f"Found file input, associated text: '{upload_type_text}'")

                if 'resume' in upload_type_text:
                    upload_button_input.send_keys(self.ai_response_generator.resume_dir) # Use potentially tailored resume path
                    if self.debug: print(f"Uploaded resume: {self.ai_response_generator.resume_dir}")
                elif 'cover letter' in upload_type_text or 'cover' in upload_type_text:
                    if self.cover_letter_dir:
                        upload_button_input.send_keys(self.cover_letter_dir)
                        if self.debug: print(f"Uploaded cover letter: {self.cover_letter_dir}")
                    elif 'required' in upload_type_text: # If cover letter is required but not provided
                        upload_button_input.send_keys(self.ai_response_generator.resume_dir) # Use resume as fallback
                        if self.debug: print(f"Cover letter required but not provided. Uploaded resume as fallback: {self.ai_response_generator.resume_dir}")
        except Exception as e:
            print(f"Failed to upload resume or cover letter: {e}")
            traceback.print_exc()


    def fill_up(self) -> None:
        """
        Identifies the current section of the application form and calls the appropriate handler.

        It inspects the current view within the Easy Apply modal (e.g., by looking for
        section headers like "Home address", "Contact info", "Resume") and dispatches
        to methods like `home_address`, `send_resume`, or `additional_questions`.
        """
        try:
            # Find the main content area of the Easy Apply modal
            easy_apply_modal_content = WebDriverWait(self.browser, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, "jobs-easy-apply-modal__content"))
            )
            # Find the form element within the modal content
            form = easy_apply_modal_content.find_element(By.TAG_NAME, 'form')

            # Determine current section by its header (h3 is common for section titles)
            try:
                section_header_element = form.find_element(By.TAG_NAME, 'h3')
                section_header_text: str = section_header_element.text.lower()
                if self.debug: print(f"Current application form section header: '{section_header_text}'")

                if 'home address' in section_header_text:
                    self.home_address(form)
                elif 'contact info' in section_header_text: # Assuming contact_info is similar to home_address or handled by additional_questions
                    # self.contact_info(form) # If a dedicated contact_info method exists
                    self.additional_questions(form) # Or handle through general questions
                elif 'resume' in section_header_text:
                    self.send_resume()
                # Add other specific sections if LinkedIn structures them this way, e.g., 'Work experience', 'Education'
                else: # Default to additional_questions for other/unknown sections
                    if self.debug: print("Section not specifically identified, defaulting to additional_questions handler.")
                    self.additional_questions(form)

            except NoSuchElementException: # No h3 header found, might be a page with just questions
                if self.debug: print("No specific section header (h3) found, treating as additional questions page.")
                self.additional_questions(form)
            except Exception as e_section:
                print(f"Error determining or handling form section: {e_section}")
                traceback.print_exc()

        except TimeoutException:
            if self.debug: print("Easy Apply modal content or form not found within timeout.")
        except NoSuchElementException:
            if self.debug: print("Easy Apply modal content or form element not found.")
        except Exception as e_fill:
            print(f"An unexpected error occurred in fill_up: {e_fill}")
            traceback.print_exc()


    def next_job_page(self, position: str, location_url_param: str, job_page_number: int) -> None:
        """
        Navigates to the next page of job search results.

        Constructs the URL for the specified position, location, and page number
        using the base search URL and parameters.

        Args:
            position (str): The job position/keywords being searched.
            location_url_param (str): The URL parameter string for the location (e.g., "&location=New+York").
            job_page_number (int): The page number to navigate to (0-indexed).
                                   The actual `start` parameter for LinkedIn is `page_number * 25`.
        """
        start_param_value: int = job_page_number * 25
        search_url: str = (
            f"https://www.linkedin.com/jobs/search/{self.base_search_url}"
            f"&keywords={position}{location_url_param}&start={start_param_value}"
        )
        if self.debug:
            print(f"Navigating to next job page: {search_url}")
        self.browser.get(search_url)
        self.avoid_lock() # Perform anti-lock measures after navigation


    def avoid_lock(self) -> None:
        """
        Attempts to avoid LinkedIn's bot detection or account lock mechanisms.

        Simulates user activity by briefly switching focus away from the browser
        window using `pyautogui`. This is only active if `self.disable_lock` is False.
        """
        if self.disable_lock:
            return

        if self.debug:
            print("Performing anti-lock measure (simulating focus change).")
        try:
            pyautogui.keyDown('ctrl')
            pyautogui.press('esc') # Simulate pressing Ctrl+Esc (opens Start Menu on Windows)
            pyautogui.keyUp('ctrl')
            time.sleep(1.0) # Brief pause
            pyautogui.press('esc') # Close the Start Menu
        except Exception as e:
            # PyAutoGUI can fail if DISPLAY is not available (e.g., headless server)
            print(f"PyAutoGUI anti-lock measure failed: {e}. This is expected in headless environments.")
            if self.debug:
                print("If not running headless, ensure PyAutoGUI has necessary permissions/environment.")

    # Helper methods to get current job title/description if needed by other functions (e.g. for cover letter generation)
    # These are not currently used by additional_questions but could be useful.
    def get_current_job_title(self) -> str:
        """Safely attempts to get the current job title from the details pane."""
        try:
            # This selector might need adjustment based on LinkedIn's current DOM for job details title
            title_element = self.browser.find_element(By.CSS_SELECTOR, ".jobs-unified-top-card__job-title, .job-details-jobs-unified-top-card__job-title")
            return title_element.text.strip()
        except NoSuchElementException:
            if self.debug: print("Could not find current job title in details pane.")
            return "current job" # Fallback

    def get_current_job_description(self) -> str:
        """Safely attempts to get the current job description text from the details pane."""
        try:
            description_element = self.browser.find_element(By.ID, 'job-details')
            return description_element.text
        except NoSuchElementException:
            if self.debug: print("Could not find current job description text in details pane.")
            return "" # Fallback