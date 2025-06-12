"""Utility functions for file operations, primarily focused on CSV file writing.

This module provides functions to log job application details and unprepared
interview questions to CSV files.
"""
import csv
from datetime import datetime
from typing import List, Any # Added for type hinting, though Any might not be strictly needed here yet.

def write_to_file(file_name: str, company: str, job_title: str, link: str, location: str, search_location: str) -> None:
    """Appends a record of a job application to a CSV file.

    The CSV file will be named `<file_name>.csv`. Each record includes
    company name, job title, application link, location, search location,
    and the timestamp of the entry.

    Args:
        file_name: The base name for the CSV file (without .csv extension).
        company: The name of the company.
        job_title: The job title.
        link: URL to the job application.
        location: The location of the job.
        search_location: The location used in the job search.
    """
    to_write: List[Any] = [company, job_title, link, location, search_location, datetime.now()]
    file_path: str = file_name + ".csv"
    print(f'updated {file_path}.')
    with open(file_path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(to_write)

def record_unprepared_question(file_name: str, answer_type: str, question_text: str, airesponse: str = "") -> None:
    """Records an unprepared interview question and its AI-generated response to a CSV file.

    The CSV file will be named `<file_name>.csv`. Each record includes
    the answer type, the question text, and the AI's response.

    Args:
        file_name: The base name for the CSV file (without .csv extension).
        answer_type: The type of answer expected (e.g., "text", "behavioral").
        question_text: The text of the unprepared question.
        airesponse: The AI-generated response to the question. Defaults to "".
    """
    to_write: List[str] = [answer_type, question_text, airesponse]
    file_path: str = file_name + ".csv"
    try:
        # Attempt to write the question and response to the CSV file.
        with open(file_path, 'a', newline='', encoding='utf-8') as f: # Added newline='' and encoding for consistency
            writer = csv.writer(f)
            writer.writerow(to_write)
            print(f'Updated {file_path} with {to_write}.')
    # TODO: Consider making this exception clause more specific to catch expected errors.
    except Exception as e: # Made exception catching more specific and printing the error
        print(f"Failed to update unprepared questions log for '{file_path}' due to: {e}")
        print(f"Question text: {question_text}")
