# ***REMOVED***?language=nl

import logging

import requests

_LOGGER = logging.getLogger(__name__)


class PostNLJouwAPI:
    base_url: str = "https://jouw.postnl.nl/track-and-trace/"

    def __init__(self, access_token: str):
        self.client = requests.Session()

        self.client.headers = {
            "Authorization": "Bearer " + access_token
        }

    def track_and_trace(self, key):
        response = self.client.get(self.base_url + "/api/trackAndTrace/" + key + "?language=nl")

        return response.json()
