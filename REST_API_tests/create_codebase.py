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

url = "http://somehub.com"
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

def test_new_codebase():
    loggerClient.info("Starting %s" % test_new_codebase.__name__)
    global client

    loggerClient.info('STEP 1. Authentication...')
    res, cook = client.auth_at_appsec("auth/login")
    assertStatusCode(res)
    loggerClient.info('Obtained Cookie: %s' % cook)

    loggerClient.info('STEP 2. Get App 50 data...')
    app50 = client.send_get("application/50")
    assertStatusCode(app50)
    loggerClient.info('Get Results : %s' % app50.text)
    app50_data = json.loads(app50.text)

    loggerClient.info('STEP 3. Get App 50 codebase list...')
    codebase_list = client.send_get('application/50/codebase')
    assertStatusCode(codebase_list)
    loggerClient.info('Get Results : %s' % codebase_list.text)
    codebase_list_data = json.loads(codebase_list.text)

    # Creating unique name for codebase and it's link
    uuid = uuid1()
    loggerClient.info("STEP 4. Creating a new codebase %s for App 50..." % uuid)
    new_codebase_data = {"appId":"50",
                         "name":"Codebase %s" % uuid,
                         "link":"git@gitlab:/repos/test%s.git" % uuid,
                         "project":"","repo":"",
                         "branch":"master",
                         "vcsType":"git",
                         "checkoutRelativePath":"./",
                         "buildTool":"maven",
                         "active": "true"}
    new_codebase = client.send_post('codebase', new_codebase_data)
    loggerClient.info('Get Results : %s' % new_codebase.text)
    new_codebase_data = json.loads(new_codebase.text)
    print (new_codebase_data)

    loggerClient.info('STEP 5. Get App 50 codebase list again...')
    codebase_list = client.send_get('application/50/codebase' )
    assertStatusCode(codebase_list)
    loggerClient.info('Get Results : %s' % codebase_list.text)
    codebase_list_data = json.loads(codebase_list.text)

    loggerClient.info("Verifying if list of codebases contains newly added one:")
    codebase_from_list = next((item for item in codebase_list_data if item["id"] == new_codebase_data['id']), None)
    logAssert(codebase_from_list , "Newly added codebase was not found in the returned data of GET 'application/50/codebase'")

    loggerClient.info('STEP 6. Update the data of newly added codebase...')
    # Creating unique description for the bug
    new_uuid = uuid1()
    updated_codebase_data = {"appId": "50",
                         "name": "Codebase %s" % new_uuid,
                         "link": "git@gitlab:/repos/test%s.git" % uuid,
                         "project": "", "repo": "",
                         "branch": "master",
                         "vcsType": "git",
                         "checkoutRelativePath": "./",
                         "buildTool": "maven",
                         "active": "true"}
    codebase_list = client.send_put("codebase/%s" % new_codebase_data['id'], updated_codebase_data)
    #assertStatusCode(codebase_list)
    loggerClient.info('Get Results : %s %s' % (codebase_list.status_code,codebase_list.text))

    loggerClient.info('STEP 7. Get App 50 codebase list again...')
    codebase_list = client.send_get('application/50/codebase')
    assertStatusCode(codebase_list)
    loggerClient.info('Get Results : %s' % codebase_list.text)
    codebase_list_data = json.loads(codebase_list.text)

    loggerClient.info("Verifying if list of codebases contains newly added one:")
    codebase_from_list = next((item for item in codebase_list_data if item["id"] == new_codebase_data['id']), None)
    logAssert(codebase_from_list , "Newly added codebase was not found in the returned data of GET 'application/50/codebase'")
    logAssert(codebase_from_list['name'] == "Codebase %s" % new_uuid,
              "PUT command has not updated the 'name' field of the newly added codebase")


    loggerClient.info('STEP 8. Logout...')
    res = client.logout_at_appsec('auth/logout')
    assertStatusCode(res)

    loggerClient.info('STEP 9. Trying to Get all apps while logged out...')
    app_list = client.send_get("application")
    assertStatusCode(app_list, requests.codes.unauthorized)
    loggerClient.info('Get Results : %s' % app_list.text)

def test_3():
    loggerClient.info("Starting %s" % test_3.__name__)
