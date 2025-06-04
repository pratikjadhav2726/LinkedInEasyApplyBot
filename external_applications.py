from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time
import re
import random

# Improved FIELD_PATTERNS for robust field matching (no overbroad 'name' match)
FIELD_PATTERNS = [
    (re.compile(r'first\s*name', re.I), lambda info: info.get('First Name', '')),
    (re.compile(r'last\s*name', re.I), lambda info: info.get('Last Name', '')),
    (re.compile(r'name', re.I), lambda info: f"{info.get('First Name', '')} {info.get('Last Name', '')}"),
    (re.compile(r'email', re.I), lambda info: info.get('Email', '')),
    (re.compile(r'linkedin', re.I), lambda info: info.get('Linkedin', '')),
    (re.compile(r'github', re.I), lambda info: info.get('Website', '')),
    (re.compile(r'website|portfolio|personal site', re.I), lambda info: info.get('Website', '')),
    (re.compile(r'city', re.I), lambda info: info.get('City', '')),
    (re.compile(r'state', re.I), lambda info: info.get('State', '')),
    (re.compile(r'zip|postal', re.I), lambda info: info.get('Zip', '')),
    (re.compile(r'phone|mobile', re.I), lambda info: info.get('Mobile Phone Number', '')),
    (re.compile(r'location', re.I), lambda info: info.get('Location', '')),
    (re.compile(r'visa|sponsor', re.I), lambda info: "Yes"),
    (re.compile(r'work\s*sched', re.I), lambda info: "Yes"),
    (re.compile(r'authorized|legal', re.I), lambda info: "Yes"),
    (re.compile(r'salary|compensation|expect', re.I), lambda info: info.get('Salary Expectation', 'Open')),
    (re.compile(r'gender', re.I), lambda info: info.get('Gender', 'Male')),
    (re.compile(r'hispanic|latino|latinx', re.I), lambda info:"No"),
    (re.compile(r'ethnic|race', re.I), lambda info: info.get('Race', 'Asian')),
    (re.compile(r'veteran', re.I), lambda info: "I am not a protected veteran"),
    (re.compile(r'disab', re.I), lambda info: "No, I do not have a disability and have not had one in the past"),
]

# Helper to merge personalInfo, eeo, and salaryMinimum for FIELD_PATTERNS

def get_field_context(personal_info, eeo=None, salary_minimum=None):
    context = dict(personal_info)
    if eeo:
        context.update(eeo)
    if salary_minimum and 'Salary Expectation' not in context:
        context['Salary Expectation'] = salary_minimum
    # Gender, Race, Veteran, Disability fallback
    if 'Gender' not in context and eeo and 'gender' in eeo:
        context['Gender'] = eeo['gender']
    if 'Race' not in context and eeo and 'race' in eeo:
        context['Race'] = eeo['race']
    if 'Veteran' not in context and eeo and 'veteran' in eeo:
        context['Veteran'] = eeo['veteran']
    if 'Disability' not in context and eeo and 'disability' in eeo:
        context['Disability'] = eeo['disability']
    return context

# Random delay helper
def random_delay(a=0.4, b=0.9):
    time.sleep(random.uniform(a, b))

# Human-like scrolling to reduce bot detection
def human_scroll(browser, element, scrolls=2):
    # Scroll up and down a bit to simulate human behavior
    for _ in range(scrolls):
        browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        random_delay(0.2, 0.5)
        browser.execute_script("window.scrollBy(0, -100)")
        random_delay(0.2, 0.5)
        browser.execute_script("window.scrollBy(0, 200)")
        random_delay(0.2, 0.5)

# Ashby application handler
def apply_to_ashby(browser, personal_info, resume_dir, ai_response_generator, jd="", eeo=None, salary_minimum=None):
    print("Starting Ashby Application.")
    wait = WebDriverWait(browser, 20)
    context = get_field_context(personal_info, eeo, salary_minimum)
    try:
        # 1. Go to "Application" tab (if not already there)
        try:
            app_tab = browser.find_element(By.XPATH, "//span[contains(@class,'ashby-job-posting-right-pane-application-tab') and contains(text(),'Application')]")
            app_tab.click()
            random_delay()
        except Exception:
            pass  # Already on tab or not present

        # 2. Upload resume (if the upload button exists and file not already attached)
        try:
            upload_btn = browser.find_element(By.XPATH, "//button[.//span[contains(text(),'Upload File')]]")
            human_scroll(browser, upload_btn)
            upload_btn.click()
            random_delay()
            file_input = browser.find_element(By.XPATH, "//input[@type='file' and @id='_systemfield_resume']")
            human_scroll(browser, file_input)
            file_input.send_keys(resume_dir)
            print("Resume uploaded for autofill.")
            random_delay(5, 5.5)
        except Exception as e:
            print(f"Could not upload resume (may already be uploaded): {e}")

        # 3. Fill any empty text input fields
        text_inputs = browser.find_elements(By.XPATH, "//input[@type='text' or @type='email']")
        for inp in text_inputs:
            try:
                human_scroll(browser, inp)
                value = inp.get_attribute("value")
                if value and value.strip() != "":
                    continue
                label_text = ""
                try:
                    label_elem = browser.find_element(By.XPATH, f"//label[@for='{inp.get_attribute('id')}']")
                    label_text = label_elem.text.strip()
                except Exception:
                    pass
                value_filled = False
                for pattern, func in FIELD_PATTERNS:
                    # Use .fullmatch() for strict fields, but .search() for others (except first/last name)
                    label = label_text.strip()
                    if pattern.pattern in [r'^first\s*name$', r'^last\s*name$', r'^name$']:
                        if pattern.fullmatch(label):
                            inp.clear()
                            inp.send_keys(func(context))
                            value_filled = True
                            break
                    else:
                        if pattern.search(label):
                            inp.clear()
                            inp.send_keys(func(context))
                            value_filled = True
                            break
                if not value_filled:
                    ai_answer = ai_response_generator.generate_response(label_text, response_type="text", jd=jd)
                    inp.clear()
                    inp.send_keys(ai_answer)
                random_delay()
            except Exception as e:
                print(f"Could not fill Ashby text input: {e}")

        # 4. Fill any empty textareas
        textareas = browser.find_elements(By.XPATH, "//textarea")
        for ta in textareas:
            try:
                human_scroll(browser, ta)
                value = ta.get_attribute("value")
                if value and value.strip() != "":
                    continue
                label_text = ""
                try:
                    label_elem = browser.find_element(By.XPATH, f"//label[@for='{ta.get_attribute('id')}']")
                    label_text = label_elem.text.strip()
                except Exception:
                    pass
                value_filled = False
                for pattern, func in FIELD_PATTERNS:
                    if pattern.search(label_text):
                        ta.clear()
                        ta.send_keys(func(context))
                        value_filled = True
                        break
                if not value_filled:
                    ai_answer = ai_response_generator.generate_response(label_text, response_type="text", jd=jd)
                    ta.clear()
                    ta.send_keys(ai_answer)
                random_delay()
            except Exception as e:
                print(f"Could not fill Ashby textarea: {e}")

        # 5. Optionally handle selects (dropdowns) if needed
        # 6. Submit the form
        submit_btn = browser.find_element(By.XPATH, "//button[contains(@class,'ashby-application-form-submit-button')]")
        human_scroll(browser, submit_btn)
        submit_btn.click()
        print("Ashby application submitted successfully.")
        random_delay(2, 2.5)
        return True
    except Exception as e:
        print(f"Error during Ashby application: {e}")
        return False

# Greenhouse application handler
def apply_to_greenhouse(browser, personal_info, resume_dir, cover_letter_dir, ai_response_generator, jd=""):
    print("Starting Greenhouse Application.")
    wait = WebDriverWait(browser, 15)
    try:
        # Wait for either modern or classic Greenhouse form container
        try:
            wait.until(lambda d: d.find_elements(By.ID, "application-form") or d.find_elements(By.ID, "main_fields"))
            random_delay()
        except Exception as e:
            print("Could not find Greenhouse application form or main_fields: ", e)
            return False
        # Upload resume FIRST
        try:
            resume_input = browser.find_element(By.ID, "resume")
            print(f"Uploading resume from: {resume_dir}")
            resume_input.send_keys(resume_dir)
            random_delay()
        except Exception as e:
            print(f"Could not upload resume: {e}")
        # Upload cover letter if present
        try:
            if cover_letter_dir:
                cover_letter_input = browser.find_element(By.ID, "cover_letter")
                print(f"Uploading cover letter from: {cover_letter_dir}")
                cover_letter_input.send_keys(cover_letter_dir)
                random_delay()
        except Exception:
            pass
        # Handle Select2 dropdowns (classic Greenhouse)
        select2s = browser.find_elements(By.CSS_SELECTOR, ".select2-container")
        for select2 in select2s:
            try:
                choice = select2.find_element(By.CSS_SELECTOR, ".select2-choice")
                human_scroll(browser, choice)
                choice.click()
                random_delay()
                # Wait for dropdown to appear
                wait = WebDriverWait(browser, 5)
                wait.until(lambda d: d.find_element(By.CSS_SELECTOR, ".select2-drop:not(.select2-display-none)"))
                options = browser.find_elements(By.CSS_SELECTOR, ".select2-drop:not(.select2-display-none) .select2-result-label")
                option_texts = [opt.text.strip() for opt in options]
                # Use AI or FIELD_PATTERNS to pick the right option (here: pick first non-empty)
                for opt in options:
                    if opt.text.strip():
                        opt.click()
                        break
                random_delay()
            except Exception as e:
                print(f"Could not handle select2: {e}")

        # Handle file uploads via "Attach" button (classic Greenhouse)
        from selenium.webdriver.common.keys import Keys
        attach_buttons = browser.find_elements(By.CSS_SELECTOR, "button[data-source='attach']")
        for btn in attach_buttons:
            try:
                # Close any Select2 overlays before clicking
                browser.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                WebDriverWait(browser, 2).until_not(lambda d: d.find_elements(By.ID, "select2-drop-mask") and d.find_element(By.ID, "select2-drop-mask").is_displayed())
                human_scroll(browser, btn)
                btn.click()
                random_delay()
                # Find the now-visible file input (type='file')
                file_inputs = browser.find_elements(By.CSS_SELECTOR, "input[type='file']")
                for file_input in file_inputs:
                    if file_input.is_displayed():
                        if "resume" in btn.get_attribute("aria-describedby") or "resume" in btn.get_attribute("aria-label"):
                            file_input.send_keys(resume_dir)
                        elif "cover_letter" in btn.get_attribute("aria-describedby") or "cover_letter" in btn.get_attribute("aria-label"):
                            file_input.send_keys(cover_letter_dir)
                        else:
                            # fallback: try resume
                            file_input.send_keys(resume_dir)
                        random_delay()
                        break
            except Exception as e:
                print(f"Could not upload file: {e}")
        # --- Classic Greenhouse: Autofill all .field divs inside #main_fields ---
        try:
            main_fields = browser.find_element(By.ID, "main_fields")
            field_divs = main_fields.find_elements(By.CSS_SELECTOR, ".field")
            for field in field_divs:
                try:
                    if not field.is_displayed():
                        continue
                    label_elem = None
                    label_text = ""
                    try:
                        label_elem = field.find_element(By.TAG_NAME, "label")
                        label_text = label_elem.text.strip().lower()
                    except Exception:
                        pass
                    input_elem = None
                    for tag in ["input", "select", "textarea"]:
                        try:
                            elem = field.find_element(By.TAG_NAME, tag)
                            if elem.is_displayed():
                                input_elem = elem
                                break
                        except Exception:
                            continue
                    if not input_elem:
                        continue
                    # Handle file inputs for resume/cover letter
                    if input_elem.get_attribute("type") == "file":
                        # Skip if already filled
                        if input_elem.get_attribute("value"):
                            continue
                        if "resume" in label_text and resume_dir:
                            human_scroll(browser, input_elem)
                            input_elem.send_keys(resume_dir)
                            random_delay()
                        elif ("cover letter" in label_text or "coverletter" in label_text) and cover_letter_dir:
                            human_scroll(browser, input_elem)
                            input_elem.send_keys(cover_letter_dir)
                            random_delay()
                        continue
                    # Handle Select2 dropdowns
                    if "select2-container" in field.get_attribute("class") or field.find_elements(By.CSS_SELECTOR, ".select2-container"):
                        try:
                            select2 = field.find_element(By.CSS_SELECTOR, ".select2-container")
                            choice = select2.find_element(By.CSS_SELECTOR, ".select2-choice")
                            human_scroll(browser, choice)
                            choice.click()
                            random_delay()
                            wait = WebDriverWait(browser, 5)
                            wait.until(lambda d: d.find_element(By.CSS_SELECTOR, ".select2-drop:not(.select2-display-none)"))
                            options = browser.find_elements(By.CSS_SELECTOR, ".select2-drop:not(.select2-display-none) .select2-result-label")
                            for opt in options:
                                if opt.text.strip():
                                    opt.click()
                                    break
                            random_delay()
                            continue
                        except Exception as e:
                            print(f"Could not handle select2 in .field: {e}")
                    context = get_field_context(personal_info)
                    value_filled = False
                    for pattern, func in FIELD_PATTERNS:
                        if pattern.search(label_text):
                            input_elem.clear()
                            input_elem.send_keys(func(context))
                            value_filled = True
                            break
                    if not value_filled:
                        ai_answer = ai_response_generator.generate_response(label_text, response_type="text", jd=jd)
                        input_elem.clear()
                        input_elem.send_keys(ai_answer)
                    random_delay()
                except Exception as e:
                    print(f"Could not autofill .field: {e}")
        except Exception as e:
            print(f"Could not process classic Greenhouse .field divs: {e}")
        # Fill all text, email, tel, and number inputs
        all_inputs = browser.find_elements(By.XPATH, "//input[@id]")
        for inp in all_inputs:
            try:
                human_scroll(browser, inp)
                qid = inp.get_attribute('id')
                if qid in ["resume", "cover_letter"]:
                    continue
                # Robust label extraction
                label_text = ""
                try:
                    label_elem = browser.find_element(By.XPATH, f"//label[@for='{qid}']")
                    label_text = label_elem.text.strip()
                except Exception:
                    # Try aria-label or placeholder
                    label_text = inp.get_attribute('aria-label') or inp.get_attribute('placeholder') or ""
                    # Try traversing up for a .label
                    try:
                        parent = inp.find_element(By.XPATH, './ancestor::*[contains(@class, "input-wrapper") or contains(@class, "select__container")][1]')
                        label_elem = parent.find_element(By.XPATH, './/label')
                        label_text = label_elem.text.strip()
                    except Exception:
                        pass
                value_filled = False
                context = get_field_context(personal_info)
                # Use .search() for all FIELD_PATTERNS and skip if already filled
                input_value = inp.get_attribute('value')
                if input_value and input_value.strip() != '':
                    continue
                for pattern, func in FIELD_PATTERNS:
                    if pattern.search(label_text.strip()):
                        inp.clear()
                        inp.send_keys(func(context))
                        value_filled = True
                        break
                if not value_filled:
                    input_type = inp.get_attribute('type')
                    role = inp.get_attribute('role')
                    # Handle React/Greenhouse selects (combobox)
                    if role == "combobox":
                        try:
                            # Find the select container and indicator button
                            select_container = inp.find_element(By.XPATH, './ancestor::div[contains(@class, "select__container")]')
                            indicator_btn = select_container.find_element(By.XPATH, ".//div[contains(@class,'select__indicators')]//button")
                            browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", indicator_btn)
                            ActionChains(browser).move_to_element(indicator_btn).pause(0.2).click(indicator_btn).perform()
                            random_delay(0.7, 1.0)
                            # Wait for dropdown options to be visible
                            wait = WebDriverWait(browser, 5)
                            wait.until(lambda d: d.find_elements(By.XPATH, "//div[contains(@class,'select__option') or contains(@class,'option')]") and any(opt.is_displayed() for opt in d.find_elements(By.XPATH, "//div[contains(@class,'select__option') or contains(@class,'option')]")))
                            options = browser.find_elements(By.XPATH, "//div[contains(@class,'select__option') or contains(@class,'option')]")
                            option_texts = [opt.text.strip() for opt in options if opt.text.strip()]
                            if option_texts:
                                ai_answer = ai_response_generator.generate_response(label_text, response_type="choice", options=list(enumerate(option_texts)), jd=jd)
                                if ai_answer is not None and 0 <= ai_answer < len(options):
                                    options[ai_answer].click()
                                else:
                                    for i, opt in enumerate(options):
                                        if 'prefer not' in opt.text.lower():
                                            opt.click()
                                            break
                                    else:
                                        options[0].click()
                                value_filled = True
                        except Exception as e:
                            print(f"Could not handle React select for {qid}: {e}")
                    if not value_filled:
                        if input_type == "checkbox":
                            ai_answer = ai_response_generator.generate_response(label_text, response_type="text", jd=jd)
                            if ai_answer.strip().lower().startswith("y"):
                                if not inp.is_selected():
                                    inp.click()
                        elif input_type == "radio":
                            name = inp.get_attribute('name')
                            radios = browser.find_elements(By.NAME, name)
                            options = [(i, radio.get_attribute('value')) for i, radio in enumerate(radios)]
                            ai_answer = ai_response_generator.generate_response(label_text, response_type="choice", options=options, jd=jd)
                            if ai_answer is not None and 0 <= ai_answer < len(radios):
                                radios[ai_answer].click()
                            else:
                                for radio in radios:
                                    if 'prefer not' in radio.get_attribute('value').lower():
                                        radio.click()
                                        break
                                else:
                                    radios[0].click()
                        elif input_type == "select-one":
                            options = inp.find_elements(By.TAG_NAME, "option")
                            option_texts = [opt.text.strip() for opt in options]
                            if options and len(option_texts) > 1:
                                ai_answer = ai_response_generator.generate_response(label_text, response_type="choice", options=list(enumerate(option_texts)), jd=jd)
                                if ai_answer is not None and 0 <= ai_answer < len(options):
                                    options[ai_answer].click()
                                else:
                                    for i, opt in enumerate(options):
                                        if 'prefer not' in opt.text.lower():
                                            opt.click()
                                            break
                                    else:
                                        options[0].click()
                            else:
                                ai_answer = ai_response_generator.generate_response(label_text, response_type="text", jd=jd)
                                inp.clear()
                                inp.send_keys(ai_answer)
                        else:
                            ai_answer = ai_response_generator.generate_response(label_text, response_type="text", jd=jd)
                            inp.clear()
                            inp.send_keys(ai_answer)
                random_delay()
            except Exception as e:
                print(f"Could not fill input {inp.get_attribute('id')}: {e}")
        # Fill all textareas
        textareas = browser.find_elements(By.XPATH, "//textarea[@id]")
        for ta in textareas:
            try:
                human_scroll(browser, ta)
                qid = ta.get_attribute('id')
                label_text = ""
                try:
                    label_elem = browser.find_element(By.XPATH, f"//label[@for='{qid}']")
                    label_text = label_elem.text.strip()
                except Exception:
                    pass
                value_filled = False
                context = get_field_context(personal_info)
                for pattern, func in FIELD_PATTERNS:
                    if pattern.search(label_text):
                        ta.clear()
                        ta.send_keys(func(context))
                        value_filled = True
                        break
                if not value_filled:
                    ai_answer = ai_response_generator.generate_response(label_text, response_type="text", jd=jd)
                    ta.clear()
                    ta.send_keys(ai_answer)
                random_delay()
            except Exception as e:
                print(f"Could not fill textarea {ta.get_attribute('id')}: {e}")
        # Fill all selects
        selects = browser.find_elements(By.XPATH, "//select[@id]")
        for sel in selects:
            try:
                human_scroll(browser, sel)
                qid = sel.get_attribute('id')
                label_text = ""
                try:
                    label_elem = browser.find_element(By.XPATH, f"//label[@for='{qid}']")
                    label_text = label_elem.text.strip()
                except Exception:
                    pass
                # Try to get all options for the select
                options = sel.find_elements(By.TAG_NAME, "option")
                option_texts = [opt.text.strip() for opt in options]
                if options and len(option_texts) > 1:
                    # Always pass the question and options to AI
                    ai_answer = ai_response_generator.generate_response(
                        label_text, response_type="choice", options=list(enumerate(option_texts)), jd=jd
                    )
                    if ai_answer is not None and 0 <= ai_answer < len(options):
                        options[ai_answer].click()
                    else:
                        # fallback: select 'Prefer not to say' or first
                        for i, opt in enumerate(options):
                            if 'prefer not' in opt.text.lower():
                                opt.click()
                                break
                        else:
                            options[0].click()
                else:
                    # If no options found, fallback to text answer
                    ai_answer = ai_response_generator.generate_response(label_text, response_type="text", jd=jd)
                    sel.send_keys(ai_answer)
                random_delay()
            except Exception as e:
                print(f"Could not fill select {sel.get_attribute('id')}: {e}")
        random_delay(0.8, 1.5)
        submit_btn = browser.find_element(By.XPATH, "//button[contains(text(), 'Submit application')]")
        human_scroll(browser, submit_btn)
        submit_btn.click()
        print("Greenhouse application submitted successfully.")
        random_delay(2, 2.5)
        return True
    except Exception as e:
        print(f"Error during Greenhouse application: {e}")
        return False

if __name__ == "__main__":
    import sys
    import yaml
    from ai_response_generator import AIResponseGenerator
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    # Example usage: python external_applications.py <application_url>
    if len(sys.argv) < 2:
        print("Usage: python external_applications.py <application_url>")
        sys.exit(1)
    url = sys.argv[1]

    # Load config.yaml for real personal info and other parameters
    with open("config.prod.yaml", "r") as f:
        config = yaml.safe_load(f)

    personal_info = config.get('personalInfo', {})
    experience = config.get('experience', {})
    languages = config.get('languages', {})
    checkboxes = config.get('checkboxes', {})
    eeo = config.get('eeo', {})
    salary_minimum = config.get('salaryMinimum', None)
    resume_dir = config.get('uploads', {}).get('resume', '')
    cover_letter_dir = config.get('uploads', {}).get('coverLetter', '')
    ollama_model = config.get('ollamaModel', 'your-model')
    text_resume_path = config.get('textResume', None)
    debug = config.get('debug', False)
    api_key = config.get('openaiApiKey', None)

    # Use the real AIResponseGenerator
    ai_response_generator = AIResponseGenerator(
        api_key=api_key,
        personal_info=personal_info,
        experience=experience,
        languages=languages,
        resume_path=resume_dir,
        checkboxes=checkboxes,
        ollama_model=ollama_model,
        text_resume_path=text_resume_path,
        debug=debug
    )

    # Setup Selenium
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    # Remove headless for visible Chrome
    # chrome_options.add_argument('--headless=new')
    browser = webdriver.Chrome(options=chrome_options)
    browser.get(url)
    random_delay(2, 2.5)

    # Simple detection logic
    page_source = browser.page_source.lower()
    if 'ashby' in page_source:
        print("Detected Ashby application form.")
        apply_to_ashby(browser, personal_info, resume_dir, ai_response_generator, eeo=eeo, salary_minimum=salary_minimum)
    elif 'greenhouse' in page_source or 'grnh.se' in url:
        print("Detected Greenhouse application form.")
        apply_to_greenhouse(browser, personal_info, resume_dir, cover_letter_dir, ai_response_generator)
    else:
        print("Unknown application type. Please extend detection logic.")
    browser.quit()