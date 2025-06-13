import time, random, csv, pyautogui, os, re # Removed traceback here as it's added later
import traceback # Added traceback
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from datetime import date, datetime
from itertools import product
from pypdf import PdfReader
import PyPDF2 # Added for PDF manipulation
import requests
# from docx import Document # Removed docx import
# from docx2pdf import convert # Removed docx2pdf import
import json
import ollama
from litellm import completion
# import traceback # Ensure traceback is imported if used, it was added above.

class AIResponseGenerator:
    def __init__(self, api_key, personal_info, experience, languages, resume_path, checkboxes, model_name, text_resume_path=None, debug=False):
        self.personal_info = personal_info
        self.experience = experience
        self.languages = languages
        self.pdf_resume_path = resume_path # This will be used as input_pdf_path
        self.text_resume_path = text_resume_path
        self.checkboxes = checkboxes
        self._resume_content = None
        self._client = True
        self.model_name = model_name  # Unified model name for LiteLLM
        self.debug = debug
        self.resume_dir = resume_path # Initialize resume_dir, will be updated by tailor_resume_pdf

    @property
    def resume_content(self):
        if self._resume_content is None:
            # First try to read from text resume if available
            if self.text_resume_path:
                try:
                    with open(self.text_resume_path, 'r', encoding='utf-8') as f:
                        self._resume_content = f.read()
                        print("Successfully loaded text resume")
                        return self._resume_content
                except Exception as e:
                    print(f"Could not read text resume: {str(e)}")

            # Fall back to PDF resume if text resume fails or isn't available
            # Ensure this uses self.resume_dir which might be updated
            current_pdf_path = self.resume_dir if hasattr(self, 'resume_dir') and self.resume_dir else self.pdf_resume_path
            try:
                content = []
                # reader = PdfReader(self.pdf_resume_path) # Original line
                reader = PdfReader(current_pdf_path) # Use current_pdf_path
                for page in reader.pages:
                    content.append(page.extract_text())
                self._resume_content = "\n".join(content)
                print(f"Successfully loaded PDF resume from {current_pdf_path}")
            except Exception as e:
                print(f"Could not extract text from resume PDF ({current_pdf_path}): {str(e)}")
                self._resume_content = ""
        return self._resume_content

    def _build_context(self):
        return f"""
        Personal Information:
        - Name: {self.personal_info['First Name']} {self.personal_info['Last Name']}
        - Current Role: {self.experience.get('currentRole', 'AI Specialist')}
        - Current Location: {self.personal_info['City']}, {self.personal_info['State']}, United States
        - Authorized to work in the US: {'Yes' if self.checkboxes.get('legallyAuthorized') else 'No'}
        - Skills: {', '.join(self.experience.keys())}
        - Languages: {', '.join(f'{lang}: {level}' for lang, level in self.languages.items())}

        Resume Content:
        {self.resume_content}
        """
    def get_tailored_skills_replacements(self, job_description):
        # Step 1: Extract top 10 technical skills from job description
        system_prompt_1 = (
            "You are an expert resume and job description analyst.\n"
            "Your task is to read the job description below and extract the **top 10 technical skills or tools** that are essential for the role.\n"
            "Guidelines:\n"
            "- Return skills exactly as written in the job description (no synonyms, no rewording).\n"
            "- Include programming languages, libraries, frameworks, cloud platforms, APIs, machine learning techniques, tools, and standards mentioned.\n"
            "- Focus on the most important and unique technical terms. Do not include soft skills or generic phrases.\n"
            "- Return the output as a **comma-separated list** of skill keywords, in order of relevance and frequency.\n\n"
            f"Job Description:\n{job_description}"
        )
        try:
            response_1 = completion(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt_1}
                ]
            )
            job_skills = response_1.choices[0]['message']['content'].strip()
        except Exception as e:
            print(f"Error extracting job skills: {str(e)}")
            return None

        # Step 2: Suggest tailored skill replacements
        MAX_SKILL_REPLACEMENTS = 5
        system_prompt_2 = (
            "You are an AI assistant specialized in optimizing resumes for Applicant Tracking Systems (ATS).\n\n"
            "Your task:\n"
            "Given a list of resume skills and a list of job description skills, identify **exactly 5 skills** from the resume that can be replaced with **more relevant skills from the job description** to improve alignment and ATS score.\n\n"
            "Strict Rules:\n"
            "1. Each \"old\" skill must exist in the resume.\n"
            "2. Each \"new\" skill must exist in the job description and **must NOT already exist in the resume**.\n"
            "3. DO NOT suggest replacements that are already present in the resume in any form (no duplicates, no synonyms).\n"
            "4. Only suggest replacements where the old and new skills are **semantically similar** — i.e., they belong to the same category or purpose (e.g., frameworks, cloud platforms, dev tools, AI methods, APIs).\n"
            "5. Return **exactly 5 valid replacements**. If there are not enough matches, return fewer — do not force unrelated replacements.\n"
            "6. Your output must be a **JSON array**, in this exact format:\n\n"
            "[\n"
            "{\"old\": \"old_resume_skill\", \"new\": \"new_job_description_skill\"},\n"
            "{\"old\": \"old_resume_skill\", \"new\": \"new_job_description_skill\"},\n"
            "...\n"
            "]\n\n"
            "Do not include any explanation, heading, or commentary. Only output the JSON array."
        )
        user_content_2 = f"Job Skills:\n{job_skills}\n\nResume:\n{self.resume_content}"
        try:
            response_2 = completion(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt_2},
                    {"role": "user", "content": user_content_2}
                ]
            )
            answer = response_2.choices[0]['message']['content'].strip()
            replacements = json.loads(re.search(r'\[.*\]', answer, re.DOTALL).group())
            print(f"AI response: {answer}")
            return replacements[:MAX_SKILL_REPLACEMENTS]
        except Exception as e:
            print(f"Error using AI to generate resume tailoring skills: {str(e)}")
            return None

    def tailor_resume_pdf(self, replacements, input_pdf_path):
        try:
            if not input_pdf_path:
                print("Error: Input PDF path is not provided.")
                return None

            print(f"Starting to tailor PDF: {input_pdf_path}")
            pdf_reader = PyPDF2.PdfReader(input_pdf_path)
            pdf_writer = PyPDF2.PdfWriter()

            modified_texts = []

            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                try:
                    original_text = page.extract_text()
                    if original_text is None:
                        print(f"Warning: Could not extract text from page {page_num + 1}.")
                        # Add original page if text extraction fails
                        pdf_writer.add_page(page)
                        continue

                    modified_page_text = original_text
                    for r in replacements:
                        old_skill = r['old']
                        new_skill = r['new']
                        # Use re.compile for case-insensitive search and re.escape for literal matching
                        pattern = re.compile(re.escape(old_skill), re.IGNORECASE)
                        if pattern.search(modified_page_text):
                            modified_page_text = pattern.sub(new_skill, modified_page_text)
                            print(f"  Page {page_num + 1}: Replaced '{old_skill}' (case-insensitively) with '{new_skill}'")
                        else:
                            if self.debug:
                                print(f"  Page {page_num + 1}: Skill '{old_skill}' not found for replacement (checked case-insensitively).")

                    modified_texts.append({
                        "page": page_num + 1,
                        "original_text_snippet": original_text[:100] + "...", # Log snippet
                        "modified_text_snippet": modified_page_text[:100] + "..." # Log snippet
                    })

                    # Add the original page to the writer, as PyPDF2 doesn't support easy in-place text replacement
                    # The text replacement performed above is on the extracted string and not on the PDF page object directly.
                    pdf_writer.add_page(page)

                except Exception as e:
                    print(f"Error processing page {page_num + 1}: {str(e)}")
                    # Add original page in case of error processing it
                    pdf_writer.add_page(page)

            # Define dynamic output path based on input path
            directory = os.path.dirname(input_pdf_path)
            base_name = os.path.basename(input_pdf_path)
            name, ext = os.path.splitext(base_name)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_pdf_path = os.path.join(directory, f"{name}_tailored_{timestamp}{ext}")

            with open(output_pdf_path, 'wb') as output_file:
                pdf_writer.write(output_file)

            self.resume_dir = output_pdf_path  # Update the resume_dir with the path of the new PDF
            self._resume_content = None # Reset resume content so it's re-read next time

            print(f"Resume tailoring process complete. Modified PDF (original structure preserved) saved to: {output_pdf_path}")
            if modified_texts:
                print("Summary of text modifications (logged, not directly in PDF page content):")
                for mod_text in modified_texts:
                    print(f"  Page {mod_text['page']}:")
                    # print(f"    Original snippet: {mod_text['original_text_snippet']}") # Potentially verbose
                    print(f"    Attempted changes for page {mod_text['page']} logged above during processing.")
            print("Note: PyPDF2 does not support direct in-place text editing of PDF content streams easily. The original PDF structure is preserved. Text replacements are logged.")

        except FileNotFoundError:
            print(f"Error: The input PDF file was not found at {input_pdf_path}")
            return None
        except PyPDF2.errors.PdfReadError as pre:
            print(f"Error reading PDF {input_pdf_path}. It might be corrupted or password-protected: {str(pre)}")
            return None
        except Exception as e:
            print(f"Error during PDF tailoring: {str(e)}")
            traceback.print_exc()
            return None
        return output_pdf_path


    def generate_response(self, question_text, response_type="text", options=None, max_tokens=100, jd=""):
        """
        Generate a response using OpenAI's API
        
        Args:
            question_text: The application question to answer
            response_type: "text", "numeric", or "choice"
            options: For "choice" type, a list of tuples containing (index, text) of possible answers
            max_tokens: Maximum length of response
            
        Returns:
            - For text: Generated text response or None
            - For numeric: Integer value or None
            - For choice: Integer index of selected option or None
        """
        # if not self._client:
        #     return None
            
        try:
            context = self._build_context()
            # print(context)
            system_prompt = {
                "text": "You are a helpful assistant answering job application questions professionally and short. Use the candidate's background information and resume to personalize responses. Pretend you are the candidate.Only give the answer if you are sure from background. Otherwise return NA.",
                "numeric": "You are a helpful assistant providing numeric answers to job application questions. Based on the candidate's experience, provide a single number as your response. No explanation needed.",
                "choice": "You are a helpful assistant selecting the most appropriate answer choice for job application questions. Based on the candidate's background, select the best option by returning only its index number. No explanation needed."
            }[response_type]

            user_content = f"Using this candidate's background and resume:\n{context} JD{jd}\n\nPlease answer this job application question: {question_text}"
            if response_type == "choice" and options:
                options_text = "\n".join([f"{idx}: {text}" for idx, text in options])
                user_content += f"\n\nSelect the most appropriate answer by providing its index number from these options:\n{options_text}"

            response = completion(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ]
                # max_tokens=max_tokens,
                # temperature=0.7
            )
            
            answer = response.choices[0]['message']['content'].strip()
            print(f"AI response: {answer}")  # TODO: Put logging behind a debug flag
            
            if response_type == "numeric":
                # Extract first number from response
                numbers = re.findall(r'\d+', answer)
                if numbers:
                    return int(numbers[0])
                return 0
            elif response_type == "choice":
                # Extract the index number from the response
                numbers = re.findall(r'\d+', answer)
                if numbers and options:
                    index = int(numbers[0])
                    # Ensure index is within valid range
                    if 0 <= index < len(options):
                        return index
                return None  # Return None if the index is not within the valid range
                
            return answer
            
        except Exception as e:
            print(f"Error using AI to generate response: {str(e)}")
            return None

    def evaluate_job_fit(self, job_title, job_description):
        """
        Given a job description and my current resume, evaluate whether this job is worth applying for based on a 50–60% alignment threshold.
        
        Args:
            job_title: The title of the job posting
            job_description: The full job description text
            
        Returns:
            bool: True if should apply, False if should skip
        """
        # if not self._client:
        #     return True  # Proceed with application if AI not available
        try:
            system_prompt=""" Given Job description summarize it in 120 words, focus on qualifications and years of experience and technical skills. Expertise needed"""
            response = completion(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Job: {job_title}\n{job_description}"}
                ]
                # max_tokens=250 if self.debug else 1,  # Allow more tokens when debug is enabled
                # temperature=0.2  # Lower temperature for more consistent decisions
            )
            
            job_description = response.choices[0]['message']['content'].strip()
            # print(f"Job Summary: {job_description}")
            time.sleep(random.uniform(2,4))
        except Exception as e:
            print(f"Error evaluating job fit: {str(e)}")
            return True  # Proceed with application if evaluation fails
        try:
            context=self._build_context()
            # print(context)
            percent="80"
            system_prompt = """
                Based on the candidate’s resume and the job description, respond with APPLY if the resume matches at least 85 percent of the required qualifications and experience. Otherwise, respond with SKIP.
                Only return APPLY or SKIP.
            """
            #Consider the candidate's education level when evaluating whether they meet the core requirements. Having higher education than required should allow for greater flexibility in the required experience.
            
            if self.debug:
                pass
                # system_prompt += """
                # You are in debug mode. Return a detailed explanation of your reasoning for each requirement.

                # Return APPLY or SKIP followed by a brief explanation.

                # Format response as: APPLY/SKIP: [brief reason]"""
            else:
                system_prompt += """Return only APPLY or SKIP."""

            response = completion(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Job: {job_title}\n{job_description}\n\nCandidate:\n{context}"}
                ],
                temperature=0.9,
                max_completion_tokens=250 if self.debug else 1,  # Allow more tokens when debug is enabled
                # max_tokens=250 if self.debug else 1,  # Allow more tokens when debug is enabled
                # temperature=0.2  # Lower temperature for more consistent decisions
            )
            
            answer = response.choices[0]['message']['content'].strip()
            print(f"AI evaluation: {answer}")
            time.sleep(random.uniform(2,4))
            return answer.upper().startswith('A')  # True for APPLY, False for SKIP
            
        except Exception as e:
            print(f"Error evaluating job fit: {str(e)}")
            return True  # Proceed with application if evaluation fails
