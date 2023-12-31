import argparse
import base64
import os
import re
import time
from typing import Tuple, List

import schoolopy
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select


def _parse_args():
    parser = argparse.ArgumentParser("Pull user's data from schoology")
    parser.add_argument("-k", "--key", required=True, type=str, help="Schoology consumer key - can be obtained at "
                                                                     "https://app.schoology.com/api/v1")
    parser.add_argument("-s", "--secret", required=True, type=str, help="Schoology consumer secret - can be obtained "
                                                                        "at https://app.schoology.com/api/v1")
    parser.add_argument("-e", "--email", required=True, type=str, help="Email to login to schoology")
    parser.add_argument("-p", "--password", required=True, type=str, help="Password to login to schoology")
    parser.add_argument("-o", "--output-dir", default="out", type=str, help="Directory to save output files to")
    parser.add_argument("-se", "--student-email", required=True, type=str, help="Email to login to schoology as a "
                                                                                "student")
    parser.add_argument("-sp", "--student-password", required=True, type=str, help="Password to login to schoology as "
                                                                                   "a student")
    return parser.parse_args()


def _get_assignments(key: str, secret: str) -> List[Tuple[str, str]]:
    sc = schoolopy.Schoology(schoolopy.Auth(key, secret))
    sc.limit = 500
    me = sc.get_me()
    assignments = []
    for section in sc.get_sections(me.uid):
        for assignment in sc.get_assignments(section.id):
            assignments.append((assignment.id, assignment.title))
    return assignments


def _add_all_questions_to_assessment(driver: webdriver.Chrome, assignment_id: str) -> None:
    driver.get(f"https://app.schoology.com/assignment/{assignment_id}/assessment_questions")
    question_sets = driver.find_elements(by=By.CLASS_NAME, value="component-summary-wrapper")
    question_set_count = len(question_sets)
    print(f"Found {len(question_sets)} question sets")
    for i in range(question_set_count):
        question_set = question_sets[i]
        try:
            num_questions = question_set.find_element(by=By.CLASS_NAME, value="component-num-questions")
        except:
            continue
        match = re.match(r"(\d+) of (\d+) questions?", num_questions.text)
        if match.group(1) != match.group(2):
            menu_button = question_set.find_element(by=By.CLASS_NAME, value="action-links-unfold-text")
            menu_button.click()
            edit_button = question_set.find_element(by=By.CLASS_NAME, value="component-action-edit")
            edit_button.click()
            question_bank_size = driver.find_element(by=By.CLASS_NAME, value="question-bank-size")
            total_questions = question_bank_size.text.lstrip("/")
            num_questions_input = driver.find_element(value="edit-banks-ncid-num-questions")
            num_questions_input.clear()
            num_questions_input.send_keys(total_questions)
            print("Adding all questions to assessment")
            webdriver.ActionChains(driver).send_keys(webdriver.Keys.TAB).send_keys(webdriver.Keys.TAB)\
                .send_keys(webdriver.Keys.ENTER).perform()
            driver.get(f"https://app.schoology.com/assignment/{assignment_id}/assessment_questions")
            question_sets = driver.find_elements(by=By.CLASS_NAME, value="component-summary-wrapper")
            time.sleep(5)


def _no_randomize_order(driver: webdriver.Chrome, assignment_id: str):
    driver.get(f"https://app.schoology.com/assignment/{assignment_id}/assessment_settings")
    randomize_order = driver.find_element(value="edit-randomize-order")
    attempts = driver.find_element(value="edit-attempts")
    student_view = driver.find_element(value="edit-student-view")
    paging = driver.find_element(value="edit-paging")
    availability = driver.find_element(value="edit-availability")
    order_select = Select(randomize_order)
    attempts_select = Select(attempts)
    student_view_select = Select(student_view)
    paging_select = Select(paging)
    availability_select = Select(availability)
    if (order_select.first_selected_option.get_attribute("value") != "0" or
            attempts_select.first_selected_option.get_attribute("value") != "0" or
            student_view_select.first_selected_option.get_attribute("value") != "3" or
            paging_select.first_selected_option.get_attribute("value") != "1" or
            availability_select.first_selected_option.get_attribute("value") != "1"):
        attempts_select.select_by_value("0")
        student_view_select.select_by_value("3")
        paging_select.select_by_value("1")
        availability_select.select_by_value("1")
        order_select.select_by_value("1")
        order_select.select_by_value("0")
        print("Saving assessment settings")
        webdriver.ActionChains(driver).send_keys(webdriver.Keys.TAB).send_keys(webdriver.Keys.TAB) \
            .send_keys(webdriver.Keys.TAB).send_keys(webdriver.Keys.TAB).send_keys(webdriver.Keys.TAB) \
            .send_keys(webdriver.Keys.TAB).send_keys(webdriver.Keys.TAB).send_keys(webdriver.Keys.ENTER).perform()
        time.sleep(5)


def _login(driver: webdriver.Chrome, email: str, password: str):
    driver.implicitly_wait(1)
    driver.get("https://app.schoology.com/login")
    email_box = driver.find_element(value="edit-mail")
    email_box.send_keys(email)
    password_box = driver.find_element(value="edit-pass")
    password_box.send_keys(password)
    button = driver.find_element(value="edit-submit")
    button.click()


def _download_assignment(driver: webdriver.Chrome, assignment_id: str, file: str):
    driver.get(f"https://app.schoology.com/assignment/{assignment_id}/assessment")
    try:
        start_test_button = driver.find_element(value="begin-test-quiz")
    except:
        start_test_button = driver.find_element(value="edit-submit-1")
    start_test_button.click()
    review_test_button = driver.find_element(value="edit-submit")
    review_test_button.click()
    submit_test_button = driver.find_element(value="edit-submit")
    submit_test_button.click()
    confirm_button = driver.find_element(value="popup_confirm")
    confirm_button.click()
    contents = base64.b64decode(driver.print_page())
    print("Downloading file")
    with open(file, "wb") as f:
        f.write(contents)


def main(key: str, secret: str, email: str, password: str, output_dir: str, student_email: str, student_password: str):
    assignments = _get_assignments(key, secret)
    print(f"Found {len(assignments)} assignments")
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    teacher_driver = webdriver.Chrome(options=options)
    _login(teacher_driver, email, password)
    student_driver = webdriver.Chrome(options)
    _login(student_driver, student_email, student_password)
    os.makedirs(output_dir, exist_ok=True)

    i = 0
    for assignment, assignment_name in assignments:
        i += 1
        file = os.path.join(output_dir, f"{assignment_name}-{assignment}.pdf")
        if os.path.isfile(file):
            print(f"File {file} exists. Skipping")
            continue
        print(f"Finding questions for assignment {assignment_name}: {i} of {len(assignments)}")
        _add_all_questions_to_assessment(teacher_driver, assignment)
        _no_randomize_order(teacher_driver, assignment)
        print(f"Saving questions for assignment {assignment_name}: {i} of {len(assignments)}")
        _download_assignment(student_driver, assignment, file)


if __name__ == '__main__':
    args = _parse_args()
    main(args.key, args.secret, args.email, args.password, args.output_dir, args.student_email,
         args.student_password)
