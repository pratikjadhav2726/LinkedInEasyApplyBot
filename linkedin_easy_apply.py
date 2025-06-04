from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from datetime import date, datetime
from itertools import product
from ai_response_generator import AIResponseGenerator
import time, random, csv, pyautogui, traceback, os, re
from utils import enter_text, select_dropdown, radio_select, scroll_slow, get_base_search_url
from external_applications import apply_to_ashby, apply_to_greenhouse
from file_utils import write_to_file, record_unprepared_question

class LinkedinEasyApply:
    def __init__(self, parameters, driver):
        self.browser = driver
        self.email = parameters['email']
        self.password = parameters['password']
        self.openai_api_key = parameters.get('openaiApiKey', '')  # Get API key with empty default
        self.model_name = parameters.get('modelName', '')  # Unified model selection
        self.disable_lock = parameters['disableAntiLock']
        self.company_blacklist = parameters.get('companyBlacklist', []) or []
        self.title_blacklist = parameters.get('titleBlacklist', []) or []
        self.poster_blacklist = parameters.get('posterBlacklist', []) or []
        self.positions = parameters.get('positions', [])
        self.locations = parameters.get('locations', [])
        self.residency = parameters.get('residentStatus', [])
        self.base_search_url = get_base_search_url(parameters)
        self.seen_jobs = []
        self.file_name = "output"
        self.unprepared_questions_file_name = "unprepared_questions"
        self.output_file_directory = parameters['outputFileDirectory']
        self.resume_dir = parameters['uploads']['resume']
        self.text_resume = parameters.get('textResume', '')
        self.docx_resume = parameters.get('docxResume','')
        if 'coverLetter' in parameters['uploads']:
            self.cover_letter_dir = parameters['uploads']['coverLetter']
        else:
            self.cover_letter_dir = ''
        self.checkboxes = parameters.get('checkboxes', [])
        self.university_gpa = parameters['universityGpa']
        self.salary_minimum = parameters['salaryMinimum']
        self.notice_period = int(parameters['noticePeriod'])
        self.languages = parameters.get('languages', [])
        self.experience = parameters.get('experience', [])
        self.personal_info = parameters.get('personalInfo', [])
        self.eeo = parameters.get('eeo', [])
        self.experience_default = int(self.experience['default'])
        self.debug = parameters.get('debug', False)
        self.evaluate_job_fit = parameters.get('evaluateJobFit', True)
        self.tailor_resume = parameters.get('tailorResume', True)
        self.ai_response_generator = AIResponseGenerator(
            api_key=self.openai_api_key,
            personal_info=self.personal_info,
            experience=self.experience,
            languages=self.languages,
            resume_path=self.resume_dir,
            checkboxes=self.checkboxes,
            text_resume_path=self.text_resume,
            debug=self.debug,
            model_name=self.model_name
        )

    def login(self):
        try:
            # Check if the "chrome_bot" directory exists
            print("Attempting to restore previous session...")
            if os.path.exists("chrome_bot"):
                self.browser.get("https://www.linkedin.com/feed/")
                time.sleep(random.uniform(5, 10))

                # Check if the current URL is the feed page
                if self.browser.current_url != "https://www.linkedin.com/feed/":
                    print("Feed page not loaded, proceeding to login.")
                    self.load_login_page_and_login()
            else:
                print("No session found, proceeding to login.")
                self.load_login_page_and_login()

        except TimeoutException:
            print("Timeout occurred, checking for security challenges...")
            self.security_check()
            # raise Exception("Could not login!")

    def security_check(self):
        current_url = self.browser.current_url
        page_source = self.browser.page_source

        if '/checkpoint/challenge/' in current_url or 'security check' in page_source or 'quick verification' in page_source:
            input("Please complete the security check and press enter on this console when it is done.")
            time.sleep(random.uniform(5.5, 10.5))

    def load_login_page_and_login(self):
        self.browser.get("https://www.linkedin.com/login")

        # Wait for the username field to be present
        WebDriverWait(self.browser, 10).until(
            EC.presence_of_element_located((By.ID, "username"))
        )

        self.browser.find_element(By.ID, "username").send_keys(self.email)
        self.browser.find_element(By.ID, "password").send_keys(self.password)
        self.browser.find_element(By.CSS_SELECTOR, ".btn__primary--large").click()

        # Wait for the feed page to load after login
        WebDriverWait(self.browser, 10).until(
            EC.url_contains("https://www.linkedin.com/feed/")
        )

        time.sleep(random.uniform(5, 10))

    def start_applying(self):
        searches = list(product(self.positions, self.locations))
        random.shuffle(searches)

        page_sleep = 0
        minimum_time = 60 * 2  # minimum time bot should run before taking a break
        minimum_page_time = time.time() + minimum_time

        for (position, location) in searches:
            location_url = "&location=" + location
            job_page_number = -1

            print("Starting the search for " + position + " in " + location + ".")

            try:
                while True:
                    page_sleep += 1
                    job_page_number += 1
                    print("Going to job page " + str(job_page_number))
                    self.next_job_page(position, location_url, job_page_number)
                    time.sleep(random.uniform(1.5, 3.5))
                    print("Starting the application process for this page...")
                    self.apply_jobs(location)
                    print("Job applications on this page have been successfully completed.")

                    time_left = minimum_page_time - time.time()
                    if time_left > 0:
                        print("Sleeping for " + str(time_left) + " seconds.")
                        time.sleep(time_left)
                        minimum_page_time = time.time() + minimum_time
                    if page_sleep % 5 == 0:
                        sleep_time = random.randint(180, 300)  # Changed from 500, 900 {seconds}
                        print("Sleeping for " + str(sleep_time / 60) + " minutes.")
                        time.sleep(sleep_time)
                        page_sleep += 1
            except:
                traceback.print_exc()
                pass

            time_left = minimum_page_time - time.time()
            if time_left > 0:
                print("Sleeping for " + str(time_left) + " seconds.")
                time.sleep(time_left)
                minimum_page_time = time.time() + minimum_time
            if page_sleep % 5 == 0:
                sleep_time = random.randint(500, 900)
                print("Sleeping for " + str(sleep_time / 60) + " minutes.")
                time.sleep(sleep_time)
                page_sleep += 1

    def apply_jobs(self, location):
        no_jobs_text = ""
        try:
            no_jobs_element = self.browser.find_element(By.CLASS_NAME,
                                                        'jobs-search-two-pane__no-results-banner--expand')
            no_jobs_text = no_jobs_element.text
        except:
            pass
        if 'No matching jobs found' in no_jobs_text:
            raise Exception("No more jobs on this page.")

        if 'unfortunately, things are' in self.browser.page_source.lower():
            raise Exception("No more jobs on this page.")
        try:
            with open("output.csv", 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                self.seen_jobs = [row[2] for row in reader if len(row) > 2]  # Assuming the link is in the 3rd column
        except FileNotFoundError:
            print("output.csv not found. Starting with an empty seen_jobs list.")
        except Exception as e:
            print(f"Error reading output.csv: {e}")
        job_results_header = ""
        maybe_jobs_crap = ""
        job_results_header = self.browser.find_element(By.CLASS_NAME, "jobs-search-results-list__text")
        maybe_jobs_crap = job_results_header.text

        if 'Jobs you may be interested in' in maybe_jobs_crap:
            raise Exception("Nothing to do here, moving forward...")

        try:
            # TODO: Can we simply use class name scaffold-layout__list for the scroll (necessary to show all li in the dom?)? Does it need to be the ul within the scaffold list?
            #      Then we can simply get all the li scaffold-layout__list-item elements within it for the jobs

            # Define the XPaths for potentially different regions
            xpath_region1 = "/html/body/div[6]/div[3]/div[4]/div/div/main/div/div[2]/div[1]/div"
            xpath_region2 = "/html/body/div[5]/div[3]/div[4]/div/div/main/div/div[2]/div[1]/div"
            job_list = []

            # Attempt to locate the element using XPaths
            try:
                job_results = self.browser.find_element(By.XPATH, xpath_region1)
                ul_xpath = "/html/body/div[6]/div[3]/div[4]/div/div/main/div/div[2]/div[1]/div/ul"
                ul_element = self.browser.find_element(By.XPATH, ul_xpath)
                ul_element_class = ul_element.get_attribute("class").split()[0]
                print(f"Found using xpath_region1 and detected ul_element as {ul_element_class} based on {ul_xpath}")

            except NoSuchElementException:
                job_results = self.browser.find_element(By.XPATH, xpath_region2)
                ul_xpath = "/html/body/div[5]/div[3]/div[4]/div/div/main/div/div[2]/div[1]/div/ul"
                ul_element = self.browser.find_element(By.XPATH, ul_xpath)
                ul_element_class = ul_element.get_attribute("class").split()[0]
                print(f"Found using xpath_region2 and detected ul_element as {ul_element_class} based on {ul_xpath}")

            # Extract the random class name dynamically
            random_class = job_results.get_attribute("class").split()[0]
            print(f"Random class detected: {random_class}")

            # Use the detected class name to find the element
            job_results_by_class = self.browser.find_element(By.CSS_SELECTOR, f".{random_class}")
            print(f"job_results: {job_results_by_class}")
            print("Successfully located the element using the random class name.")

            # Scroll logic (currently disabled for testing)
            scroll_slow(job_results_by_class)  # Scroll down
            scroll_slow(job_results_by_class, step=300, reverse=True)  # Scroll up

            # Find job list elements
            job_list = self.browser.find_elements(By.CLASS_NAME, ul_element_class)[0].find_elements(By.CLASS_NAME, 'scaffold-layout__list-item')
            print(f"Found {len(job_list)} jobs on this page")

            if len(job_list) == 0:
                raise Exception("No more jobs on this page.")  # TODO: Seemed to encounter an error where we ran out of jobs and didn't go to next page, perhaps because I didn't have scrolling on?

        except NoSuchElementException:
            print("No job results found using the specified XPaths or class.")

        except Exception as e:
            print(f"An unexpected error occurred: {e}")

        for job_tile in job_list:
            job_title, company, poster, job_location, apply_method, link = "", "", "", "", "", ""

            try:
                ## patch to incorporate new 'verification' crap by LinkedIn
                # job_title = job_tile.find_element(By.CLASS_NAME, 'job-card-list__title').text # original code
                job_title_element = job_tile.find_element(By.CLASS_NAME, 'job-card-list__title--link')
                job_title = job_title_element.find_element(By.TAG_NAME, 'strong').text

                link = job_tile.find_element(By.CLASS_NAME, 'job-card-list__title--link').get_attribute('href').split('?')[0]
            except:
                pass
            try:
                # company = job_tile.find_element(By.CLASS_NAME, 'job-card-container__primary-description').text # original code
                company = job_tile.find_element(By.CLASS_NAME, 'artdeco-entity-lockup__subtitle').text
            except:
                pass
            try:
                # get the name of the person who posted for the position, if any is listed
                hiring_line = job_tile.find_element(By.XPATH, '//span[contains(.,\' is hiring for this\')]')
                hiring_line_text = hiring_line.text
                name_terminating_index = hiring_line_text.find(' is hiring for this')
                if name_terminating_index != -1:
                    poster = hiring_line_text[:name_terminating_index]
            except:
                pass
            try:
                job_location = job_tile.find_element(By.CLASS_NAME, 'job-card-container__metadata-item').text
            except:
                pass
            try:
                apply_method = job_tile.find_element(By.CLASS_NAME, 'job-card-container__apply-method').text
            except:
                pass

            contains_blacklisted_keywords = False
            job_title_parsed = job_title.lower().split(' ')
            
            for word in self.title_blacklist:
                if word.lower() in job_title_parsed:
                    contains_blacklisted_keywords = True
                    break

            if company.lower() not in [word.lower() for word in self.company_blacklist] and \
                    poster.lower() not in [word.lower() for word in self.poster_blacklist] and \
                    contains_blacklisted_keywords is False and link not in self.seen_jobs:
                try:
                    # Click the job to load description
                    max_retries = 3
                    retries = 0
                    while retries < max_retries:
                        try:
                            # TODO: This is throwing an exception when running out of jobs on a page
                            job_el = job_tile.find_element(By.CLASS_NAME, 'job-card-list__title--link')
                            job_el.click()
                            break
                        except StaleElementReferenceException:
                            retries += 1
                            continue

                    time.sleep(random.uniform(3, 5))

                    # TODO: Check if the job is already applied or the application has been reached
                    # "You’ve reached the Easy Apply application limit for today. Save this job and come back tomorrow to continue applying."
                    # Do this before evaluating job fit to save on API calls
                    if self.tailor_resume:
                        try:
                            job_description = self.browser.find_element(
                                By.ID, 'job-details'
                            ).text 
                            replacements = self.ai_response_generator.get_tailored_skills_replacements(job_description)
                            self.ai_response_generator.tailor_resume_pdf(replacements)
                        except:
                            print("Could not load job description and tailorResume")
                    if self.evaluate_job_fit:
                        try:
                            # Get job description
                            job_description = self.browser.find_element(
                                By.ID, 'job-details'
                            ).text  

                            # Evaluate if we should apply
                            if not self.ai_response_generator.evaluate_job_fit(job_title, job_description):
                                print("Skipping application: Job requirements not aligned with candidate profile per AI evaluation.")
                                continue
                        except:
                            print("Could not load job description")

                    try:
                        done_applying = self.apply_to_job()
                        if done_applying:
                            print(f"Application sent to {company} for the position of {job_title}.")
                        else:
                            print(f"An application for a job at {company} has been submitted earlier.")
                    except:
                        temp = self.file_name
                        self.file_name = "failed"
                        print("Failed to apply to job. Please submit a bug report with this link: " + link)
                        try:
                            write_to_file(self.file_name, company, job_title, link, job_location, location)
                        except:
                            pass
                        self.file_name = temp
                        print(f'updated {temp}.')

                    try:
                        write_to_file(self.file_name, company, job_title, link, job_location, location)
                    except Exception:
                        print(
                            f"Unable to save the job information in the file. The job title {job_title} or company {company} cannot contain special characters,")
                        traceback.print_exc()
                except:
                    traceback.print_exc()
                    print(f"Could not apply to the job in {company}")
                    pass
            else:
                print(f"Job for {company} by {poster} contains a blacklisted word {word}.")

            self.seen_jobs += link
    def apply_to_job(self):
        easy_apply_button = None

        try:
            easy_apply_button = self.browser.find_element(By.CLASS_NAME, 'jobs-apply-button')
        except:
            return False

        try:
            job_description_area = self.browser.find_element(By.ID, "job-details")
            print (f"{job_description_area}")
            scroll_slow(job_description_area, end=1600)
            scroll_slow(job_description_area, end=1600, step=400, reverse=True)
        except:
            pass

        print("Starting the job application...")
        easy_apply_button.click()
        time.sleep(3)  # Wait for redirect/new tab

        # --- New Logic: Check for External Application ---
        main_window = self.browser.current_window_handle
        all_windows = self.browser.window_handles

        # If a new window/tab is opened, switch to it
        for handle in all_windows:
            if handle != main_window:
                self.browser.switch_to.window(handle)
                current_url = self.browser.current_url
                print("Redirected to:", current_url)
                
                # If it's Greenhouse, handle with a new function
                if "greenhouse.io" in current_url:
                    try:
                        success = apply_to_greenhouse(
                            self.browser,
                            self.personal_info,
                            self.resume_dir,
                            getattr(self, 'cover_letter_dir', ''),
                            self.ai_response_generator
                        )
                        self.browser.close()
                        self.browser.switch_to.window(main_window)
                        return success
                    except Exception as e:
                        print("Greenhouse application failed:", e)
                        self.browser.close()
                        self.browser.switch_to.window(main_window)
                        return False
                # --- Ashby ---
                elif "ashbyhq.com" in current_url or "ashby" in current_url:
                    try:
                        success = apply_to_ashby(
                            self.browser,
                            self.personal_info,
                            self.resume_dir,
                            self.ai_response_generator
                        )
                        self.browser.close()
                        self.browser.switch_to.window(main_window)
                        return success
                    except Exception as e:
                        print("Ashby application failed:", e)
                        self.browser.close()
                        self.browser.switch_to.window(main_window)
                        return False

                # --- (Other external sites can be added here) ---

                # If no match, just close and switch back
                self.browser.close()
                self.browser.switch_to.window(main_window)
        button_text = ""
        submit_application_text = 'submit application'
        while submit_application_text not in button_text.lower():
            try:
                self.fill_up()
                next_button = self.browser.find_element(By.CLASS_NAME, "artdeco-button--primary")
                button_text = next_button.text.lower()
                if submit_application_text in button_text:
                    try:
                        self.unfollow()
                    except:
                        print("Failed to unfollow company.")
                time.sleep(random.uniform(1.5, 2.5))
                next_button.click()
                time.sleep(random.uniform(3.0, 5.0))

                # Newer error handling
                error_messages = [
                    'enter a valid',
                    'enter a decimal',
                    'Enter a whole number'
                    'Enter a whole number between 0 and 99',
                    'file is required',
                    'whole number',
                    'make a selection',
                    'select checkbox to proceed',
                    'saisissez un numéro',
                    '请输入whole编号',
                    '请输入decimal编号',
                    '长度超过 0.0',
                    'Numéro de téléphone',
                    'Introduce un número de whole entre',
                    'Inserisci un numero whole compreso',
                    'Preguntas adicionales',
                    'Insira um um número',
                    'Cuántos años'
                    'use the format',
                    'A file is required',
                    '请选择',
                    '请 选 择',
                    'Inserisci',
                    'wholenummer',
                    'Wpisz liczb',
                    'zakresu od',
                    'tussen'
                ]

                if any(error in self.browser.page_source.lower() for error in error_messages):
                    raise Exception("Failed answering required questions or uploading required files.")
            except:
                traceback.print_exc()
                self.browser.find_element(By.CLASS_NAME, 'artdeco-modal__dismiss').click()
                time.sleep(random.uniform(3, 5))
                self.browser.find_elements(By.CLASS_NAME, 'artdeco-modal__confirm-dialog-btn')[0].click()
                time.sleep(random.uniform(3, 5))
                raise Exception("Failed to apply to job!")

        closed_notification = False
        time.sleep(random.uniform(3, 5))
        try:
            self.browser.find_element(By.CLASS_NAME, 'artdeco-modal__dismiss').click()
            closed_notification = True
        except:
            pass
        try:
            self.browser.find_element(By.CLASS_NAME, 'artdeco-toast-item__dismiss').click()
            closed_notification = True
        except:
            pass
        try:
            self.browser.find_element(By.CSS_SELECTOR, 'button[data-control-name="save_application_btn"]').click()
            closed_notification = True
        except:
            pass

        time.sleep(random.uniform(3, 5))

        if closed_notification is False:
            raise Exception("Could not close the applied confirmation window!")

        return True

    def home_address(self, form):
        print("Trying to fill up home address fields")
        try:
            groups = form.find_elements(By.CLASS_NAME, 'jobs-easy-apply-form-section__grouping')
            if len(groups) > 0:
                for group in groups:
                    lb = group.find_element(By.TAG_NAME, 'label').text.lower()
                    input_field = group.find_element(By.TAG_NAME, 'input')
                    if 'street' in lb:
                        self.enter_text(input_field, self.personal_info['Street address'])
                    elif 'city' in lb:
                        self.enter_text(input_field, self.personal_info['City'])
                        time.sleep(3)
                        input_field.send_keys(Keys.DOWN)
                        input_field.send_keys(Keys.RETURN)
                    elif 'zip' in lb or 'zip / postal code' in lb or 'postal' in lb:
                        self.enter_text(input_field, self.personal_info['Zip'])
                    elif 'state' in lb or 'province' in lb:
                        self.enter_text(input_field, self.personal_info['State'])
                    else:
                        pass
        except:
            pass

    def get_answer(self, question):
        if self.checkboxes[question]:
            return 'yes'
        else:
            return 'no'

    def additional_questions(self, form):
        print("Trying to fill up additional questions")

        questions = form.find_elements(By.CLASS_NAME, 'fb-dash-form-element')
        for question in questions:
            try:
                # Radio check
                radio_fieldset = question.find_element(By.TAG_NAME, 'fieldset')
                question_span = radio_fieldset.find_element(By.CLASS_NAME, 'fb-dash-form-element__label').find_elements(By.TAG_NAME, 'span')[0]
                radio_text = question_span.text.lower()
                print(f"Radio question text: {radio_text}")

                radio_labels = radio_fieldset.find_elements(By.TAG_NAME, 'label')
                radio_options = [(i, text.text.lower()) for i, text in enumerate(radio_labels)]
                print(f"radio options: {[opt[1] for opt in radio_options]}")
                
                if len(radio_options) == 0:
                    raise Exception("No radio options found in question")

                answer = None

                # Try to determine answer using existing logic
                if 'driver\'s licence' in radio_text or 'driver\'s license' in radio_text:
                    answer = self.get_answer('driversLicence')
                elif any(keyword in radio_text.lower() for keyword in
                         [
                             'Aboriginal', 'native', 'genous', 'tribe', 'first nations',
                             'native american', 'native hawaiian', 'inuit', 'metis', 'maori',
                             'aborigine', 'ancestral', 'native peoples', 'original people',
                             'first people', 'gender', 'race', 'disability', 'latino', 'torres',
                             'do you identify'
                         ]):
                    negative_keywords = ['prefer', 'decline', 'don\'t', 'specified', 'none', 'no']
                    answer = next((option for option in radio_options if
                                   any(neg_keyword in option[1].lower() for neg_keyword in negative_keywords)), None)

                elif 'assessment' in radio_text:
                    answer = self.get_answer("assessment")

                elif 'clearance' in radio_text:
                    answer = self.get_answer("securityClearance")

                elif 'north korea' in radio_text:
                    answer = 'no'

                elif 'previously employ' in radio_text or 'previous employ' in radio_text:
                    answer = 'no'

                elif 'authorized' in radio_text or 'authorised' in radio_text or 'legally' in radio_text:
                    answer = self.get_answer('legallyAuthorized')

                elif any(keyword in radio_text.lower() for keyword in
                         ['certified', 'certificate', 'cpa', 'chartered accountant', 'qualification']):
                    answer = self.get_answer('certifiedProfessional')

                elif 'urgent' in radio_text:
                    answer = self.get_answer('urgentFill')

                elif 'commut' in radio_text or 'on-site' in radio_text or 'hybrid' in radio_text or 'onsite' in radio_text:
                    answer = self.get_answer('commute')

                elif 'remote' in radio_text:
                    answer = self.get_answer('remote')

                elif 'background check' in radio_text:
                    answer = self.get_answer('backgroundCheck')

                elif 'drug test' in radio_text:
                    answer = self.get_answer('drugTest')

                elif 'currently living' in radio_text or 'currently reside' in radio_text or 'right to live' in radio_text:
                    answer = self.get_answer('residency')

                elif 'level of education' in radio_text:
                    for degree in self.checkboxes['degreeCompleted']:
                        if degree.lower() in radio_text:
                            answer = "yes"
                            break

                elif 'experience' in radio_text:
                    if self.experience_default > 0:
                        answer = 'yes'
                    else:
                        for experience in self.experience:
                            if experience.lower() in radio_text:
                                answer = "yes"
                                break

                elif 'data retention' in radio_text:
                    answer = 'no'

                elif 'sponsor' in radio_text:
                    answer = self.get_answer('requireVisa')
                
                to_select = None
                if answer is not None:
                    print(f"Choosing answer: {answer}")
                    i = 0
                    for radio in radio_labels:
                        if answer in radio.text.lower():
                            to_select = radio_labels[i]
                            break
                        i += 1
                    if to_select is None:
                        print("Answer not found in radio options")

                if to_select is None:
                    print("No answer determined")
                    

                    # Since no response can be determined, we use AI to identify the best responseif available, falling back to the final option if the AI response is not available
                    ai_response = self.ai_response_generator.generate_response(
                        question_text,
                        response_type="choice",
                        options=radio_options
                    )
                    if ai_response is not None:
                        to_select = radio_labels[ai_response]
                    else:
                        to_select = radio_labels[len(radio_labels) - 1]
                    record_unprepared_question(self.unprepared_questions_file_name, "radio", radio_text, ai_response)
                to_select.click()

                if radio_labels:
                    continue
            except Exception as e:
                print("An exception occurred while filling up radio field")

            # Questions check
            try:
                question_text = question.find_element(By.TAG_NAME, 'label').text.lower()
                print( question_text )  # TODO: Put logging behind debug flag

                txt_field_visible = False
                try:
                    txt_field = question.find_element(By.TAG_NAME, 'input')
                    txt_field_visible = True
                except:
                    try:
                        txt_field = question.find_element(By.TAG_NAME, 'textarea')  # TODO: Test textarea
                        txt_field_visible = True
                    except:
                        raise Exception("Could not find textarea or input tag for question")

                if 'numeric' in txt_field.get_attribute('id').lower():
                    # For decimal and integer response fields, the id contains 'numeric' while the type remains 'text' 
                    text_field_type = 'numeric'
                elif 'text' in txt_field.get_attribute('type').lower():
                    text_field_type = 'text'
                else:
                    raise Exception("Could not determine input type of input field!")

                to_enter = ''
                if 'experience' in question_text or 'how many years in' in question_text:
                    no_of_years = None
                    for experience in self.experience:
                        if experience.lower() in question_text:
                            no_of_years = int(self.experience[experience])
                            break
                    if no_of_years is None:
                        # self.record_unprepared_question(text_field_type, question_text)
                        ai_response = self.ai_response_generator.generate_response(
                                                                    question_text,
                                                                    response_type="numeric"
                                                                )
                        no_of_years = ai_response if ai_response is not None else int(self.experience_default)
                        record_unprepared_question(self.unprepared_questions_file_name, text_field_type, question_text, ai_response)
                    to_enter = no_of_years

                elif 'grade point average' in question_text:
                    to_enter = self.university_gpa

                elif 'first name' in question_text:
                    to_enter = self.personal_info['First Name']

                elif 'last name' in question_text:
                    to_enter = self.personal_info['Last Name']

                elif 'name' in question_text:
                    to_enter = self.personal_info['First Name'] + " " + self.personal_info['Last Name']

                elif 'pronouns' in question_text:
                    to_enter = self.personal_info['Pronouns']

                elif 'phone' in question_text:
                    to_enter = self.personal_info['Mobile Phone Number']

                elif 'linkedin' in question_text:
                    to_enter = self.personal_info['Linkedin']

                elif 'message to hiring' in question_text or 'cover letter' in question_text:
                    to_enter = self.personal_info['MessageToManager']

                    if not to_enter:
                        job_title = self.get_current_job_title()
                        job_description = self.get_current_job_description()
                        self.ai_response_generator.generate_response(
                        question_text,
                        response_type="text",
                        jd=job_description
                    )

                elif 'website' in question_text or 'github' in question_text or 'portfolio' in question_text:
                    to_enter = self.personal_info['Website']

                elif 'notice' in question_text or 'weeks' in question_text:
                    if text_field_type == 'numeric':
                        to_enter = int(self.notice_period)
                    else:
                        to_enter = str(self.notice_period)

                elif 'salary' in question_text or 'expectation' in question_text or 'compensation' in question_text or 'CTC' in question_text:
                    if text_field_type == 'numeric':
                        to_enter = int(self.salary_minimum)
                    else:
                        to_enter = float(self.salary_minimum)
                    

                # Since no response can be determined, we use AI to generate a response if available, falling back to 0 or empty string if the AI response is not available
                if text_field_type == 'numeric':
                    if not isinstance(to_enter, (int, float)):
                        ai_response = self.ai_response_generator.generate_response(
                            question_text,
                            response_type="numeric"
                        )
                        record_unprepared_question(self.unprepared_questions_file_name, text_field_type, question_text, ai_response)
                        to_enter = ai_response if ai_response is not None else 0
                elif to_enter == '':
                    ai_response = self.ai_response_generator.generate_response(
                        question_text,
                        response_type="text"
                    )
                    record_unprepared_question(self.unprepared_questions_file_name, text_field_type, question_text, ai_response)
                    to_enter = ai_response if ai_response is not None else " ‏‏‎ "

                enter_text(txt_field, to_enter)
                continue
            except:
                print("An exception occurred while filling up text field")  # TODO: Put logging behind debug flag

            # Date Check
            try:
                date_picker = question.find_element(By.CLASS_NAME, 'artdeco-datepicker__input ')
                date_picker.clear()
                date_picker.send_keys(date.today().strftime("%m/%d/%y"))
                time.sleep(3)
                date_picker.send_keys(Keys.RETURN)
                time.sleep(2)
                continue
            except:
                print("An exception occurred while filling up date picker field")  # TODO: Put logging behind debug flag

            # Dropdown check
            try:
                question_text = question.find_element(By.TAG_NAME, 'label').text.lower()
                print(f"Dropdown question text: {question_text}")  # TODO: Put logging behind debug flag
                dropdown_field = question.find_element(By.TAG_NAME, 'select')

                select = Select(dropdown_field)
                options = [options.text for options in select.options]
                print(f"Dropdown options: {options}")  # TODO: Put logging behind debug flag

                if 'proficiency' in question_text:
                    proficiency = "None"
                    for language in self.languages:
                        if language.lower() in question_text:
                            proficiency = self.languages[language]
                            break
                    select_dropdown(dropdown_field, proficiency)

                elif 'clearance' in question_text:
                    answer = self.get_answer('securityClearance')

                    choice = ""
                    for option in options:
                        if answer == 'yes':
                            choice = option
                        else:
                            if 'no' in option.lower():
                                choice = option
                    if choice == "":
                        record_unprepared_question(self.unprepared_questions_file_name, text_field_type, question_text)
                    select_dropdown(dropdown_field, choice)

                elif 'assessment' in question_text:
                    answer = self.get_answer('assessment')
                    choice = ""
                    for option in options:
                        if answer == 'yes':
                            choice = option
                        else:
                            if 'no' in option.lower():
                                choice = option
                    # if choice == "":
                    #    choice = options[len(options) - 1]
                    select_dropdown(dropdown_field, choice)

                elif 'commut' in question_text or 'on-site' in question_text or 'hybrid' in question_text or 'onsite' in question_text:
                    answer = self.get_answer('commute')

                    choice = ""
                    for option in options:
                        if answer == 'yes':
                            choice = option
                        else:
                            if 'no' in option.lower():
                                choice = option
                    # if choice == "":
                    #    choice = options[len(options) - 1]
                    select_dropdown(dropdown_field, choice)

                elif 'country code' in question_text:
                    select_dropdown(dropdown_field, self.personal_info['Phone Country Code'])

                elif 'north korea' in question_text:
                    choice = ""
                    for option in options:
                        if 'no' in option.lower():
                            choice = option
                    if choice == "":
                        choice = options[len(options) - 1]
                    select_dropdown(dropdown_field, choice)

                elif 'previously employed' in question_text or 'previous employment' in question_text:
                    choice = ""
                    for option in options:
                        if 'no' in option.lower():
                            choice = option
                    if choice == "":
                        choice = options[len(options) - 1]
                    select_dropdown(dropdown_field, choice)

                elif 'sponsor' in question_text:
                    answer = self.get_answer('requireVisa')
                    choice = ""
                    for option in options:
                        if answer == 'yes':
                            choice = option
                        else:
                            if 'no' in option.lower():
                                choice = option
                    if choice == "":
                        choice = options[len(options) - 1]
                    select_dropdown(dropdown_field, choice)

                elif 'above 18' in question_text.lower():  # Check for "above 18" in the question text
                    choice = ""
                    for option in options:
                        if 'yes' in option.lower():  # Select 'yes' option
                            choice = option
                    if choice == "":
                        choice = options[0]  # Default to the first option if 'yes' is not found
                    select_dropdown(dropdown_field, choice)

                elif 'currently living' in question_text or 'currently reside' in question_text:
                    answer = self.get_answer('residency')
                    choice = ""
                    for option in options:
                        if answer == 'yes':
                            choice = option
                        else:
                            if 'no' in option.lower():
                                choice = option
                    if choice == "":
                        choice = options[len(options) - 1]
                    select_dropdown(dropdown_field, choice)

                elif 'authorized' in question_text or 'authorised' in question_text:
                    answer = self.get_answer('legallyAuthorized')
                    choice = ""
                    for option in options:
                        if answer == 'yes':
                            # find some common words
                            choice = option
                        else:
                            if 'no' in option.lower():
                                choice = option
                    if choice == "":
                        choice = options[len(options) - 1]
                    select_dropdown(dropdown_field, choice)

                elif 'citizenship' in question_text:
                    answer = self.get_answer('legallyAuthorized')
                    choice = ""
                    for option in options:
                        if answer == 'yes':
                            if 'no' in option.lower():
                                choice = option
                    if choice == "":
                        choice = options[len(options) - 1]
                    select_dropdown(dropdown_field, choice)

                elif 'clearance' in question_text:
                    answer = self.get_answer('clearance')
                    choice = ""
                    for option in options:
                        if answer == 'yes':
                            choice = option
                        else:
                            if 'no' in option.lower():
                                choice = option
                    if choice == "":
                        choice = options[len(options) - 1]

                    select_dropdown(dropdown_field, choice)

                elif any(keyword in question_text.lower() for keyword in
                         [
                             'aboriginal', 'native', 'indigenous', 'tribe', 'first nations',
                             'native american', 'native hawaiian', 'inuit', 'metis', 'maori',
                             'aborigine', 'ancestral', 'native peoples', 'original people',
                             'first people', 'gender', 'race', 'disability', 'latino'
                         ]):
                    negative_keywords = ['prefer', 'decline', 'don\'t', 'specified', 'none']

                    choice = ""
                    choice = next((option for options in option.lower() if
                               any(neg_keyword in option.lower() for neg_keyword in negative_keywords)), None)

                    self.select_dropdown(dropdown_field, choice)

                elif 'email' in question_text:
                    continue  # assume email address is filled in properly by default

                elif 'experience' in question_text or 'understanding' in question_text or 'familiar' in question_text or 'comfortable' in question_text or 'able to' in question_text:
                    answer = 'no'
                    if self.experience_default > 0:
                        answer = 'yes'
                    else:
                        for experience in self.experience:
                            if experience.lower() in question_text and self.experience[experience] > 0:
                                answer = 'yes'
                                break
                    if answer == 'no':
                        # record unlisted experience as unprepared questions
                        record_unprepared_question(self.unprepared_questions_file_name, "dropdown", question_text)

                    choice = ""
                    for option in options:
                        if answer in option.lower():
                            choice = option
                    if choice == "":
                        choice = options[len(options) - 1]
                    select_dropdown(dropdown_field, choice)

                else:
                    print(f"Unhandled dropdown question: {question_text}")
                    

                    # Since no response can be determined, we use AI to identify the best responseif available, falling back "yes" or the final response if the AI response is not available
                    choice = options[len(options) - 1]
                    choices = [(i, option) for i, option in enumerate(options)]
                    ai_response = self.ai_response_generator.generate_response(
                        question_text,
                        response_type="choice",
                        options=choices
                    )
                    record_unprepared_question(self.unprepared_questions_file_name, "dropdown", question_text, ai_response)
                    if ai_response is not None:
                        choice = options[ai_response]
                    else:
                        choice = ""
                        for option in options:
                            if 'yes' in option.lower():
                                choice = option

                    print(f"Selected option: {choice}")
                    select_dropdown(dropdown_field, choice)
                continue
            except:
                print("An exception occurred while filling up dropdown field")  # TODO: Put logging behind debug flag

            # Checkbox check for agreeing to terms and service
            try:
                clickable_checkbox = question.find_element(By.TAG_NAME, 'label')
                clickable_checkbox.click()
            except:
                print("An exception occurred while filling up checkbox field")  # TODO: Put logging behind debug flag

    def unfollow(self):
        try:
            follow_checkbox = self.browser.find_element(By.XPATH,
                                                        "//label[contains(.,\'to stay up to date with their page.\')]").click()
            follow_checkbox.click()
        except:
            pass

    def send_resume(self):
        print("Trying to send resume")
        try:
            file_upload_elements = (By.CSS_SELECTOR, "input[name='file']")
            if len(self.browser.find_elements(file_upload_elements[0], file_upload_elements[1])) > 0:
                input_buttons = self.browser.find_elements(file_upload_elements[0], file_upload_elements[1])
                if len(input_buttons) == 0:
                    raise Exception("No input elements found in element")
                for upload_button in input_buttons:
                    upload_type = upload_button.find_element(By.XPATH, "..")\
                        .find_element(By.XPATH, "preceding-sibling::*")
                    if 'resume' in upload_type.text.lower():
                        upload_button.send_keys(self.resume_dir)
                    elif 'cover' in upload_type.text.lower():
                        if self.cover_letter_dir != '':
                            upload_button.send_keys(self.cover_letter_dir)
                        elif 'required' in upload_type.text.lower():
                            upload_button.send_keys(self.resume_dir)
        except:
            print("Failed to upload resume or cover letter!")
            pass

    def fill_up(self):
        try:
            easy_apply_modal_content = self.browser.find_element(By.CLASS_NAME, "jobs-easy-apply-modal__content")
            form = easy_apply_modal_content.find_element(By.TAG_NAME, 'form')
            try:
                label = form.find_element(By.TAG_NAME, 'h3').text.lower()
                if 'home address' in label:
                    self.home_address(form)
                elif 'contact info' in label:
                    self.contact_info(form)
                elif 'resume' in label:
                    self.send_resume()
                else:
                    self.additional_questions(form)
            except Exception as e:
                print("An exception occurred while filling up the form:")
                print(e)
        except:
            print("An exception occurred while searching for form in modal")

    def next_job_page(self, position, location, job_page):
        self.browser.get("https://www.linkedin.com/jobs/search/" + self.base_search_url +
                         "&keywords=" + position + location + "&start=" + str(job_page * 25))

        self.avoid_lock()

    def avoid_lock(self):
        if self.disable_lock:
            return

        pyautogui.keyDown('ctrl')
        pyautogui.press('esc')
        pyautogui.keyUp('ctrl')
        time.sleep(1.0)
        pyautogui.press('esc')