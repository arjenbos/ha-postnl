"""Test the bundled PostNL clients at their HTTP boundaries."""

import re

import pytest
from gql.transport.exceptions import TransportQueryError
from requests_mock import Mocker

from custom_components.postnl.graphql import PostNLGraphql
from custom_components.postnl.jouw_api import PostNLJouwAPI
from custom_components.postnl.login_api import PostNLLoginAPI


@pytest.mark.parametrize(
    ("client_class", "method", "args", "url", "payload"),
    [
        (
            PostNLLoginAPI,
            "userinfo",
            (),
            "https://login.postnl.nl/101112a0-4a0f-4bbb-8176-2f1b2d370d7c/profiles/oidc/userinfo",
            {"account_id": "test-account"},
        ),
        (
            PostNLJouwAPI,
            "track_and_trace",
            ("test-key",),
            "https://jouw.postnl.nl/track-and-trace/api/trackAndTrace/test-key?language=nl",
            {"colli": {}},
        ),
    ],
)
def test_rest_client(
    requests_mock: Mocker,
    client_class: type[PostNLLoginAPI] | type[PostNLJouwAPI],
    method: str,
    args: tuple,
    url: str,
    payload: dict,
) -> None:
    """Send authentication and return the decoded JSON response."""
    # Accept normalized paths as well as the existing duplicate separators.
    pattern = (
        re.escape(url).replace("/profiles/", "/+profiles/").replace("/api/", "/+api/")
    )
    requests_mock.get(re.compile(pattern), json=payload)
    client = client_class("test-token")
    try:
        assert getattr(client, method)(*args) == payload
    finally:
        client.client.close()
    assert requests_mock.last_request.headers["Authorization"] == "Bearer test-token"


@pytest.mark.parametrize(
    ("method", "field", "payload"),
    [
        ("profile", "profile", {"profile": {"username": "test@example.com"}}),
        (
            "shipments",
            "trackedShipments",
            {"trackedShipments": {"receiverShipments": [], "senderShipments": []}},
        ),
    ],
)
def test_graphql_client(
    requests_mock: Mocker, method: str, field: str, payload: dict
) -> None:
    """Submit the expected operation and unwrap GraphQL data."""
    requests_mock.post(PostNLGraphql.endpoint, json={"data": payload})
    client = PostNLGraphql("test-token")
    assert getattr(client, method)() == payload
    assert requests_mock.last_request.headers["Authorization"] == "Bearer test-token"
    assert field in requests_mock.last_request.json()["query"]


def test_graphql_query_error(requests_mock: Mocker) -> None:
    """Expose provider query errors to the integration's error handling."""
    requests_mock.post(PostNLGraphql.endpoint, json={"errors": [{"message": "denied"}]})
    with pytest.raises(TransportQueryError, match="denied"):
        PostNLGraphql("test-token").shipments()
