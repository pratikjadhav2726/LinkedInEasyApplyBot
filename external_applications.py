from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# Ashby application handler
def apply_to_ashby(browser, personal_info, resume_dir, ai_response_generator, jd=""):
    print("Starting Ashybq Application.")
    wait = WebDriverWait(browser, 20)
    try:
        # 1. Go to "Application" tab (if not already there)
        try:
            app_tab = browser.find_element(By.XPATH, "//span[contains(@class,'ashby-job-posting-right-pane-application-tab') and contains(text(),'Application')]")
            app_tab.click()
            time.sleep(1)
        except Exception:
            pass  # Already on tab or not present

        # 2. Upload resume (if the upload button exists and file not already attached)
        try:
            upload_btn = browser.find_element(By.XPATH, "//button[.//span[contains(text(),'Upload File')]]")
            upload_btn.click()
            file_input = browser.find_element(By.XPATH, "//input[@type='file' and @id='_systemfield_resume']")
            file_input.send_keys(resume_dir)
            print("Resume uploaded for autofill.")
            time.sleep(5)
        except Exception as e:
            print(f"Could not upload resume (may already be uploaded): {e}")

        # 3. Fill any empty text input fields
        text_inputs = browser.find_elements(By.XPATH, "//input[@type='text' or @type='email']")
        for inp in text_inputs:
            try:
                value = inp.get_attribute("value")
                if value and value.strip() != "":
                    continue
                label_text = ""
                try:
                    label_elem = browser.find_element(By.XPATH, f"//label[@for='{inp.get_attribute('id')}']")
                    label_text = label_elem.text.strip()
                except Exception:
                    pass
                if "name" in label_text.lower():
                    inp.clear()
                    inp.send_keys(personal_info.get("First Name", "") + " " + personal_info.get("Last Name", ""))
                elif "email" in label_text.lower():
                    inp.clear()
                    inp.send_keys(personal_info.get("Email", ""))
                elif "linkedin" in label_text.lower():
                    inp.clear()
                    inp.send_keys(personal_info.get("Linkedin", ""))
                elif "github" in label_text.lower():
                    inp.clear()
                    inp.send_keys(personal_info.get("GitHub", ""))
                elif "website" in label_text.lower() or "portfolio" in label_text.lower():
                    inp.clear()
                    inp.send_keys(personal_info.get("Website", ""))
                elif "city" in label_text.lower():
                    inp.clear()
                    inp.send_keys(personal_info.get("City", ""))
                elif "state" in label_text.lower():
                    inp.clear()
                    inp.send_keys(personal_info.get("State", ""))
                elif "zip" in label_text.lower() or "postal" in label_text.lower():
                    inp.clear()
                    inp.send_keys(personal_info.get("Zip", ""))
                elif "location" in label_text.lower():
                    inp.clear()
                    inp.send_keys(personal_info.get("Location", ""))
                elif "visa sponsership" in label_text.lower() or "h1b" in label_text.lower():
                    inp.clear()
                    inp.send_keys("yes")
                elif "work schedule" in label_text.lower():
                    inp.clear()
                    inp.send_keys("Yes")
                else:
                    ai_answer = ai_response_generator.generate_response(label_text, response_type="text", jd=jd)
                    inp.clear()
                    inp.send_keys(ai_answer)
            except Exception as e:
                print(f"Could not fill Ashby text input: {e}")

        # 4. Fill any empty textareas
        textareas = browser.find_elements(By.XPATH, "//textarea")
        for ta in textareas:
            try:
                value = ta.get_attribute("value")
                if value and value.strip() != "":
                    continue
                label_text = ""
                try:
                    label_elem = browser.find_element(By.XPATH, f"//label[@for='{ta.get_attribute('id')}']")
                    label_text = label_elem.text.strip()
                except Exception:
                    pass
                ai_answer = ai_response_generator.generate_response(label_text, response_type="text", jd=jd)
                ta.clear()
                ta.send_keys(ai_answer)
            except Exception as e:
                print(f"Could not fill Ashby textarea: {e}")

        # 5. Optionally handle selects (dropdowns) if needed
        # 6. Submit the form
        submit_btn = browser.find_element(By.XPATH, "//button[contains(@class,'ashby-application-form-submit-button')]")
        submit_btn.click()
        print("Ashby application submitted successfully.")
        time.sleep(2)
        return True
    except Exception as e:
        print(f"Error during Ashby application: {e}")
        return False

# Greenhouse application handler
def apply_to_greenhouse(browser, personal_info, resume_dir, cover_letter_dir, ai_response_generator, jd=""):
    print("Starting Greenhouse Application.")
    wait = WebDriverWait(browser, 15)
    try:
        wait.until(EC.presence_of_element_located((By.ID, "application-form")))
        browser.find_element(By.ID, "first_name").send_keys(personal_info['First Name'])
        browser.find_element(By.ID, "last_name").send_keys(personal_info['Last Name'])
        browser.find_element(By.ID, "email").send_keys(personal_info['Email'])
        try:
            phone_field = browser.find_element(By.ID, "phone")
            phone_value = personal_info.get('Mobile Phone Number', '')
            if phone_value:
                phone_field.send_keys(phone_value)
        except Exception:
            pass
        resume_input = browser.find_element(By.ID, "resume")
        resume_input.send_keys(resume_dir)
        try:
            if cover_letter_dir:
                cover_letter_input = browser.find_element(By.ID, "cover_letter")
                cover_letter_input.send_keys(cover_letter_dir)
        except Exception:
            pass
        question_inputs = browser.find_elements(By.XPATH, "//input[starts-with(@id, 'question_')]")
        for inp in question_inputs:
            try:
                qid = inp.get_attribute('id')
                label_text = ""
                try:
                    label_elem = browser.find_element(By.XPATH, f"//label[@for='{qid}']")
                    label_text = label_elem.text.strip()
                except Exception:
                    pass
                if "linkedin" in label_text.lower():
                    inp.clear()
                    inp.send_keys(personal_info.get("Linkedin", ""))
                elif "github" in label_text.lower() or "website" in label_text.lower():
                    inp.clear()
                    inp.send_keys(personal_info.get("Website", ""))
                elif "city" in label_text.lower():
                    inp.clear()
                    inp.send_keys(personal_info.get("City", ""))
                elif "state" in label_text.lower():
                    inp.clear()
                    inp.send_keys(personal_info.get("State", ""))
                elif "zip" in label_text.lower() or "postal" in label_text.lower():
                    inp.clear()
                    inp.send_keys(personal_info.get("Zip", ""))
                elif "visa sponsership" in label_text.lower() or "h1b" in label_text.lower():
                    inp.clear()
                    inp.send_keys("yes")
                elif "work schedule" in label_text.lower():
                    inp.clear()
                    inp.send_keys("Yes")
                else:
                    input_type = inp.get_attribute('type')
                    if input_type == "checkbox":
                        ai_answer = ai_response_generator.generate_response(label_text, response_type="text", jd="")
                        if ai_answer.strip().lower().startswith("y"):
                            if not inp.is_selected():
                                inp.click()
                    elif input_type == "radio":
                        ai_answer = ai_response_generator.generate_response(label_text, response_type="numeric", jd="")
                    else:
                        ai_answer = ai_response_generator.generate_response(label_text, response_type="text", jd="")
                        inp.clear()
                        inp.send_keys(ai_answer)
            except Exception as e:
                print(f"Could not fill input {inp.get_attribute('id')}: {e}")
        question_textareas = browser.find_elements(By.XPATH, "//textarea[starts-with(@id, 'question_')]")
        for ta in question_textareas:
            try:
                qid = ta.get_attribute('id')
                label_text = ""
                try:
                    label_elem = browser.find_element(By.XPATH, f"//label[@for='{qid}']")
                    label_text = label_elem.text.strip()
                except Exception:
                    pass
                ai_answer = ai_response_generator.generate_response(label_text, response_type="text", jd="")
                ta.clear()
                ta.send_keys(ai_answer)
            except Exception as e:
                print(f"Could not fill textarea {ta.get_attribute('id')}: {e}")
        time.sleep(1)
        submit_btn = browser.find_element(By.XPATH, "//button[contains(text(), 'Submit application')]")
        submit_btn.click()
        print("Greenhouse application submitted successfully.")
        time.sleep(2)
        return True
    except Exception as e:
        print(f"Error during Greenhouse application: {e}")
        return False
