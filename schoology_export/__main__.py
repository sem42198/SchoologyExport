import argparse
import base64
import os
import re
import time
from typing import List, Tuple, Set

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


def _get_assignments(key: str, secret: str) -> Set[Tuple[str, str]]:
    sc = schoolopy.Schoology(schoolopy.Auth(key, secret))
    me = sc.get_me()
    assignments = set()
    for section in sc.get_sections(me.uid):
        for assignment in sc.get_assignments(section.id):
            assignments.add((assignment.id, assignment.title))
    return assignments


def _add_all_questions_to_assessment(driver: webdriver.Chrome, assignment_id: str) -> None:
    driver.get(f"https://app.schoology.com/assignment/{assignment_id}/assessment_questions")
    question_sets = driver.find_elements(by=By.CLASS_NAME, value="component-summary-wrapper")
    question_set_count = len(question_sets)
    print(f"Found {len(question_sets)} question sets")
    for i in range(question_set_count):
        question_set = question_sets[i]
        num_questions = question_set.find_element(by=By.CLASS_NAME, value="component-num-questions")
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
            time.sleep(2)


def _no_randomize_order(driver: webdriver.Chrome, assignment_id: str):
    driver.get(f"https://app.schoology.com/assignment/{assignment_id}/assessment_settings")
    randomize_order = driver.find_element(value="edit-randomize-order")
    attempts = driver.find_element(value="edit-attempts")
    student_view = driver.find_element(value="edit-student-view")
    order_select = Select(randomize_order)
    attempts_select = Select(attempts)
    student_view_select = Select(student_view)
    if (order_select.first_selected_option.get_attribute("value") != "0" or
            attempts_select.first_selected_option.get_attribute("value") != "0" or
            student_view_select.first_selected_option.get_attribute("value") != "3"):
        attempts_select.select_by_value("0")
        student_view_select.select_by_value("3")
        order_select.select_by_value("1")
        order_select.select_by_value("0")
        print("Saving assessment settings")
        webdriver.ActionChains(driver).send_keys(webdriver.Keys.TAB).send_keys(webdriver.Keys.TAB) \
            .send_keys(webdriver.Keys.TAB).send_keys(webdriver.Keys.TAB).send_keys(webdriver.Keys.TAB) \
            .send_keys(webdriver.Keys.TAB).send_keys(webdriver.Keys.TAB).send_keys(webdriver.Keys.ENTER).perform()
        time.sleep(2)


def _save_questions(driver: webdriver.Chrome, questions: List[str], location: str):
    os.makedirs(location, exist_ok=True)
    for i, question in enumerate(questions, start=10):
        driver.get(question)
        frame = driver.find_element(value="edit-title_ifr")
        frame.click()
        content_body = frame.find_element(value="tinymce")
        with open(os.path.join(location, f"question_{i}.html"), "w") as f:
            f.write(driver.page_source)
        # data = base64.b64decode(driver.print_page())
        # with open(os.path.join(location, f"question_{i}.pdf"), "wb") as f:
        #     f.write(data)


def _login(driver: webdriver.Chrome, email: str, password: str):
    driver.implicitly_wait(1)
    driver.get("https://app.schoology.com/login")
    email_box = driver.find_element(value="edit-mail")
    email_box.send_keys(email)
    password_box = driver.find_element(value="edit-pass")
    password_box.send_keys(password)
    button = driver.find_element(value="edit-submit")
    button.click()


def _download_assignment(driver: webdriver.Chrome, assignment_id: str, assignment_name: str, output_dir: str):
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
    file = os.path.join(output_dir, f"{assignment_name}-{assignment_id}.pdf")
    with open(file, "wb") as f:
        f.write(contents)


def main(key: str, secret: str, email: str, password: str, output_dir: str, student_email: str, student_password: str):
    assignments = _get_assignments(key, secret)
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    teacher_driver = webdriver.Chrome(options=options)
    _login(teacher_driver, email, password)
    print(f"Found {len(assignments)} assignments")
    i = 1
    for assignment, assignment_name in assignments:
        print(f"Finding questions for assignment {assignment_name}: {i} of {len(assignments)}")
        i += 1
        _add_all_questions_to_assessment(teacher_driver, assignment)
        _no_randomize_order(teacher_driver, assignment)
    teacher_driver.close()

    student_driver = webdriver.Chrome(options)
    _login(student_driver, student_email, student_password)
    os.makedirs(output_dir, exist_ok=True)
    i = 1
    for assignment, assignment_name in assignments:
        print(f"Saving questions for assignment {assignment_name}: {i} of {len(assignments)}")
        i += 1
        _download_assignment(student_driver, assignment, assignment_name, output_dir)


if __name__ == '__main__':
    args = _parse_args()
    main(args.key, args.secret, args.email, args.password, args.output_dir, args.student_email,
         args.student_password)
