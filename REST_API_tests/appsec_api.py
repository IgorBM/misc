#
# AppSec API binding for Python 3.x
#

import json, base64
from requests import Request, Session


class APIClient:
    def __init__(self, base_url, cookie_file=None):
        self.user = ''
        self.password = ''
        self.session = ''
        if not base_url.endswith('/'):
            base_url += '/'
        self.__url = base_url + 'hub/rest/'

    def auth_at_appsec(self,uri):
        url = self.__url + uri
        data = {'username': self.user, 'password': self.password}
        s = Session()
        s.headers.update({'Content-Type': 'application/x-www-form-urlencoded'})
        resp = s.post(url,data=data)
        self.session = s
        print (resp.text)
        return resp, s.cookies

    def logout_at_appsec(self,uri):
        url = self.__url + uri
        data = {'username': self.user, 'password': self.password}
        self.session.headers['Content-Type']='application/x-www-form-urlencoded'
        resp = self.session.post(url,data=data)
        print (resp.text)
        return resp

    #
    # Send Get
    #
    # Issues a GET request (read) against the API and returns the result
    # (as Python dict).
    #
    # Arguments:
    #
    # uri                 The API method to call including parameters
    #                     (e.g. application/1)
    #
    def send_get(self, uri):
        url = self.__url + uri
        return self.session.get(url)
    #
    # Send POST
    #
    # Issues a POST request (write) against the API and returns the result
    # (as Python dict).
    #
    # Arguments:
    #
    # uri                 The API method to call including parameters
    #                     (e.g. "bug")
    # data                The data to submit as part of the request (as
    #                     Python dict, strings must be UTF-8 encoded)
    #
    def send_post(self, uri, data):
        url = self.__url + uri
        self.session.headers['Content-Type']='application/json'
        return self.session.post(url, data=bytes(json.dumps(data), 'utf-8'))


    def send_put(self, uri, data):
        url = self.__url + uri
        self.session.headers['Content-Type'] = 'application/json'
        return self.session.put(url, data=bytes(json.dumps(data), 'utf-8'))


class APIError(Exception):
    pass
