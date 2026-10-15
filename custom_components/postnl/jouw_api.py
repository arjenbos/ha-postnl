"""Asynchronous PostNL tracking requests."""

from urllib.parse import quote

from .api import JsonObject, PostNLAPI


class PostNLJouwAPI(PostNLAPI):
    """Retrieve tracking information without owning a separate session."""

    base_url = "https://jouw.postnl.nl/track-and-trace"

    async def track_and_trace(self, key: str) -> JsonObject:
        """Return tracking details for a single shipment."""
        return await self.request(
            "GET",
            f"{self.base_url}/api/trackAndTrace/{quote(key, safe='')}?language=nl",
        )
