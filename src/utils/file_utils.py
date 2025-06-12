import csv
from datetime import datetime

def write_to_file(file_name, company, job_title, link, location, search_location):
    to_write = [company, job_title, link, location, search_location, datetime.now()]
    file_path = file_name + ".csv"
    print(f'updated {file_path}.')
    with open(file_path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(to_write)

def record_unprepared_question(file_name, answer_type, question_text, airesponse=""):
    to_write = [answer_type, question_text, airesponse]
    file_path = file_name + ".csv"
    try:
        with open(file_path, 'a') as f:
            writer = csv.writer(f)
            writer.writerow(to_write)
            print(f'Updated {file_path} with {to_write}.')
    except:
        print("Special characters in questions are not allowed. Failed to update unprepared questions log.")
        print(question_text)
