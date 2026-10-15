"""Shared asynchronous HTTP handling for the PostNL clients."""

from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

type JsonObject = dict[str, Any]

REQUEST_TIMEOUT = ClientTimeout(total=30, connect=10, sock_read=20)


class PostNLError(Exception):
    """Base exception for a failed PostNL request."""


class PostNLAuthenticationError(PostNLError):
    """Credentials have expired or have been rejected."""


class PostNLConnectionError(PostNLError):
    """The service could not be reached or returned an HTTP failure."""


class PostNLDataError(PostNLError):
    """The service returned an invalid or unsuccessful response."""


class PostNLAPI:
    """Use an injected session without taking ownership of its lifecycle."""

    def __init__(self, session: ClientSession, access_token: str) -> None:
        """Initialize the client with the caller's session and token."""
        self.session = session
        self.access_token = access_token

    async def request(
        self, method: str, url: str, *, json: JsonObject | None = None
    ) -> JsonObject:
        """Return validated JSON without exposing response bodies or secrets."""
        try:
            async with self.session.request(
                method,
                url,
                headers={"Authorization": f"Bearer {self.access_token}"},
                json=json,
                timeout=REQUEST_TIMEOUT,
            ) as response:
                if response.status in (401, 403):
                    raise PostNLAuthenticationError("PostNL rejected authentication")
                response.raise_for_status()
                payload = await response.json()
        except (ClientError, TimeoutError) as err:
            raise PostNLConnectionError("Unable to communicate with PostNL") from err
        except ValueError as err:
            raise PostNLDataError("PostNL returned invalid JSON") from err

        if not isinstance(payload, dict):
            raise PostNLDataError("PostNL returned an invalid response")
        if payload.get("error"):
            if payload["error"] in ("invalid_token", "invalid_grant", "unauthorized"):
                raise PostNLAuthenticationError("PostNL rejected authentication")
            raise PostNLDataError("PostNL returned an API error")
        return payload
