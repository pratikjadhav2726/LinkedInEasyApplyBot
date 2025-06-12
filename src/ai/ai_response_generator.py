"""
Handles AI-driven text generation, resume tailoring, and job fit evaluation.

This module provides the AIResponseGenerator class, which interfaces with
AI models (via LiteLLM) to perform various tasks such as generating
responses to job application questions, tailoring resumes by replacing skills
in PDF files, and evaluating job fit based on job descriptions.
"""
import time, random, csv, pyautogui, os, re
import traceback
from typing import Optional, List, Dict, Tuple, Union # Added for type hinting

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
    """
    Manages AI interactions for generating responses, tailoring resumes, and evaluating job fit.

    This class uses an AI model (configured via LiteLLM) to understand and process
    text from resumes and job descriptions. It can modify PDF resumes by replacing
    skills and provide contextual answers to job application questions.
    """
    def __init__(self,
                 api_key: str,
                 personal_info: Dict[str, str],
                 experience: Dict[str, str],
                 languages: Dict[str, str],
                 resume_path: str,
                 checkboxes: Dict[str, bool],
                 model_name: str,
                 text_resume_path: Optional[str] = None,
                 debug: bool = False):
        """
        Initializes the AIResponseGenerator.

        Args:
            api_key (str): The API key for the AI service (not directly used by LiteLLM if model is local).
            personal_info (Dict[str, str]): Dictionary containing personal information (e.g., 'First Name', 'Last Name').
            experience (Dict[str, str]): Dictionary detailing professional experience and skills.
            languages (Dict[str, str]): Dictionary of languages and proficiency levels.
            resume_path (str): Path to the primary resume file (PDF expected for tailoring).
            checkboxes (Dict[str, bool]): Dictionary of boolean flags from user input (e.g., 'legallyAuthorized').
            model_name (str): The name of the AI model to be used via LiteLLM.
            text_resume_path (Optional[str]): Path to a plain text version of the resume. Defaults to None.
            debug (bool): If True, enables debug mode which may print more verbose logs. Defaults to False.
        """
        self.personal_info = personal_info
        self.experience = experience
        self.languages = languages
        self.pdf_resume_path = resume_path  # Path to the original PDF resume
        self.text_resume_path = text_resume_path
        self.checkboxes = checkboxes
        self._resume_content: Optional[str] = None  # Cached resume text content
        self._client = True # Placeholder, consider for actual API client status
        self.model_name = model_name
        self.debug = debug
        self.resume_dir: str = resume_path  # Directory/path for the current resume, updated after tailoring

    @property
    def resume_content(self) -> str:
        """
        Extracts and returns the text content of the resume.

        It first tries to load from a plain text resume if available.
        If not, it falls back to extracting text from the PDF resume specified
        by `self.resume_dir` (which could be the original or a tailored version).
        The content is cached after the first read.

        Returns:
            str: The extracted text content of the resume. Returns an empty
                 string if extraction fails.
        """
        if self._resume_content is None:
            # Attempt to load from the plain text version first
            if self.text_resume_path:
                try:
                    with open(self.text_resume_path, 'r', encoding='utf-8') as f:
                        self._resume_content = f.read()
                        print("Successfully loaded text resume")
                        return self._resume_content
                except Exception as e:
                    print(f"Could not read text resume: {str(e)}")

            # Fall back to PDF resume if text resume is not available or fails
            # Ensure this uses self.resume_dir, which might point to an updated (tailored) PDF
            current_pdf_path: str = self.resume_dir if hasattr(self, 'resume_dir') and self.resume_dir else self.pdf_resume_path
            try:
                content: List[str] = []
                # Use PdfReader (from pypdf) for text extraction from the current PDF path
                reader = PdfReader(current_pdf_path)
                for page in reader.pages:
                    content.append(page.extract_text())
                self._resume_content = "\n".join(content)
                print(f"Successfully loaded PDF resume from {current_pdf_path}")
            except Exception as e:
                print(f"Could not extract text from resume PDF ({current_pdf_path}): {str(e)}")
                self._resume_content = ""  # Set to empty string on failure
        return self._resume_content if self._resume_content is not None else ""

    def _build_context(self) -> str:
        """
        Constructs a context string containing personal and resume information.

        This context is used to inform the AI model when generating responses.

        Returns:
            str: A formatted string containing personal details, skills, languages,
                 and the full resume content.
        """
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

    def get_tailored_skills_replacements(self, job_description: str) -> Optional[List[Dict[str, str]]]:
        """
        Identifies skills in the resume to replace with skills from a job description.

        This method performs two steps:
        1. Extracts the top 10 technical skills from the provided job description using an AI model.
        2. Asks the AI model to suggest up to 5 replacements, where 'old' skills are from
           the resume and 'new' skills are from the job description. The new skills must
           not already be in the resume and should be semantically similar to the old ones.

        Args:
            job_description (str): The full text of the job description.

        Returns:
            Optional[List[Dict[str, str]]]: A list of dictionaries, where each dictionary
            has 'old' (skill from resume) and 'new' (skill from job description) keys.
            Returns None if an error occurs during the process.
        """
        # Step 1: Extract top 10 technical skills from the job description using AI
        system_prompt_1: str = (
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
            # Call AI model to extract job skills
            response_1 = completion(
                model=self.model_name,
                messages=[{"role": "system", "content": system_prompt_1}]
            )
            job_skills: str = response_1.choices[0]['message']['content'].strip()
        except Exception as e:
            print(f"Error extracting job skills: {str(e)}")
            return None

        # Step 2: Get AI suggestions for skill replacements
        MAX_SKILL_REPLACEMENTS: int = 5
        system_prompt_2: str = (
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
        user_content_2: str = f"Job Skills:\n{job_skills}\n\nResume:\n{self.resume_content}"
        try:
            # Call AI model to get skill replacement suggestions
            response_2 = completion(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt_2},
                    {"role": "user", "content": user_content_2}
                ]
            )
            answer: str = response_2.choices[0]['message']['content'].strip()
            # Extract JSON array from the AI's response
            match = re.search(r'\[.*\]', answer, re.DOTALL)
            if match:
                replacements: List[Dict[str, str]] = json.loads(match.group())
                if self.debug:
                    print(f"AI response for replacements: {answer}")
                return replacements[:MAX_SKILL_REPLACEMENTS]
            else:
                if self.debug:
                    print(f"AI response for replacements (no JSON found): {answer}")
                return [] # Return empty list if no valid JSON is found
        except Exception as e:
            print(f"Error using AI to generate resume tailoring skills: {str(e)}")
            return None

    def tailor_resume_pdf(self, replacements: List[Dict[str, str]], input_pdf_path: str) -> Optional[str]:
        """
        Modifies a PDF resume by attempting to replace specified skills in its text content.

        The function reads a PDF, extracts text from each page, and performs case-insensitive
        replacements of 'old' skills with 'new' skills as defined in the `replacements` list.
        Due to limitations in PyPDF2 for direct text stream editing, this function adds the
        original pages to a new PDF. The textual changes are logged to indicate what
        modifications would occur if direct editing were straightforward. The modified PDF
        (structurally identical to the original but with a new name) is saved with a timestamp.

        Args:
            replacements (List[Dict[str, str]]): A list of dictionaries, where each
                dictionary must have 'old': <skill_to_replace> and 'new': <skill_to_insert>.
            input_pdf_path (str): The file path of the PDF resume to be tailored.

        Returns:
            Optional[str]: The file path of the newly created tailored PDF if successful,
                           None otherwise.
        """
        try:
            if not input_pdf_path:
                print("Error: Input PDF path is not provided.")
                return None

            if self.debug:
                print(f"Starting to tailor PDF: {input_pdf_path} with replacements: {replacements}")

            # Initialize PDF reader and writer objects
            pdf_reader = PyPDF2.PdfReader(input_pdf_path)
            pdf_writer = PyPDF2.PdfWriter()

            modified_texts_log: List[Dict[str, Union[int, str]]] = [] # For logging changes

            # Iterate through each page of the PDF
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                try:
                    original_text: Optional[str] = page.extract_text()
                    if original_text is None:
                        if self.debug:
                            print(f"Warning: Could not extract text from page {page_num + 1}.")
                        pdf_writer.add_page(page) # Add original page if text extraction fails
                        continue

                    modified_page_text: str = original_text
                    # Perform replacements for the current page's text
                    for r_item in replacements:
                        old_skill: str = r_item['old']
                        new_skill: str = r_item['new']

                        # Compile regex for case-insensitive and literal replacement
                        pattern = re.compile(re.escape(old_skill), re.IGNORECASE)
                        if pattern.search(modified_page_text):
                            modified_page_text = pattern.sub(new_skill, modified_page_text)
                            if self.debug:
                                print(f"  Page {page_num + 1}: Replaced '{old_skill}' (case-insensitively) with '{new_skill}'")
                        else:
                            if self.debug:
                                print(f"  Page {page_num + 1}: Skill '{old_skill}' not found for replacement (checked case-insensitively).")

                    # Log information about text modification attempts
                    if original_text != modified_page_text:
                        modified_texts_log.append({
                            "page": page_num + 1,
                            "original_text_snippet": original_text[:100] + "...",
                            "modified_text_snippet": modified_page_text[:100] + "..."
                        })

                    # IMPORTANT: Add the *original* page to the writer.
                    # PyPDF2 does not easily support replacing text in an existing content stream
                    # while preserving formatting. The `modified_page_text` is for logging/record.
                    pdf_writer.add_page(page)

                except Exception as e:
                    print(f"Error processing page {page_num + 1}: {str(e)}")
                    pdf_writer.add_page(page) # Add original page in case of error during processing

            # Generate dynamic output path with timestamp
            directory: str = os.path.dirname(input_pdf_path)
            base_name: str = os.path.basename(input_pdf_path)
            name, ext = os.path.splitext(base_name)
            timestamp: str = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_pdf_path: str = os.path.join(directory, f"{name}_tailored_{timestamp}{ext}")

            # Write the output PDF
            with open(output_pdf_path, 'wb') as output_file:
                pdf_writer.write(output_file)

            # Update instance's resume directory and clear cached content
            self.resume_dir = output_pdf_path
            self._resume_content = None

            if self.debug:
                print(f"Resume tailoring process complete. Modified PDF (original structure preserved) saved to: {output_pdf_path}")
                if modified_texts_log:
                    print("Summary of text modifications (logged, actual PDF pages are original):")
                    for mod_text in modified_texts_log:
                        print(f"  Page {mod_text['page']}: Attempted changes logged during processing.")
                print("Note: PyPDF2 does not support direct in-place text editing of PDF content streams easily. Original PDF structure preserved. Text replacements logged.")
            return output_pdf_path

        except FileNotFoundError:
            print(f"Error: The input PDF file was not found at {input_pdf_path}")
            return None
        except PyPDF2.errors.PdfReadError as pre: # Specific PyPDF2 read error
            print(f"Error reading PDF {input_pdf_path}. It might be corrupted or password-protected: {str(pre)}")
            return None
        except Exception as e: # Catch any other exceptions
            print(f"Error during PDF tailoring: {str(e)}")
            traceback.print_exc()
            return None

    def generate_response(self,
                          question_text: str,
                          response_type: str = "text",
                          options: Optional[List[Tuple[int, str]]] = None,
                          max_tokens: int = 100, # Not directly used by LiteLLM completion's default call structure
                          jd: str = "") -> Optional[Union[str, int]]:
        """
        Generates a response to a given question using the AI model.

        The type of response (text, numeric, choice) can be specified.
        It uses the candidate's context (personal info, resume) to tailor the answer.

        Args:
            question_text (str): The job application question to answer.
            response_type (str): The type of response expected: "text", "numeric", or "choice".
                                 Defaults to "text".
            options (Optional[List[Tuple[int, str]]]): For "choice" type, a list of tuples,
                                                       where each tuple is (index, choice_text).
                                                       Defaults to None.
            max_tokens (int): Maximum number of tokens for the response (actual enforcement
                              depends on the LiteLLM model's configuration). Defaults to 100.
            jd (str): Job description text, appended to the context if provided. Defaults to "".

        Returns:
            Optional[Union[str, int]]: The generated response. This can be a string for "text" type,
                                     an integer for "numeric" or "choice" (index) type.
                                     Returns None if an error occurs.
        """
        # `_client` check can be used here if an actual client object status needs checking
        # if not self._client:
        #     return None
            
        try:
            context: str = self._build_context()
            if self.debug:
                print(f"Context for generate_response: {context[:200]}...") # Print snippet

            system_prompts: Dict[str, str] = {
                "text": "You are a helpful assistant answering job application questions professionally and concisely. "
                        "Use the candidate's background information and resume to personalize responses. "
                        "Pretend you are the candidate. Only give the answer if you are sure from background. Otherwise return 'NA'.",
                "numeric": "You are a helpful assistant providing numeric answers to job application questions. "
                           "Based on the candidate's experience, provide a single number as your response. No explanation needed.",
                "choice": "You are a helpful assistant selecting the most appropriate answer choice for job application questions. "
                          "Based on the candidate's background, select the best option by returning only its index number. No explanation needed."
            }
            current_system_prompt: str = system_prompts[response_type]

            user_content: str = (f"Using this candidate's background and resume:\n{context} "
                                 f"{('JD: ' + jd) if jd else ''}\n\n"
                                 f"Please answer this job application question: {question_text}")

            if response_type == "choice" and options:
                options_text: str = "\n".join([f"{idx}: {text}" for idx, text in options])
                user_content += f"\n\nSelect the most appropriate answer by providing its index number from these options:\n{options_text}"

            # Call AI model for response generation
            ai_response = completion(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": current_system_prompt},
                    {"role": "user", "content": user_content}
                ],
                # max_tokens=max_tokens, # Max_tokens can be passed if supported by the specific LiteLLM call/model
                # temperature=0.7      # Temperature can also be passed
            )
            
            answer: str = ai_response.choices[0]['message']['content'].strip()
            if self.debug:
                print(f"AI response for question '{question_text[:50]}...': {answer}")
            
            # Process response based on type
            if response_type == "numeric":
                numbers = re.findall(r'\d+', answer)
                return int(numbers[0]) if numbers else 0 # Return first number found or 0
            elif response_type == "choice":
                numbers = re.findall(r'\d+', answer)
                if numbers and options:
                    index = int(numbers[0])
                    if 0 <= index < len(options): # Validate index
                        return index
                return None # Return None if index is invalid or not found
                
            return answer # For "text" type
            
        except Exception as e:
            print(f"Error using AI to generate response for question '{question_text[:50]}...': {str(e)}")
            return None

    def evaluate_job_fit(self, job_title: str, job_description: str) -> bool:
        """
        Evaluates if a job is a good fit based on the candidate's resume and a job description.

        This method first asks the AI to summarize the job description, focusing on key
        qualifications. Then, it asks the AI to compare this summary and the candidate's
        context (resume, personal info) to decide if the job is an "APPLY" or "SKIP",
        targeting roughly an 85% match threshold.

        Args:
            job_title (str): The title of the job.
            job_description (str): The full job description text.

        Returns:
            bool: True if the AI deems the job a good fit ("APPLY"), False otherwise ("SKIP").
                  Returns True by default if an error occurs during evaluation to be permissive.
        """
        # Placeholder for actual client status check
        # if not self._client:
        #     return True

        summarized_jd: str = job_description
        try:
            # Step 1: Summarize the job description using AI
            summary_system_prompt: str = ("Given the job description, summarize it in about 120 words. "
                                          "Focus on required qualifications, years of experience, and key technical skills.")
            summary_response = completion(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": summary_system_prompt},
                    {"role": "user", "content": f"Job Title: {job_title}\nJob Description:\n{job_description}"}
                ]
            )
            summarized_jd = summary_response.choices[0]['message']['content'].strip()
            if self.debug:
                print(f"Summarized Job Description: {summarized_jd}")
            # Optional: Short delay if making rapid calls to an API
            # time.sleep(random.uniform(1, 2))
        except Exception as e:
            print(f"Error summarizing job description for '{job_title}': {str(e)}")
            # Proceed with full job_description if summarization fails

        try:
            # Step 2: Evaluate fit based on summarized JD and candidate context
            context: str = self._build_context()
            
            eval_system_prompt: str = (
                "Based on the candidate’s resume and the provided job description summary, "
                "respond with APPLY if the resume matches at least 85% of the required qualifications and experience. "
                "Otherwise, respond with SKIP. Only return the word APPLY or SKIP."
            )
            if self.debug:
                # Optionally provide more detailed instructions in debug mode (though LiteLLM might not use them)
                # eval_system_prompt += ("\nIn debug mode, you can also briefly state the main reason for your decision.")
                pass

            eval_response = completion(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": eval_system_prompt},
                    {"role": "user", "content": f"Job Title: {job_title}\nJob Description Summary:\n{summarized_jd}\n\nCandidate Context:\n{context}"}
                ],
                # temperature=0.5, # Adjust for more deterministic output if needed
                max_tokens=10 if self.debug else 5 # Limit tokens for APPLY/SKIP response
            )
            
            answer: str = eval_response.choices[0]['message']['content'].strip().upper()
            if self.debug:
                print(f"AI job fit evaluation for '{job_title}': {answer}")

            # Optional: Short delay
            # time.sleep(random.uniform(1, 2))
            return answer.startswith('APPLY')
            
        except Exception as e:
            print(f"Error evaluating job fit for '{job_title}': {str(e)}")
            return True # Default to True (apply) if evaluation fails
