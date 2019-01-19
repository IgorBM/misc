import logging

LOG_FILE_NAME = 'appsec_tests.log'

logging.basicConfig(filename=LOG_FILE_NAME,
                    filemode='w',
                    format='%(asctime)s.%(msecs)03d %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.DEBUG)

def pytest_configure(config):
    print("configure test session")