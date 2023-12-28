import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3 import Retry

_LOGGER = logging.getLogger(__name__)


class PostNLLoginAPI:
    base_url: str = "https://login.postnl.nl/101112a0-4a0f-4bbb-8176-2f1b2d370d7c/"

    def __init__(self, access_token: str):
        self.client = requests.Session()
        self.client.mount(
            prefix='https://',
            adapter=HTTPAdapter(
                max_retries=Retry(
                    total=5,
                    backoff_factor=3
                )
            )
        )
        self.client.headers = {
            "Authorization": "Bearer " + access_token
        }

    def userinfo(self):
        response = self.client.get(self.base_url + "/profiles/oidc/userinfo")

        return response.json()
