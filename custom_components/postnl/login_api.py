"""Asynchronous PostNL account information requests."""

from .api import JsonObject, PostNLAPI


class PostNLLoginAPI(PostNLAPI):
    """Retrieve the account behind a PostNL access token."""

    base_url = "https://login.postnl.nl/101112a0-4a0f-4bbb-8176-2f1b2d370d7c"

    async def userinfo(self) -> JsonObject:
        """Return user information for the authenticated account."""
        return await self.request("GET", f"{self.base_url}/profiles/oidc/userinfo")
