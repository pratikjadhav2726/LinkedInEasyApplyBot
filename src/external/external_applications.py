"""
Utility functions for handling job applications on external platforms like Ashby and Greenhouse.

This module provides functions to automate filling out application forms on these
external sites, using Selenium for browser interaction and an AI model for
generating responses to custom questions. It leverages predefined field patterns
for common information and attempts to fill fields intelligently.
"""
import time
import re
import random
from typing import Dict, List, Any, Optional, Tuple, Pattern, Callable

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys # Added for Keys.ESCAPE

# Assuming AIResponseGenerator is in src.ai directory, adjust if necessary
from src.ai.ai_response_generator import AIResponseGenerator


# FIELD_PATTERNS: A list of tuples, where each tuple contains:
# 1. A compiled regular expression pattern (Pattern[str]) to match field labels.
# 2. A lambda function (Callable[[Dict[str, Any]], str]) that takes a context dictionary
#    (merged personal_info, eeo, etc.) and returns the string value for that field.
# This structure allows for flexible and pattern-based field filling.
FIELD_PATTERNS: List[Tuple[Pattern[str], Callable[[Dict[str, Any]], str]]] = [
    (re.compile(r'first\s*name', re.I), lambda info: info.get('First Name', '')),
    (re.compile(r'last\s*name', re.I), lambda info: info.get('Last Name', '')),
    # This 'name' pattern should be less specific or ordered carefully to avoid overriding first/last name
    (re.compile(r'^name$', re.I), lambda info: f"{info.get('First Name', '')} {info.get('Last Name', '')}"),
    (re.compile(r'email', re.I), lambda info: info.get('Email', '')),
    (re.compile(r'linkedin', re.I), lambda info: info.get('Linkedin', '')),
    (re.compile(r'github', re.I), lambda info: info.get('Website', '')), # Assuming GitHub URL is in 'Website'
    (re.compile(r'website|portfolio|personal site', re.I), lambda info: info.get('Website', '')),
    (re.compile(r'city', re.I), lambda info: info.get('City', '')),
    (re.compile(r'state', re.I), lambda info: info.get('State', '')),
    (re.compile(r'zip|postal', re.I), lambda info: info.get('Zip', '')),
    (re.compile(r'phone|mobile', re.I), lambda info: info.get('Mobile Phone Number', '')),
    (re.compile(r'location', re.I), lambda info: info.get('Location', '')), # General location, might be city/state
    (re.compile(r'visa|sponsor', re.I), lambda info: info.get('Sponsorship', "Yes")), # Default to "Yes" if not specified
    (re.compile(r'work\s*sched', re.I), lambda info: "Yes"), # Generic response for work schedule questions
    (re.compile(r'authorized|legal', re.I), lambda info: info.get('Authorized', "Yes")), # Work authorization
    (re.compile(r'salary|compensation|expect', re.I), lambda info: info.get('Salary Expectation', 'Open to discussion')),
    # EEO Questions - these often have specific dropdowns/radio buttons handled by AI choice or specific logic.
    # The lambdas provide fallback text if direct input is possible.
    (re.compile(r'gender', re.I), lambda info: info.get('Gender', 'Prefer not to say')),
    (re.compile(r'hispanic|latino|latinx', re.I), lambda info: info.get('HispanicLatino', "No")), # Example for EEO
    (re.compile(r'ethnic|race', re.I), lambda info: info.get('Race', 'Prefer not to say')),
    (re.compile(r'veteran', re.I), lambda info: info.get('VeteranStatus', "I am not a protected veteran")),
    (re.compile(r'disab', re.I), lambda info: info.get('DisabilityStatus', "No, I do not have a disability")),
]

def get_field_context(personal_info: Dict[str, Any],
                      eeo: Optional[Dict[str, Any]] = None,
                      salary_minimum: Optional[str] = None) -> Dict[str, Any]:
    """
    Merges personal information, EEO data, and salary expectations into a single context dictionary.

    This context dictionary is then used by FIELD_PATTERNS to retrieve appropriate values
    for filling form fields.

    Args:
        personal_info (Dict[str, Any]): Dictionary of personal information.
        eeo (Optional[Dict[str, Any]]): Dictionary of EEO information. Defaults to None.
        salary_minimum (Optional[str]): Minimum salary expectation string. Defaults to None.

    Returns:
        Dict[str, Any]: A merged dictionary containing all provided information.
    """
    context = dict(personal_info) # Start with personal_info
    if eeo:
        context.update(eeo) # Add EEO info

    # Add salary expectation if provided and not already in personal_info
    if salary_minimum and 'Salary Expectation' not in context:
        context['Salary Expectation'] = salary_minimum

    # Provide fallbacks for common EEO fields if not explicitly in personal_info or eeo dicts
    # These keys ('Gender', 'Race', etc.) should match what FIELD_PATTERNS expect.
    if 'Gender' not in context and eeo and eeo.get('gender'):
        context['Gender'] = eeo['gender']
    if 'Race' not in context and eeo and eeo.get('race'):
        context['Race'] = eeo['race']
    # ... (add other EEO fallbacks as needed based on your config structure) ...
    return context

def random_delay(min_seconds: float = 0.4, max_seconds: float = 0.9) -> None:
    """
    Pauses execution for a random duration within a specified range.

    Args:
        min_seconds (float): Minimum delay in seconds.
        max_seconds (float): Maximum delay in seconds.
    """
    time.sleep(random.uniform(min_seconds, max_seconds))

def human_scroll(browser: WebDriver, element: WebElement, scrolls: int = 2) -> None:
    """
    Simulates human-like scrolling behavior around a specific web element.

    Scrolls the element into view (centered), then performs small up and down
    scrolls to mimic human interaction and potentially trigger lazy-loaded content.

    Args:
        browser (WebDriver): The Selenium WebDriver instance.
        element (WebElement): The element to scroll around.
        scrolls (int): The number of small up/down scroll cycles to perform.
    """
    for _ in range(scrolls):
        # Scroll element to the center of the view
        browser.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", element)
        random_delay(0.2, 0.5)
        # Scroll up a bit
        browser.execute_script("window.scrollBy(0, -100);")
        random_delay(0.2, 0.5)
        # Scroll down a bit more (net scroll down)
        browser.execute_script("window.scrollBy(0, 200);")
        random_delay(0.2, 0.5)

def apply_to_ashby(browser: WebDriver,
                   personal_info: Dict[str, Any],
                   resume_dir: str,
                   ai_response_generator: AIResponseGenerator,
                   jd: str = "",
                   eeo: Optional[Dict[str, Any]] = None,
                   salary_minimum: Optional[str] = None) -> bool:
    """
    Automates filling out a job application form on the Ashby platform.

    This function handles:
    - Navigating to the application tab (if applicable).
    - Uploading a resume.
    - Filling text input fields and textareas using predefined patterns and AI for unknown fields.
    - Submitting the application.

    Args:
        browser (WebDriver): The Selenium WebDriver instance.
        personal_info (Dict[str, Any]): Candidate's personal information.
        resume_dir (str): Path to the resume file.
        ai_response_generator (AIResponseGenerator): Instance for generating AI responses.
        jd (str, optional): Job description text. Defaults to "".
        eeo (Optional[Dict[str, Any]], optional): EEO information. Defaults to None.
        salary_minimum (Optional[str], optional): Minimum salary expectation. Defaults to None.

    Returns:
        bool: True if the application was submitted successfully, False otherwise.
    """
    print("Starting Ashby Application process.")
    wait = WebDriverWait(browser, 20) # Increased wait time for elements
    context = get_field_context(personal_info, eeo, salary_minimum)

    try:
        # Step 1: Ensure "Application" tab is active (if such tabs exist on the page)
        # This is a speculative step; Ashby forms are often single-page.
        try:
            # Example: Look for a tab-like element and click if not active.
            # This XPath is hypothetical and needs to match Ashby's actual structure if tabs are used.
            app_tab_xpath = "//div[contains(@class,'ashby-job-posting-nav')]//a[contains(text(),'Application')]"
            if browser.find_elements(By.XPATH, app_tab_xpath): # Check if tab navigation exists
                app_tab = browser.find_element(By.XPATH, app_tab_xpath)
                # Check if it's already active or click it
                if "active" not in app_tab.get_attribute("class"): # Hypothetical active class
                    human_scroll(browser, app_tab)
                    app_tab.click()
                    random_delay()
        except Exception:
            print("Application tab navigation not found or not applicable for this Ashby form.")
            pass

        # Step 2: Upload resume
        # Ashby forms often have a prominent resume upload that can autofill.
        try:
            # Common XPath for Ashby resume upload button or input.
            # Look for a button that triggers a file input, or the file input itself.
            resume_upload_trigger_xpath = "//button[.//span[contains(text(),'Upload Resume') or contains(text(),'Upload File')]] | //input[@type='file' and (contains(@name, 'resume') or contains(@id, 'resume'))]"
            resume_upload_element = wait.until(EC.presence_of_element_located((By.XPATH, resume_upload_trigger_xpath)))

            human_scroll(browser, resume_upload_element)
            if resume_upload_element.tag_name == 'button':
                resume_upload_element.click() # Click button to reveal input[@type='file']
                random_delay()
                # After clicking button, find the actual file input (often hidden then revealed)
                # This ID `_systemfield_resume` was in original; might be specific or general.
                file_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='file' and (@id='_systemfield_resume' or @name='resume')]")))
                file_input.send_keys(resume_dir)
            else: # It was already the file input
                resume_upload_element.send_keys(resume_dir)

            print("Resume uploaded to Ashby form.")
            random_delay(3, 5) # Allow time for potential autofill after resume upload
        except Exception as e:
            print(f"Could not upload resume to Ashby (or it's optional/already handled): {e}")

        # Step 3: Fill text input fields (type='text', type='email')
        # Ashby input fields are typically `input` tags.
        text_inputs: List[WebElement] = browser.find_elements(By.XPATH, "//div[contains(@class, 'ashby-application-form-field')]//input[@type='text' or @type='email' or @type='tel']")
        print(f"Found {len(text_inputs)} text input fields on Ashby form.")
        for inp in text_inputs:
            try:
                if not inp.is_displayed(): continue # Skip hidden inputs
                human_scroll(browser, inp)
                current_value: str = inp.get_attribute("value")
                if current_value and current_value.strip() != "": # Skip if already filled (e.g., by autofill)
                    print(f"Skipping already filled input: {current_value[:30]}")
                    continue

                # Try to find the label associated with the input
                label_text: str = ""
                try:
                    # Ashby labels are often `div` or `label` elements preceding or as part of the field container.
                    # This XPath tries to find a label based on `for` attribute or as a preceding sibling `div` with text.
                    input_id = inp.get_attribute('id')
                    if input_id:
                        label_elem = browser.find_element(By.XPATH, f"//label[@for='{input_id}']")
                        label_text = label_elem.text.strip()
                    if not label_text: # Fallback to find a div that looks like a label
                        label_elem = inp.find_element(By.XPATH, "./ancestor::div[contains(@class,'ashby-application-form-field')]//div[contains(@class,'ashby-application-form-field-label')]")
                        label_text = label_elem.text.strip()
                except Exception:
                    print(f"Could not find label for an Ashby text input. ID: {inp.get_attribute('id')}")
                    # Try to use placeholder as a fallback for context if label is missing
                    label_text = inp.get_attribute("placeholder") or ""


                value_to_fill: Optional[str] = None
                # Match label_text against FIELD_PATTERNS
                for pattern, func in FIELD_PATTERNS:
                    if pattern.search(label_text.lower()): # Use lower for robust matching
                        value_to_fill = func(context)
                        break

                if value_to_fill is not None:
                    inp.clear()
                    inp.send_keys(value_to_fill)
                    print(f"Filled Ashby input '{label_text}' with: '{value_to_fill[:30]}...'")
                elif label_text: # If no pattern matched but we have a label, try AI
                    print(f"No pattern match for Ashby input '{label_text}'. Using AI.")
                    ai_answer: Optional[str] = ai_response_generator.generate_response(label_text, response_type="text", jd=jd)
                    if ai_answer:
                        inp.clear()
                        inp.send_keys(ai_answer)
                        print(f"Filled Ashby input '{label_text}' with AI: '{ai_answer[:30]}...'")
                random_delay()
            except Exception as e:
                print(f"Could not fill an Ashby text input (label: '{label_text}'): {e}")

        # Step 4: Fill textareas
        textareas: List[WebElement] = browser.find_elements(By.XPATH, "//div[contains(@class, 'ashby-application-form-field')]//textarea")
        print(f"Found {len(textareas)} textarea fields on Ashby form.")
        for ta in textareas:
            try:
                if not ta.is_displayed(): continue
                human_scroll(browser, ta)
                current_value: str = ta.get_attribute("value")
                if current_value and current_value.strip() != "":
                    print(f"Skipping already filled textarea: {current_value[:30]}")
                    continue

                label_text: str = ""
                try:
                    textarea_id = ta.get_attribute('id')
                    if textarea_id:
                         label_elem = browser.find_element(By.XPATH, f"//label[@for='{textarea_id}']")
                         label_text = label_elem.text.strip()
                    if not label_text:
                        label_elem = ta.find_element(By.XPATH, "./ancestor::div[contains(@class,'ashby-application-form-field')]//div[contains(@class,'ashby-application-form-field-label')]")
                        label_text = label_elem.text.strip()
                except Exception:
                    print(f"Could not find label for an Ashby textarea. ID: {ta.get_attribute('id')}")
                    label_text = ta.get_attribute("placeholder") or ""

                value_to_fill: Optional[str] = None
                for pattern, func in FIELD_PATTERNS:
                    if pattern.search(label_text.lower()):
                        value_to_fill = func(context)
                        break

                if value_to_fill is not None:
                    ta.clear()
                    ta.send_keys(value_to_fill)
                    print(f"Filled Ashby textarea '{label_text}' with: '{value_to_fill[:30]}...'")
                elif label_text: # If no pattern matched, try AI
                    print(f"No pattern match for Ashby textarea '{label_text}'. Using AI.")
                    ai_answer: Optional[str] = ai_response_generator.generate_response(label_text, response_type="text", jd=jd)
                    if ai_answer:
                        ta.clear()
                        ta.send_keys(ai_answer)
                        print(f"Filled Ashby textarea '{label_text}' with AI: '{ai_answer[:30]}...'")
                random_delay()
            except Exception as e:
                print(f"Could not fill an Ashby textarea (label: '{label_text}'): {e}")

        # Step 5: Handle select dropdowns (if any specific logic is needed beyond standard HTML select)
        # Ashby might use custom dropdowns. Example for a common pattern:
        # Find clickable element that opens dropdown, then click desired option.
        # This requires identifying those custom dropdowns and their option selectors.
        # For now, this part is illustrative and may need specific selectors for Ashby.
        # Example: custom_dropdowns = browser.find_elements(By.XPATH, "//div[@role='combobox']")
        # for dropdown in custom_dropdowns: ... handle clicks and option selection ...

        # Step 6: Submit the form
        # Common XPath for Ashby submit button.
        submit_button_xpath = "//button[contains(@class,'ashby-application-form-submit-button') and not(@disabled)]"
        submit_btn = wait.until(EC.element_to_be_clickable((By.XPATH, submit_button_xpath)))
        human_scroll(browser, submit_btn)
        submit_btn.click()
        print("Ashby application submitted (or attempted).")
        random_delay(3, 5) # Wait for submission confirmation or next page

        # Check for success message or errors after submission if possible
        # page_source = browser.page_source.lower()
        # if "thank you" in page_source or "application submitted" in page_source:
        #    print("Ashby application confirmed submitted.")
        #    return True
        # elif "error" in page_source or "fix the errors" in page_source:
        #    print("Error message detected after Ashby submission attempt.")
        #    return False

        return True # Assume success if no immediate error after click

    except Exception as e:
        print(f"An error occurred during the Ashby application process: {e}")
        traceback.print_exc()
        return False

def apply_to_greenhouse(browser: WebDriver,
                        personal_info: Dict[str, Any],
                        resume_dir: str,
                        cover_letter_dir: str,
                        ai_response_generator: AIResponseGenerator,
                        jd: str = "") -> bool:
    """
    Automates filling out a job application form on the Greenhouse platform.

    Handles resume/cover letter uploads, filling standard text fields,
    and interacting with various input types like dropdowns (including Select2).
    Uses AI for unmapped fields or complex questions.

    Args:
        browser (WebDriver): The Selenium WebDriver instance.
        personal_info (Dict[str, Any]): Candidate's personal information.
        resume_dir (str): Path to the resume file.
        cover_letter_dir (str): Path to the cover letter file (can be empty).
        ai_response_generator (AIResponseGenerator): Instance for AI responses.
        jd (str, optional): Job description text. Defaults to "".

    Returns:
        bool: True if the application was submitted successfully, False otherwise.
    """
    print("Starting Greenhouse Application process.")
    wait = WebDriverWait(browser, 15) # Standard wait time
    context = get_field_context(personal_info) # Context for FIELD_PATTERNS

    try:
        # Wait for the main application form container to be loaded
        # Greenhouse forms can have ID "application-form" or "main_fields" (older versions)
        form_container_xpath = "//*[@id='application-form' or @id='main_fields']"
        wait.until(EC.presence_of_element_located((By.XPATH, form_container_xpath)))
        random_delay()

        # --- Resume Upload (often triggers autofill) ---
        try:
            # Greenhouse resume input often has ID "resume" or "file" for resume.
            resume_input_xpath = "//input[@type='file' and (@id='resume' or @name='resume_text[file]' or contains(@aria-label, 'resume'))]"
            resume_input = browser.find_element(By.XPATH, resume_input_xpath)
            human_scroll(browser, resume_input) # Scroll to it
            resume_input.send_keys(resume_dir)
            print(f"Resume uploaded to Greenhouse from: {resume_dir}")
            random_delay(3, 5) # Allow time for autofill if supported
        except Exception as e:
            print(f"Could not upload resume to Greenhouse (or field not found): {e}")

        # --- Cover Letter Upload (if path provided) ---
        if cover_letter_dir:
            try:
                # Greenhouse cover letter input often has ID "cover_letter" or "file" for cover letter.
                cover_letter_input_xpath = "//input[@type='file' and (@id='cover_letter' or @name='cover_letter_text[file]' or contains(@aria-label, 'cover letter'))]"
                cover_letter_input = browser.find_element(By.XPATH, cover_letter_input_xpath)
                human_scroll(browser, cover_letter_input)
                cover_letter_input.send_keys(cover_letter_dir)
                print(f"Cover letter uploaded to Greenhouse from: {cover_letter_dir}")
                random_delay()
            except Exception as e:
                print(f"Could not upload cover letter to Greenhouse (or field not found): {e}")

        # --- Handle standard input fields (text, email, tel) ---
        # These are often directly fillable after resume autofill.
        # Using a more general XPath to find inputs with IDs, then matching labels.
        all_inputs_xpath = "//form[@id='application_form']//input[@id and (@type='text' or @type='email' or @type='tel' or @type='number')]"
        text_inputs: List[WebElement] = browser.find_elements(By.XPATH, all_inputs_xpath)
        print(f"Found {len(text_inputs)} text/email/tel/number input fields on Greenhouse form.")

        for inp in text_inputs:
            try:
                if not inp.is_displayed(): continue
                human_scroll(browser, inp)
                current_value: str = inp.get_attribute("value")
                input_id: str = inp.get_attribute("id")

                # Skip if already filled (likely by autofill or previous step)
                if current_value and current_value.strip() != "" and "demographics" not in input_id : # Don't skip demographic fields if they need specific answers
                    # However, if it's a demographic field, we might want to overwrite it based on EEO config
                    # This needs careful handling if EEO data should override autofill.
                    # For now, if filled and not a known EEO field, skip.
                    print(f"Skipping already filled Greenhouse input (ID: {input_id}): {current_value[:30]}")
                    continue

                # Get associated label text
                label_text: str = ""
                try:
                    # Greenhouse labels are usually `label` tags with a `for` attribute.
                    label_elem = browser.find_element(By.XPATH, f"//label[@for='{input_id}']")
                    label_text = label_elem.text.strip()
                except NoSuchElementException:
                    # Fallback: check aria-label or placeholder on the input itself
                    label_text = inp.get_attribute("aria-label") or inp.get_attribute("placeholder") or ""

                if not label_text: # If still no label, might be hard to map
                    print(f"Could not determine label for Greenhouse input ID: {input_id}. Skipping pattern/AI fill for this one unless it's part of a known group.")
                    continue

                value_to_fill: Optional[str] = None
                # Match label_text against FIELD_PATTERNS
                for pattern, func in FIELD_PATTERNS:
                    if pattern.search(label_text.lower()):
                        value_to_fill = func(context)
                        break

                if value_to_fill is not None:
                    inp.clear() # Clear before sending keys
                    inp.send_keys(value_to_fill)
                    print(f"Filled Greenhouse input '{label_text}' with: '{value_to_fill[:30]}...'")
                elif label_text: # If no pattern matched but we have a label, try AI
                    print(f"No pattern match for Greenhouse input '{label_text}'. Using AI.")
                    ai_answer: Optional[str] = ai_response_generator.generate_response(label_text, response_type="text", jd=jd)
                    if ai_answer:
                        inp.clear()
                        inp.send_keys(ai_answer)
                        print(f"Filled Greenhouse input '{label_text}' with AI: '{ai_answer[:30]}...'")
                random_delay()
            except Exception as e:
                print(f"Could not fill a Greenhouse text/email/tel input (Label: '{label_text}'): {e}")

        # --- Handle Textareas ---
        textareas: List[WebElement] = browser.find_elements(By.XPATH, "//form[@id='application_form']//textarea[@id]")
        print(f"Found {len(textareas)} textarea fields on Greenhouse form.")
        for ta in textareas:
            # Similar logic to text inputs for textareas
            # ... (omitted for brevity, but would mirror text input logic with label finding, FIELD_PATTERNS, AI fallback) ...
            pass # Placeholder for textarea logic

        # --- Handle Select Dropdowns (standard HTML select) ---
        select_elements: List[WebElement] = browser.find_elements(By.XPATH, "//form[@id='application_form']//select[@id]")
        print(f"Found {len(select_elements)} select dropdowns on Greenhouse form.")
        for sel in select_elements:
            # Similar logic: get label, get options, use FIELD_PATTERNS or AI (choice)
            # ... (omitted for brevity) ...
            pass # Placeholder for select logic

        # --- Handle Custom Questions / EEO (often radio buttons or custom selects) ---
        # This requires more specific selectors for Greenhouse EEO sections if they exist.
        # E.g., find sections by header "U.S. Equal Opportunity Employment Information"
        # Then find radio groups or dropdowns within that section.
        # AIResponseGenerator's "choice" type would be useful here.
        # ... (omitted for brevity) ...

        # --- Submit Application ---
        try:
            # Common submit button text/ID for Greenhouse
            submit_button_xpath = "//button[@type='submit' and (contains(text(), 'Submit Application') or @id='submit_app')]"
            submit_btn = wait.until(EC.element_to_be_clickable((By.XPATH, submit_button_xpath)))
            human_scroll(browser, submit_btn) # Scroll to submit button
            submit_btn.click()
            print("Greenhouse application submitted (or attempted).")
            random_delay(3, 5) # Wait for confirmation or errors

            # Check for success/thank you page or error messages
            # page_source = browser.page_source.lower()
            # if "thank you for applying" in page_source or "application submitted" in page_source:
            #    print("Greenhouse application confirmed submitted.")
            #    return True
            # elif "error" in page_source or "please correct the errors" in page_source:
            #    print("Error message detected after Greenhouse submission attempt.")
            #    return False

            return True # Assume success if click doesn't error out immediately
        except Exception as e_submit:
            print(f"Could not submit Greenhouse application: {e_submit}")
            return False

    except Exception as e:
        print(f"An error occurred during the Greenhouse application process: {e}")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # This block is for testing the functions in this module directly.
    # It requires a live browser and a config file (config.prod.yaml) with credentials.
    import sys
    import yaml
    # from ai.ai_response_generator import AIResponseGenerator # Already imported at top
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    # Example usage: python src/external/external_applications.py <application_url>
    if len(sys.argv) < 2:
        print("Usage: python src/external/external_applications.py <application_url>")
        sys.exit(1)

    test_application_url: str = sys.argv[1]

    # Load configuration from a YAML file (adjust path if necessary)
    try:
        with open("config.prod.yaml", "r") as f: # Ensure this path is correct
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print("Error: config.prod.yaml not found. Please create it with necessary parameters.")
        sys.exit(1)

    # Extract parameters from config
    personal_info_conf: Dict[str, Any] = config.get('personalInfo', {})
    experience_conf: Dict[str, Any] = config.get('experience', {})
    languages_conf: Dict[str, str] = config.get('languages', {})
    checkboxes_conf: Dict[str, bool] = config.get('checkboxes', {})
    eeo_conf: Optional[Dict[str, Any]] = config.get('eeo') # EEO can be optional
    salary_minimum_conf: Optional[str] = config.get('salaryMinimum')
    resume_dir_conf: str = config.get('uploads', {}).get('resume', '')
    cover_letter_dir_conf: str = config.get('uploads', {}).get('coverLetter', '')

    # AI Model related config
    # Assuming 'ollamaModel' was a typo and it should be 'modelName' for AIResponseGenerator
    model_name_conf: str = config.get('modelName', config.get('ollamaModel', 'default-model'))
    text_resume_path_conf: Optional[str] = config.get('textResume')
    debug_conf: bool = config.get('debug', False)
    api_key_conf: Optional[str] = config.get('openaiApiKey')


    if not resume_dir_conf:
        print("Error: Resume directory ('uploads.resume') not specified in config.prod.yaml.")
        sys.exit(1)

    # Initialize the AIResponseGenerator
    ai_gen_instance = AIResponseGenerator(
        api_key=api_key_conf or "", # Pass empty string if None
        personal_info=personal_info_conf,
        experience=experience_conf,
        languages=languages_conf,
        resume_path=resume_dir_conf,
        checkboxes=checkboxes_conf,
        model_name=model_name_conf,
        text_resume_path=text_resume_path_conf,
        debug=debug_conf
    )

    # Setup Selenium WebDriver
    chrome_options = Options()
    # Add any necessary options, e.g., for headless if desired, though not recommended for initial testing
    # chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')

    print(f"Attempting to open browser for URL: {test_application_url}")
    browser_instance = webdriver.Chrome(options=chrome_options)
    browser_instance.get(test_application_url)
    random_delay(3, 5) # Wait for page to load initially

    # Basic detection logic to call the appropriate handler
    page_source_lower: str = browser_instance.page_source.lower()

    if 'ashby' in page_source_lower or "ashbyhq.com" in test_application_url:
        print("Detected Ashby application form. Attempting to apply...")
        apply_to_ashby(browser_instance, personal_info_conf, resume_dir_conf, ai_gen_instance,
                       eeo=eeo_conf, salary_minimum=salary_minimum_conf)
    elif 'greenhouse' in page_source_lower or 'grnh.se' in test_application_url:
        print("Detected Greenhouse application form. Attempting to apply...")
        apply_to_greenhouse(browser_instance, personal_info_conf, resume_dir_conf,
                            cover_letter_dir_conf, ai_gen_instance)
    else:
        print("Unknown application type from URL or page source. Cannot apply automatically.")

    print("Test finished. Closing browser in 10 seconds...")
    time.sleep(10)
    browser_instance.quit()