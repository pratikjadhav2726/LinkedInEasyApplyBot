"""General utility functions for various tasks.

This module includes helpers for web automation (using Selenium) such as
entering text, selecting dropdowns, handling radio buttons, and scrolling,
as well as functions for constructing search URLs based on parameters.
"""
import time
import random
from typing import Dict, List, Any, Optional
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.remote.webdriver import WebDriver # For type hinting parent driver
from selenium.webdriver.support.ui import Select # Moved import to top
from selenium.webdriver.common.by import By # For modern find_element syntax

def enter_text(element: WebElement, text: str) -> None:
    """Clears an input field and enters the given text.

    Args:
        element: The Selenium WebElement representing the input field.
        text: The text to enter into the field.
    """
    element.clear()
    element.send_keys(text)

def select_dropdown(element: WebElement, text: str) -> None:
    """Selects an option from a dropdown menu by its visible text.

    Args:
        element: The Selenium WebElement representing the <select> element.
        text: The visible text of the option to select.
    """
    select = Select(element)
    select.select_by_visible_text(text)

def radio_select(element: WebElement, label_text: str, clickLast: bool = False) -> None:
    """Selects a radio button based on its label text.

    It searches for a <label> tag within the provided 'element'. If the
    label_text is found in the label's text (case-insensitive) or if
    clickLast is True, the label is clicked.
    This function assumes `element` is a container that includes the label.

    Args:
        element: The Selenium WebElement that is a container for the radio button
                 and its label.
        label_text: The text to search for in the radio button's label.
        clickLast: If True, clicks the label regardless of text match.
                   Useful if this is the last/only option.
    """
    # TODO: Replace find_element_by_tag_name with driver.find_element(By.TAG_NAME, 'label')
    # Assuming 'element' is a WebElement that can find other elements within it.
    # If 'element' is the WebDriver instance itself, this would need to be element.find_element(By.TAG_NAME, 'label')
    # For now, using the provided structure, assuming element.find_element_by_tag_name was intended.
    # Modern Selenium prefers element.find_element(By.TAG_NAME, 'label').
    try:
        # Attempt to find the label using the older find_element_by_tag_name for compatibility
        # with the original code structure.
        label = element.find_element(By.TAG_NAME, 'label') # Corrected to modern syntax
        if label_text.lower() in label.text.lower() or clickLast:
            label.click()
    except Exception: # Consider more specific exceptions
        # Fallback or error handling if label is not found or another issue occurs
        if clickLast: # If clickLast is true, and we couldn't find a label, maybe try clicking the element itself?
             # This depends on what 'element' is. If it's the input, this might work.
            try:
                element.click()
            except Exception as e_click:
                print(f"Could not click element directly after failing to find label: {e_click}")
        else:
            print(f"Could not find label for radio button with text '{label_text}' within the provided element.")


def scroll_slow(scrollable_element: WebElement, start: int = 0, end: int = 3600, step: int = 100, reverse: bool = False) -> None:
    """Scrolls a web element slowly in increments.

    Uses JavaScript `scrollTo` on the parent of the scrollable element.

    Args:
        scrollable_element: The Selenium WebElement that is scrollable.
                            Its parent is used for executing scroll script.
        start: The starting scroll position (in pixels).
        end: The ending scroll position (in pixels).
        step: The increment/decrement for each scroll step.
        reverse: If True, scrolls from end to start (upwards).
    """
    # Assumes scrollable_element.parent is a WebDriver or an element on which execute_script can be called.
    # More robustly, one might need to get the driver instance explicitly.
    driver: WebDriver = scrollable_element.parent # Type hint for clarity

    if reverse:
        current_pos, target_pos = end, start
        actual_step = -abs(step) # Ensure step is negative
    else:
        current_pos, target_pos = start, end
        actual_step = abs(step) # Ensure step is positive

    for i in range(current_pos, target_pos, actual_step):
        driver.execute_script("arguments[0].scrollTo(0, {})".format(i), scrollable_element)
        time.sleep(random.uniform(0.1, 0.6))
    # Ensure the final position is reached
    driver.execute_script("arguments[0].scrollTo(0, {})".format(target_pos), scrollable_element)


def get_base_search_url(parameters: Dict[str, Any]) -> str:
    """Constructs a LinkedIn search URL query string based on given parameters.

    Args:
        parameters: A dictionary containing search criteria like 'remote',
                    'lessthanTenApplicants', 'newestPostingsFirst',
                    'experienceLevel', 'distance', 'jobTypes', and 'date'.

    Returns:
        A string representing the query parameters to be appended to a base
        LinkedIn search URL.
    """
    remote_url: str = ""
    lessthan_ten_applicants_url: str = ""
    newest_postings_first_url: str = ""
    experience_url: str = "f_E=" # Base for experience level parameter
    job_types_url: str = "f_JT=" # Base for job types parameter
    date_url: str = ""

    # Handle 'remote' work preference
    # f_WT=1 (On-site), f_WT=2 (Remote), f_WT=3 (Hybrid)
    if parameters.get('remote'): # Assuming 'remote' is a boolean indicating fully remote
        remote_url = "&f_WT=2"
    # else: # No specific parameter if not exclusively remote; could add logic for hybrid/on-site if needed
        # TO DO: Others &f_WT= options { WT=1 onsite, WT=2 remote, WT=3 hybrid, f_WT=1%2C2%2C3 }
        # Based on current structure, only remote is explicitly handled.

    # Handle 'lessthanTenApplicants' filter
    if parameters.get('lessthanTenApplicants'): # Assuming boolean
        lessthan_ten_applicants_url = "&f_EA=true"

    # Handle 'newestPostingsFirst' sorting
    if parameters.get('newestPostingsFirst'): # Assuming boolean
        newest_postings_first_url = "&sortBy=DD" # DD for Date Descending (newest)

    # Handle 'experienceLevel'
    # Mapping: 1: Internship, 2: Entry level, 3: Associate, 4: Mid-Senior level, 5: Director, 6: Executive
    experience_level_map: Dict[str, str] = {
        "Internship": "1", "Entry level": "2", "Associate": "3",
        "Mid-Senior level": "4", "Director": "5", "Executive": "6"
    }
    selected_experience_levels: List[str] = []
    # Ensure 'experienceLevel' in parameters is a dictionary as expected by original .keys() call
    experience_level_params: Optional[Dict[str, bool]] = parameters.get('experienceLevel')
    if isinstance(experience_level_params, dict):
        for key, is_selected in experience_level_params.items():
            if is_selected and key in experience_level_map:
                selected_experience_levels.append(experience_level_map[key])

    if selected_experience_levels:
        experience_url += "%2C".join(selected_experience_levels)
    else:
        experience_url = "" # No experience level filter if none selected or invalid

    # Handle 'distance'
    distance_param: Optional[str] = parameters.get('distance')
    distance_url: str = f"?distance={distance_param}" if distance_param else "?distance=25" # Default or from params

    # Handle 'jobTypes'
    # Mapping: F: Full-time, C: Contract, P: Part-time, T: Temporary, I: Internship, V: Volunteer, O: Other
    job_type_params: Optional[Dict[str, bool]] = parameters.get('jobTypes')
    selected_job_types: List[str] = []
    if isinstance(job_type_params, dict):
        for job_type_key, is_selected in job_type_params.items():
            # Assuming job_type_key is like "Full-time", "Contract", etc.
            # and we need the first letter for the URL.
            if is_selected and job_type_key and len(job_type_key) > 0:
                 # Basic mapping, might need adjustment if keys are not single letters already
                if job_type_key.startswith("Full"): selected_job_types.append("F")
                elif job_type_key.startswith("Part"): selected_job_types.append("P")
                elif job_type_key.startswith("Contract"): selected_job_types.append("C")
                elif job_type_key.startswith("Temp"): selected_job_types.append("T")
                elif job_type_key.startswith("Intern"): selected_job_types.append("I")
                elif job_type_key.startswith("Volunteer"): selected_job_types.append("V")


    if selected_job_types:
        job_types_url += "%2C".join(selected_job_types)
    else:
        job_types_url = "" # No job type filter if none selected

    # Handle 'date' posted filter
    # f_TPR (Time Posted Range): r86400 (Past 24 hours), r604800 (Past Week), r2592000 (Past Month)
    dates_map: Dict[str, str] = {
        "all time": "", "month": "&f_TPR=r2592000", "week": "&f_TPR=r604800", "24 hours": "&f_TPR=r86400"
    }
    date_table_params: Optional[Dict[str, bool]] = parameters.get('date')
    if isinstance(date_table_params, dict):
        for key, is_selected in date_table_params.items():
            if is_selected and key in dates_map:
                date_url = dates_map[key]
                break # Typically only one date filter is active

    easy_apply_url: str = "" # Placeholder for Easy Apply if needed in future

    # Combine all URL components
    # Note: `distance_url` starts with '?' which is for the very first query param.
    # Other params should start with '&'. The logic below might need adjustment if distance_url isn't first.
    # For robustness, it's better to build a list of "key=value" strings and then `&`.join().

    query_params: List[str] = []
    if distance_url.startswith("?"): # Assuming distance is the primary part of query string
        base_query_part = distance_url[1:] # remove '?'
        if base_query_part : query_params.append(base_query_part)

    # Add other parameters, ensuring they are correctly formatted (e.g. "f_WT=2" not "&f_WT=2" initially)
    if remote_url.startswith("&"): remote_url = remote_url[1:]
    if lessthan_ten_applicants_url.startswith("&"): lessthan_ten_applicants_url = lessthan_ten_applicants_url[1:]
    if newest_postings_first_url.startswith("&"): newest_postings_first_url = newest_postings_first_url[1:]
    # job_types_url and experience_url already start with "f_JT=" or "f_E="
    if date_url.startswith("&"): date_url = date_url[1:]

    # Filter out empty strings before adding to query_params
    for term in [remote_url, lessthan_ten_applicants_url, newest_postings_first_url, job_types_url, experience_url, date_url, easy_apply_url]:
        if term and (not term.endswith("=")) : # Avoid adding "f_E=" if no levels were selected
             query_params.append(term)

    # Join all parameters with '&'
    # The initial '?' for the query string should be prepended by the caller if this function only returns the param string.
    # Or, this function can decide if it returns "?params" or just "params".
    # The original code's distance_url started with "?", implying it might be the first.
    # Let's ensure the output string starts correctly.

    final_query_string = "&".join(filter(None, query_params))

    # The original code had distance_url as the first element in extra_search_terms.
    # If distance_url was like "?distance=25", then the join would look like "?distance=25&param2&param3..."
    # If distance_url was empty or not starting with "?", the logic should adjust.
    # Given the original structure, let's try to mimic it:
    # extra_search_terms = [distance_url, remote_url, lessthanTenApplicants_url, newestPostingsFirst_url, job_types_url, experience_url]
    # extra_search_terms_str = '&'.join(term for term in extra_search_terms if len(term) > 0) + easy_apply_url + date_url
    # This implies that if distance_url is "?d=1", result is "?d=1&p2&p3". If distance_url is empty, result is "p2&p3".
    # This is a bit fragile. A more robust way is to manage the '?' and '&' explicitly.

    # Let's refine the return to be just the query part, without the initial '?'
    # The caller can add '?' or '&' as needed.
    # However, the original code structure seems to return something like "?distance=X&f_WT=Y..."
    # or "&f_WT=Y..." if distance is not the first one.
    # For now, adhering to the potential original intent of including '?' if distance is present:

    if parameters.get('distance'): # If distance is a primary parameter that starts the query
        return f"?{final_query_string}" if not final_query_string.startswith("?") else final_query_string
    else: # If distance is not there, the string should start with "&" if it's to be appended
        return f"&{final_query_string}" if final_query_string else ""
        # Or, more simply, just return final_query_string and let caller handle prefix.
        # Given the original code's use of `extra_search_terms_str = '&'.join(...) + date_url`,
        # it suggests the components themselves might already contain '&' or '?'
        # This is very complex to refactor perfectly without knowing all call sites.
        # Let's simplify and make it return a string that always needs '&' prepended by caller,
        # unless it's the very first set of params after '?'
        # For now, I'll return the string and assume the caller handles the initial '?' or '&'.
        # The original code's structure `extra_search_terms_str = '&'.join(...)` implies the terms
        # themselves should not have leading/trailing '&'.

        # Re-evaluating the original:
        # extra_search_terms = [distance_url, remote_url, lessthanTenApplicants_url, newestPostingsFirst_url, job_types_url, experience_url]
        # distance_url = "?distance=" + str(parameters['distance'])
        # remote_url = "&f_WT=2"
        # This means the first term might start with '?' and subsequent ones with '&'.
        # The '&'.join() would then produce something like "?distance=10&&f_WT=2&&f_EA=true" which is wrong.
        # The filter `if len(term) > 0` was good.
        # The terms should be "key=value" pairs essentially.

    # Corrected construction:
    final_params: List[str] = []
    if parameters.get('distance'):
        final_params.append(f"distance={parameters['distance']}") # No '?' yet

    if parameters.get('remote'):
        final_params.append("f_WT=2")

    if parameters.get('lessthanTenApplicants'):
        final_params.append("f_EA=true")

    if parameters.get('newestPostingsFirst'):
        final_params.append("sortBy=DD")

    # Rebuild experience_url correctly
    if selected_experience_levels: # This list now contains "1", "2", etc.
        final_params.append(f"f_E={','.join(selected_experience_levels)}") # LinkedIn uses simple comma, not %2C, for f_E list.

    # Rebuild job_types_url correctly
    if selected_job_types: # This list now contains "F", "P", etc.
        final_params.append(f"f_JT={','.join(selected_job_types)}") # LinkedIn uses simple comma for f_JT list.

    # Rebuild date_url
    # The original maps like "&f_TPR=r2592000". We only need the "f_TPR=..." part.
    if date_url and date_url.startswith("&"): # date_url was like "&f_TPR=r2592000"
        final_params.append(date_url[1:]) # Remove leading '&'

    # if easy_apply_url: # if it were implemented
    #     final_params.append("easyApply=true") # example

    return "&".join(final_params) # This is the query string itself. Caller adds '?'
