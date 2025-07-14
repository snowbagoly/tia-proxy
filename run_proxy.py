from mitmproxy import http
import json
import re
import os
import requests
from datetime import datetime

COMMANDER_SERVER_URL = os.getenv("COMMANDER_SERVER_URL", "http://localhost:5000")

LOG_FILE = "proxy_events.log"

API_ON_PREMISE_CALL_OPEN_TEST_RUNNER = '/_api/_wit/pageWorkItems?__v=5'
API_CALL_UPDATE_TEST_RUN_SUFFIX = '/_api/_testresult/Update?teamId=&__v=5'
API_SERVICES_CALL_OPEN_TEST_RUNNER = '/_apis/Contribution/dataProviders/query'

API_CALL_WORKITEM_SUFFIX_WIT = '/_apis/wit/workitems/'
API_CALL_WORKITEM_SUFFIX_VERSION = '?api-version=6.0'

AZURE_DEVOPS_URL_PATTERN = re.compile(r"^https://.*visualstudio\.com/|^https://dev\.azure\.com/")

def log_to_file(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} {message}\n")

def is_azure_devops_url(url: str) -> bool:
    return bool(AZURE_DEVOPS_URL_PATTERN.match(url))

def get_completed_date_of_action_result(action_result):
    date_string = action_result.get("dateCompleted", "")
    if "(" in date_string and ")" in date_string:
        timestamp = date_string.split("(")[1].split(")")[0]
        return int(timestamp)
    return 0  # fallback if format is wrong or missing

def is_substep_info(info):
    return bool(info.get("actionPath"))


def get_updated_iteration_action_result(update_request):
    result = None

    for action_result in update_request.get("actionResults", []):
        if is_substep_info(action_result):
            continue

        if (result is None or
            get_completed_date_of_action_result(result) < get_completed_date_of_action_result(action_result)):
            result = action_result

    return result

def test_outcome_to_teamscale_test_execution_result(outcome):
    match outcome:
        case 2:
            return "PASSED"
        case 3:
            return "FAILURE"
        case 7:
            return "SKIPPED"
        case 11 | 12:
            return "ERROR"
        case _:
            return "ERROR"
        
def parse_body(flow):
    raw_body = flow.request.raw_content
    body_json = json.loads(raw_body.decode("utf-8"))
    return body_json
        
        
def test_run_update_call_listener(flow, url):
    try:
        update_request = json.loads(parse_body(flow)["updateRequests"])[0]
    except Exception as e:
        log_error_message("Failed to parse update request: " + str(e))
        return

    test_case_id = update_request["testCaseResult"]["testCaseId"]
    updated_result = get_updated_iteration_action_result(update_request)

    test_name = update_request["testCaseResult"]["testCaseTitle"].strip()

    action = "update"
    if updated_result.get("outcome") == 12:
        action = "stop"
        log_warning_message(
            "Pausing a test case is currently not supported. Coverage recorded until the 'pause' event will be processed, subsequent coverage will be lost."
        )

    result_status = test_outcome_to_teamscale_test_execution_result(updated_result.get("outcome"))
    send_profiler_request(action, str(test_case_id) + " - " + test_name, result_status)

def test_run_start_listener(flow, url, service, work_item_id):
    urlToFetchTitle = url.replace(service, API_CALL_WORKITEM_SUFFIX_WIT + work_item_id + API_CALL_WORKITEM_SUFFIX_VERSION)
    title = request_work_item_title(flow, urlToFetchTitle)
    if title:
        send_profiler_request("start", str(work_item_id) + " - " + title, None)

def request_work_item_title(flow, url_to_fetch_title):
    try:
        headers = {
            "Authorization": flow.request.headers.get("Authorization", ""),
            "Cookie": flow.request.headers.get("Cookie", ""),
            "Content-Type": "application/json"
        }
        response = requests.get(url_to_fetch_title, headers=headers, verify=False)
        if response.status_code >= 200 and response.status_code < 300:
            data = response.json()
            work_item_title = data['fields'].get('System.Title', 'Unknown Title')

            return work_item_title
        else:
            log_error_message(f"Failed to fetch title: {response.status_code} {response.reason}")
            return None

    except requests.RequestException as e:
        log_error_message("Failed to fetch title: " + str(e))
        return None

def assert_string_ends_with(value, suffix):
    return value if value.endswith(suffix) else value + suffix

def send_profiler_request(action, test_id_and_title, status):

    profiler_url = assert_string_ends_with(COMMANDER_SERVER_URL, "/")
    service_url = profiler_url + "test/"

    if action == "stop" or action == "update":
        url = f"{service_url}stop/{status}"
    else:
        url = f"{service_url}{action}/{test_id_and_title}"

    
    log_to_file("[INFO] Sending request " + str(action) + " " + str(test_id_and_title) + " " + str(status) + " to " + url)

    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(url, headers=headers, verify=False)
    log_to_file(f"[INFO] Response from profiler: {response.status_code} {response.text}")

def log_error_message(msg):
    log_to_file("[ERROR] " + msg)

def log_warning_message(msg):
    log_to_file("[WARNING] " + msg)

def request(flow: http.HTTPFlow) -> None:
    url = flow.request.pretty_url
    if not is_azure_devops_url(url):
        return

    try:
        if url.endswith(API_SERVICES_CALL_OPEN_TEST_RUNNER):
            request_body = parse_body(flow)
            if "context" not in request_body or "properties" not in request_body["context"] or "workItemIds" not in request_body["context"]["properties"]:
                return
            work_item_id = request_body["context"]["properties"]["workItemIds"]
            test_run_start_listener(flow, url, API_SERVICES_CALL_OPEN_TEST_RUNNER, work_item_id)
        if url.endswith(API_ON_PREMISE_CALL_OPEN_TEST_RUNNER):
            request_body = parse_body(flow)
            if "workItemIds" not in request_body:
                return
            work_item_id = request_body["workItemIds"]
            test_run_start_listener(flow, url, API_ON_PREMISE_CALL_OPEN_TEST_RUNNER, work_item_id)
        if url.endswith(API_CALL_UPDATE_TEST_RUN_SUFFIX):
            test_run_update_call_listener(flow, url)
    except Exception as e:
            log_error_message("Something went wrong: " + str(e))