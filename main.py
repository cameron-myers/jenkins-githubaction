import os
from api4jenkins import Jenkins
import logging
import json
import requests
from time import time, sleep

log_level = os.environ.get('INPUT_LOG_LEVEL', 'INFO')
logging.basicConfig(format='JENKINS_ACTION:')
gh_token = os.environ["GH_TOKEN"]
commit_sha = os.environ.get("GITHUB_SHA")

def comment_on_commit(commit_sha, comment_body):
    url = f"https://api.github.com/repos/cameron-myers/MayhemEngine/commits/{commit_sha}/comments"
    headers = {
        "authorization": f"Bearer {gh_token}",
        "accept": "application/vnd.github-commitcomment.raw+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    data = {
        "body": comment_body,
    }

    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 201:
        print("Comment added successfully!")
    else:
        print(f"Error adding comment: {response.status_code} - {response.text}")

# Example usage


def print_test_case_to_file(case, f):
    
    if(case.status == 'SUCCESS' or 'PASSED'):
        print(case.name + ": PASSED\n",file = f)
    elif(case.status == 'FAILED' or 'REGRESSION'):
        print(case.name + ": FAILED\n" ,file = f)
        print("ERROR: " + case.error_details + "\n",file = f)

    return

def has_class(case, sections):
    for className in sections:
        if className == case.class_name:
            return True
        
    return False

def get_failed_sections(suite):
    sections = []
    #get a list of failed classes
    for case in suite:
        if not has_class(case, sections):
            sections.append(case.class_name)
    return sections

def get_failed_tests(section, suite):
    tests = ["\0"]
    for case in suite:
        if case.class_name == section:
            tests.append(case.name)

    return tests

def add_workflow_job_summary(test_results):
    
    #Format
    #Summary:Total Tests, Passes, Fails, RunTime
    #Section passed just show that
    #Section fails show section and list tests that failed
    comment_body = "\0"
    suite = test_results.get('MSTestSuite')  # same as `for suite in tr.suites`

    runtime = '0'
    #test_results.duration
    tests_passed = test_results.fail_count
    tests_failed = test_results.pass_count
    total_tests = int(tests_passed) + int(tests_failed)

    
    comment_body = "Total Tests: {total_tests}\n :white_check_mark: Passed:{tests_passed} \n :x: Failed: {tests_failed} \n Runtime: {runtime}"

    if(tests_failed > 0):
        failed_sections = get_failed_sections(suite)
        for section in failed_sections:
            comment_body += "\n FAILED SECTIONS: \n{section}"
            for test in get_failed_tests(section, suite):
                comment_body += "\n :x:{test}"
    
    comment_on_commit(commit_sha, comment_body)
    
    if "GITHUB_STEP_SUMMARY" in os.environ:
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            print(comment_body, f)
    else:
        logging.error(f'File Not Found Error: GITHUB_STEP_SUMMARY')
    return


def main():
    # Required
    url = os.environ["INPUT_URL"]
    job_name = os.environ["INPUT_JOB_NAME"]
    # Optional
    username = os.environ.get("INPUT_USERNAME")
    api_token = os.environ.get("INPUT_API_TOKEN")
    parameters = os.environ.get("INPUT_PARAMETERS")
    cookies = os.environ.get("INPUT_COOKIES")
    wait = bool(os.environ.get("INPUT_WAIT"))
    timeout = int(os.environ.get("INPUT_TIMEOUT"))
    start_timeout = int(os.environ.get("INPUT_START_TIMEOUT"))
    interval = int(os.environ.get("INPUT_INTERVAL"))

    if username and api_token:
        auth = (username, api_token)
    else:
        auth = None
        logging.info('Username or token not provided. Connecting without authentication.')

    if parameters:
        try:
            parameters = json.loads(parameters)
        except json.JSONDecodeError as e:
            raise Exception('`parameters` is not valid JSON.') from e
    else:
        parameters = {}

    if cookies:
        try:
            cookies = json.loads(cookies)
        except json.JSONDecodeError as e:
            raise Exception('`cookies` is not valid JSON.') from e
    else:
        cookies = {}

    jenkins = Jenkins(url, auth=auth, cookies=cookies)

    try:
        jenkins.version
    except Exception as e:
        raise Exception('Could not connect to Jenkins.') from e

    logging.info('Successfully connected to Jenkins.')

    queue_item = jenkins.build_job(job_name, **parameters)

    logging.info('Requested to build job.')

    t0 = time()
    sleep(interval)
    while time() - t0 < start_timeout:
        build = queue_item.get_build()
        if build:
            break
        logging.info(f'Build not started yet. Waiting {interval} seconds.')
        sleep(interval)
    else:
        raise Exception(f"Could not obtain build and timed out. Waited for {start_timeout} seconds.")

    build_url = build.url
    logging.info(f"Build URL: {build_url}")
    print(f"::set-output name=build_url::{build_url}")
    print(f"::notice title=build_url::{build_url}")
    
    if not wait:
        logging.info("Not waiting for build to finish.")
        return

    t0 = time()
    sleep(interval)
    while time() - t0 < timeout:
        if build.building:
            logging.info(f'Build not finished yet. Waiting {interval} seconds. {build_url}')
            sleep(interval)
        else:
            result = build.result
            test_results = build.get_test_report()
            add_workflow_job_summary(test_results)
            if result == 'SUCCESS':
                logging.info(f'Build successful 🎉')
                return
            elif result in ('FAILURE', 'ABORTED', 'UNSTABLE'):
                raise Exception(f'Build status returned \"{result}\". Build has failed ☹️.')
            
    else:
        raise Exception(f"Build has not finished and timed out. Waited for {timeout} seconds.")

if __name__ == "__main__":
    main()


