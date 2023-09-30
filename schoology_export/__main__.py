import argparse
import base64
import os
from typing import List, Tuple

import schoolopy
from selenium import webdriver
from selenium.webdriver.common.by import By


def _parse_args():
    parser = argparse.ArgumentParser("Pull user's data from schoology")
    parser.add_argument("-k", "--key", required=True, type=str, help="Schoology consumer key - can be obtained at "
                                                                     "https://app.schoology.com/api/v1")
    parser.add_argument("-s", "--secret", required=True, type=str, help="Schoology consumer secret - can be obtained "
                                                                        "at https://app.schoology.com/api/v1")
    parser.add_argument("-e", "--email", required=True, type=str, help="Email to login to schoology")
    parser.add_argument("-p", "--password", required=True, type=str, help="Password to login to schoology")
    parser.add_argument("-o", "--output-dir", default="out", type=str, help="Directory to save output files to")
    return parser.parse_args()


def _get_assignments(key: str, secret: str) -> List[Tuple[str, str]]:
    sc = schoolopy.Schoology(schoolopy.Auth(key, secret))
    me = sc.get_me()
    assignments = []
    for section in sc.get_sections(me.uid):
        for assignment in sc.get_assignments(section.id):
            assignments.append((assignment.id, assignment.title))
    return assignments


def _get_questions(driver: webdriver.Chrome, assignment_id: str) -> List[List[str]]:
    driver.get(f"https://app.schoology.com/assignment/{assignment_id}/assessment_questions")
    question_sets = driver.find_elements(by=By.CLASS_NAME, value="component-main-cell")
    print(f"Found {len(question_sets)} question sets")
    assessment_questions = []
    for question_set in question_sets:
        expander = question_set.find_element(by=By.CLASS_NAME, value="random-qset-expander")
        expander.click()
        question_rows = question_set.find_elements(by=By.CLASS_NAME, value="random-qset-questions-list-row")
        assert len(question_rows) != 0
        set_questions = []
        for question_row in question_rows:
            menu_button = question_row.find_element(by=By.CLASS_NAME, value="action-links-unfold-text")
            menu_button.click()
            edit_button = question_row.find_element(by=By.CLASS_NAME, value="action-edit-child")
            set_questions.append(edit_button.get_attribute("href"))
            menu_button.click()
        assessment_questions.append(set_questions)

    return assessment_questions


def _save_questions(driver: webdriver.Chrome, questions: List[str], location: str):
    os.makedirs(location, exist_ok=True)
    for i, question in enumerate(questions, start=1):
        driver.get(question)
        data = base64.b64decode(driver.print_page())
        with open(os.path.join(location, f"question_{i}.pdf"), "wb") as f:
            f.write(data)


def main(key: str, secret: str, email: str, password: str, output_dir: str):
    assignments = _get_assignments(key, secret)
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(1)
    driver.get("https://app.schoology.com/login")
    email_box = driver.find_element(value="edit-mail")
    email_box.send_keys(email)
    password_box = driver.find_element(value="edit-pass")
    password_box.send_keys(password)
    button = driver.find_element(value="edit-submit")
    button.click()
    questions = {}
    for assignment, assignment_name in assignments:
        print(f"Finding questions for assignment {assignment_name}")
        question_sets = _get_questions(driver, assignment)
        total_questions = sum([len(question_set) for question_set in question_sets])
        print(f"Found {total_questions} questions for assignment {assignment_name}")
        questions[f"{assignment_name} - {assignment}"] = question_sets

    for assignment_name, question_sets in questions.items():
        print(f"Downloading questions for {assignment_name}")
        for i, question_set in enumerate(question_sets, start=1):
            _save_questions(driver, question_set, os.path.join(output_dir, assignment_name, f"question_set_{i}"))

    print(assignments)


if __name__ == '__main__':
    args = _parse_args()
    main(args.key, args.secret, args.email, args.password, args.output_dir)
