import os
from api4jenkins import Jenkins
import logging
import json
from time import time, sleep

log_level = os.environ.get('INPUT_LOG_LEVEL', 'INFO')
logging.basicConfig(format='JENKINS_ACTION:')
markdownSummaryTemplate = """## JaCoCo Test Coverage Summary
                            * __Coverage:__ 1234
                            * __Branches:__ 5678
                            """

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
            if result == 'SUCCESS':
                logging.info(f'Build successful 🎉')
                return
            elif result in ('FAILURE', 'ABORTED', 'UNSTABLE'):
                raise Exception(f'Build status returned \"{result}\". Build has failed ☹️.')
            add_workflow_job_summary(12,34)
    else:
        raise Exception(f"Build has not finished and timed out. Waited for {timeout} seconds.")

def add_workflow_job_summary(cov, branches) :
    """Adds a job summary.

    Keyword arguments:
    cov - Coverage percentage
    branches - Branches coverage percentage
    """
    if "GITHUB_STEP_SUMMARY" in os.environ :
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f :
            print("Hello World", file=f)
    else:
        logging.info(f'File Not Found Error: GITHUB_STEP_SUMMARY')
    return
if __name__ == "__main__":
    main()
