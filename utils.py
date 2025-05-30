# Utility functions can be added here in the future as needed for modularity.

def enter_text(element, text):
    element.clear()
    element.send_keys(text)

def select_dropdown(element, text):
    from selenium.webdriver.support.ui import Select
    select = Select(element)
    select.select_by_visible_text(text)

def radio_select(element, label_text, clickLast=False):
    label = element.find_element_by_tag_name('label')
    if label_text in label.text.lower() or clickLast:
        label.click()

def scroll_slow(scrollable_element, start=0, end=3600, step=100, reverse=False):
    import time, random
    if reverse:
        start, end = end, start
        step = -step
    for i in range(start, end, step):
        scrollable_element.parent.execute_script("arguments[0].scrollTo(0, {})".format(i), scrollable_element)
        time.sleep(random.uniform(0.1, .6))

def get_base_search_url(parameters):
    remote_url = ""
    lessthanTenApplicants_url = ""
    newestPostingsFirst_url = ""

    if parameters.get('remote'):
        remote_url = "&f_WT=2"
    else:
        remote_url = ""
        # TO DO: Others &f_WT= options { WT=1 onsite, WT=2 remote, WT=3 hybrid, f_WT=1%2C2%2C3 }

    if parameters['lessthanTenApplicants']:
        lessthanTenApplicants_url = "&f_EA=true"

    if parameters['newestPostingsFirst']:
        newestPostingsFirst_url += "&sortBy=DD"

    level = 1
    experience_level = parameters.get('experienceLevel', [])
    experience_url = "f_E="
    for key in experience_level.keys():
        if experience_level[key]:
            experience_url += "%2C" + str(level)
        level += 1

    distance_url = "?distance=" + str(parameters['distance'])

    job_types_url = "f_JT="
    job_types = parameters.get('jobTypes', [])
    for key in job_types:
        if job_types[key]:
            job_types_url += "%2C" + key[0].upper()

    date_url = ""
    dates = {"all time": "", "month": "&f_TPR=r2592000", "week": "&f_TPR=r604800", "24 hours": "&f_TPR=r86400"}
    date_table = parameters.get('date', [])
    for key in date_table.keys():
        if date_table[key]:
            date_url = dates[key]
            break

    easy_apply_url = ""

    extra_search_terms = [distance_url, remote_url, lessthanTenApplicants_url, newestPostingsFirst_url, job_types_url, experience_url]
    extra_search_terms_str = '&'.join(
        term for term in extra_search_terms if len(term) > 0) + easy_apply_url + date_url

    return extra_search_terms_str
