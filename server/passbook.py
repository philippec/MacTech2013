#!/usr/bin/env python
#
# Copyright 2013 Philippe Casgrain
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from google.appengine.ext import db
# from google.appengine.dist import use_library
# use_library('django', '1.2')
from django.utils import simplejson as json
import urbanairship
import os
import datetime
from urlparse import urlparse
import logging
from PrivateInfo import *

class RegisteredDevice(db.Model):
    deviceLibraryIdentifier = db.StringProperty()
    passTypeIdentifier = db.StringProperty()
    serialNumber = db.StringProperty()
    pushToken = db.StringProperty()
    date = db.DateTimeProperty(auto_now_add=True)

class LogHandler(webapp.RequestHandler):
    def get(self):
        logging.info("log get:" + self.request.url)
        self.response.out.write("hello")
    def post(self):
        args = json.loads(self.request.body)
        logs = args['logs']
        logging.info("Logs: " + str(logs))


def get_pass_path_for_user():
    path = os.path.join(os.path.dirname(__file__), 'mactech.pkpass')
    return path

def get_pass_data_for_user():
    result = open(get_pass_path_for_user()).read()
    return result

def get_pass_last_modified_for_user():
    t = os.path.getmtime(get_pass_path_for_user())
    return str(t)

class DeviceHandler(webapp.RequestHandler):
    def post(self):
        logging.info("device post:" + self.request.url)
        url = urlparse(self.request.url)
        # http://localhost:8084/passbook/v1/devices/deviceLibraryIdentifier/registrations/passTypeIdentifier/serialNumber
        path = url.path.split('/')
        deviceLibraryIdentifier = path[4]
        passTypeIdentifier = path[6]
        serialNumber = path[7]
        logging.info("deviceLibraryIdentifier: " + deviceLibraryIdentifier)
        logging.info("passTypeIdentifier: " + passTypeIdentifier)
        logging.info("serialNumber: " + serialNumber)
        args = json.loads(self.request.body)
        pushToken = args['pushToken']
        logging.info("pushToken: " + pushToken)
        # Remember this device in our database
        device = RegisteredDevice()
        device.deviceLibraryIdentifier = deviceLibraryIdentifier
        device.passTypeIdentifier = passTypeIdentifier
        device.serialNumber = serialNumber
        device.pushToken = pushToken
        device.put()
        # Register for push notifications
        airship = urbanairship.Airship(PassAppKey(), PassAppMasterSecret())
        airship.register(pushToken)

        self.response.set_status(201)
        # If the serial number is already registered for this device, return HTTP status 200. 
        # If registration succeeds, return HTTP status 201.
        # If the request is not authorized, return HTTP status 401.

    def get(self):
        logging.info("device get:" + self.request.url)
        url = urlparse(self.request.url)
        path = url.path.split('/')
        deviceLibraryIdentifier = path[4]
        passTypeIdentifier = path[6]
        passesUpdatedSince=self.request.get('passesUpdatedSince')
        # If the passesUpdatedSince parameter is present, return only the passes that have been updated since the time 
        # indicated by tag. Otherwise, return all passes.
        latest = { 'lastUpdated': get_pass_last_modified_for_user(), 'serialNumbers': ['ABCDEF-12345'] }
        self.response.set_status(200)
        self.response.out.write(json.dumps(latest))
        logging.info("json: " + json.dumps(latest, sort_keys=True, indent=4, ensure_ascii=False));
        # If there are matching passes, return HTTP status 200 with a JSON dictionary with the following keys and values:
        #   lastUpdated (string)
        #       The current modification tag.
        #   serialNumbers (array of strings)
        #       The serial numbers of the matching passes.
        # If there are no matching passes, return HTTP status 204.
        
    def delete(self):
        logging.info("device delete:" + self.request.url)
        url = urlparse(self.request.url)
        # http://localhost:8084/passbook/v1/devices/deviceLibraryIdentifier/registrations/passTypeIdentifier/serialNumber
        path = url.path.split('/')
        deviceLibraryIdentifier = path[4]
        passTypeIdentifier = path[6]
        serialNumber = path[7]
        logging.info("deviceLibraryIdentifier: " + deviceLibraryIdentifier)
        logging.info("passTypeIdentifier: " + passTypeIdentifier)
        logging.info("serialNumber: " + serialNumber)
        
        airship = urbanairship.Airship(PassAppKey(), PassAppMasterSecret())
        devices = RegisteredDevice().all().filter('deviceLibraryIdentifier = ', deviceLibraryIdentifier)
        results = devices.fetch(1)
        for result in results:
            # Remove the device from the push notifications
            airship.deregister(result.pushToken)
            # Remove the device from our database
            result.delete()
        
        self.response.set_status(200)
        # If disassociation succeeds, return HTTP status 200.
        # If the request is not authorized, return HTTP status 401. 

class PassesHandler(webapp.RequestHandler):
    def get(self):
        logging.info("passes get:" + self.request.url)
        authorizationToken = None
        try:
            authorizationHeader = self.request.headers["Authorization"]
            # Remove "ApplePass " from the Authorization Header
            authorizationToken = authorizationHeader[len("ApplePass "):]
        except:
            logging.info("auth failed, key not found")
        if authorizationToken == "3C04F878-958F-46D1-85C3-19504E40310C":
            pass
        else:
            if authorizationToken is None:
                logging.info("Empty authorizationToken")
            else:
                logging.info("Unrecognized auth: " + authorizationToken)
            self.response.set_status(401)
            return
        
        modifiedSince = None
        passModified = get_pass_last_modified_for_user()
        try:
            modifiedSince = self.request.headers["If-Modified-Since"]
        except:
            pass
        if modifiedSince is None:
            logging.info("modified-since: none, passModified: " + passModified)
            modifiedSince = 0
        else:
            logging.info("modified-since: " + modifiedSince)
        if float(modifiedSince) < float(passModified):
            url = urlparse(self.request.url)
            # http://localhost:8084/passbook/v1/passes/passTypeIdentifier/serialNumber
            path = url.path.split('/')
            passTypeIdentifier = path[4]
            serialNumber = path[5]
            logging.info("passTypeIdentifier: " + passTypeIdentifier)
            logging.info("serialNumber: " + serialNumber)
            pass_data = get_pass_data_for_user()
            self.response.headers["Content-Type"] = "application/vnd.apple.pkpass"
            self.response.headers["last-modified"] = passModified
            self.response.out.write(pass_data)
            self.response.set_status(200)
        else:
            self.response.set_status(304)
        # If request is authorized, return HTTP status 200 with a payload of the pass data. 
        # If the request is not authorized, return HTTP status 401.
        # Support standard HTTP caching on this endpoint: check for the If-Modified-Since header or entity tags, 
        # and return HTTP status code 304 if the pass has not changed.
        
def main():
    application = webapp.WSGIApplication([('/passbook/v1/devices/.*', DeviceHandler),
                                          ('/passbook/v1/passes/.*',  PassesHandler),
                                          ('/passbook/v1/log.*',      LogHandler)],
                                         debug=True)
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()
