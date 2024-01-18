import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3 import Retry

_LOGGER = logging.getLogger(__name__)


class PostNLJouwAPI:
    base_url: str = "https://jouw.postnl.nl/track-and-trace/"

    def __init__(self, access_token: str):
        self.client = requests.Session()
        self.client.mount(
            prefix='https://',
            adapter=HTTPAdapter(
                max_retries=Retry(
                    total=5,
                    backoff_factor=3
                ),
                pool_maxsize=25,
                pool_block=True
            )
        )
        self.client.headers = {
            "Authorization": "Bearer " + access_token
        }

    def track_and_trace(self, key):
        response = self.client.get(self.base_url + "/api/trackAndTrace/" + key + "?language=nl")

        return response.json()
