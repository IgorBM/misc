import logging,logging.handlers
import pytest
from appsec_api import *
import json
import requests
from appsec_utils import *
from uuid import uuid1

#logging.basicConfig(filename='tests.log',
#                    filemode='w',
#                    format='%(asctime)s.%(msecs)03d %(name)s %(levelname)s %(message)s',
#                    datefmt='%H:%M:%S',
#                    level=logging.DEBUG)

loggerClient = logging.getLogger('Client')

url = "http://hub.dev.swordfishsecurity.com"
login = "q"
passwd = "q"
client = None

def setup_module(module):
    loggerClient.info('Setting up test module %s' % module.__name__)
    global client
    client = APIClient(url)
    client.user = login
    client.password = passwd

def teardown_module(module):
    loggerClient.info('Tear Down test module %s' % module.__name__)

def test_submit_bug():
    loggerClient.info("Starting %s" % test_submit_bug.__name__)
    global client

    loggerClient.info('STEP 1. Authentication...')
    res, cook = client.auth_at_appsec("auth/login")
    assertStatusCode(res)
    loggerClient.info('Obtained Cookie: %s' % cook)

    loggerClient.info('STEP 2. Get App 50 data...')
    app50_res = client.send_get("application/50")
    assertStatusCode(app50_res)
    loggerClient.info('Get Results : %s' % app50_res.text)
    app50_data = json.loads(app50_res.text)

    # Creating unique description for the bug
    uuid = uuid1()
    loggerClient.info("STEP 3. Going to submite a bug: %s" % uuid)
    bug_data = {"priority":{"rank":1,"name":"Critical"},
                "severity":{"rank":1,"name":"Medium"},
                "source":"Manual",
                "tool":"none",
                "type":"Software",
                "stage":"FT",
                "summary":"Test Summary",
                "description":"BUG Description %s" % uuid}
    bug_res = client.send_post("bug", bug_data)
    assertStatusCode(bug_res)
    loggerClient.info('Get Results : %s' %  bug_res.text)
    new_bug_data = json.loads(bug_res.text)
    new_bug_id = bug_res['id']

    loggerClient.info('STEP 4. Obtained all a50 bugs:')
    app50_bugs = client.send_get("bug?application=50")
    assertStatusCode(app50_bugs)
    loggerClient.info('Get Results : %s' % app50_bugs.text)
    # TODO assert here the the list of all bugs includes our new bug with it's new_bug_id
    # and it's description contains UUID

    loggerClient.info('STEP 5. Obtained a new bug:')
    new_bug = client.send_get("bug/%s" % new_bug_id)
    assertStatusCode(new_bug)
    loggerClient.info('Get Results : %s' % new_bug.text)

    # Creating unique description for the bug
    new_uuid = uuid1()
    loggerClient.info("STEP 5. Change the bug description with the new UUID: %s" % new_uuid)
    bug_data = {"priority": {"rank": 1, "name": "Critical"},
                "severity": {"rank": 1, "name": "Medium"},
                "source": "Manual",
                "tool": "none",
                "type": "Software",
                "stage": "FT",
                "summary": "Test Summary",
                "description": "BUG Description %s" % new_uuid}
    updated_bug = client.send_put("bug/1", bug_data)
    assertStatusCode(updated_bug)
    loggerClient.info('Get Results : %s' % updated_bug.text)
    logAssert(updated_bug['description'] == "BUG Description %s" % new_uuid, "The bug was not updated" )

    loggerClient.info('STEP 7. Logout...')
    res = client.logout_at_appsec('auth/logout')
    assertStatusCode(res)

    loggerClient.info('STEP 8. Trying to Get all apps while logged out...')
    app_list = client.send_get("application")
    assertStatusCode(app_list, requests.codes.unauthorized)
    loggerClient.info('Get Results : %s' % app_list.text)


def test_2():
    loggerClient.info("Starting %s" % test_2.__name__)

