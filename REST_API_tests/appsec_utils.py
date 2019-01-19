import logging
import requests

loggerClient = logging.getLogger('Client')

def logAssert(test,msg):
    __tracebackhide__ = True
    if not test:
        loggerClient.error(msg)
        assert test,msg

def assertStatusCode(result, status_code=requests.codes.ok ):
    logAssert(result.status_code == status_code,
              "Unexpected result. Status code: %s" % result.status_code)