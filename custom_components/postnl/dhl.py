import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3 import Retry

_LOGGER = logging.getLogger(__name__)


class DHL:
    base_url: str = "https://my.dhlecommerce.nl/"

    def __init__(self):
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

    def login(self, username: str, password: str):
        return self.client.post(
            url=self.base_url + 'api/user/login',
            json={
                'email': username,
                'password': password
            }
        ).json()

    def user(self):
        return self.client.get(
            url=self.base_url + 'api/user',
        ).json()

    def parcels(self):
        return self.client.get(
            url=self.base_url + 'receiver-parcel-api/parcels',
        ).json()
