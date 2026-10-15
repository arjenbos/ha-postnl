"""Asynchronous GraphQL operations for the PostNL account API."""

from .api import JsonObject, PostNLAPI, PostNLAuthenticationError, PostNLDataError


class PostNLGraphql(PostNLAPI):
    """Execute the account queries using the injected HTTP session."""

    endpoint = "https://jouw.postnl.nl/account/api/graphql"

    async def call(self, query: str) -> JsonObject:
        """Unwrap GraphQL data and classify explicit authentication errors."""
        result = await self.request("POST", self.endpoint, json={"query": query})
        if errors := result.get("errors"):
            if not isinstance(errors, list) or not all(
                isinstance(error, dict) for error in errors
            ):
                raise PostNLDataError("PostNL returned invalid GraphQL errors")
            if any(
                isinstance(error.get("extensions"), dict)
                and error["extensions"].get("code")
                in ("UNAUTHENTICATED", "UNAUTHORIZED")
                for error in errors
            ):
                raise PostNLAuthenticationError("PostNL rejected authentication")
            raise PostNLDataError("PostNL returned a GraphQL error")
        data = result.get("data")
        if not isinstance(data, dict):
            raise PostNLDataError("PostNL returned invalid GraphQL data")
        return data

    async def profile(self) -> JsonObject:
        """Retrieve PostNL profile."""
        return await self.call(
            """
            query {
              profile {
                ...ProfileData
                __typename
              }
            }
            
            fragment ProfileData on Profile {
              username
              __typename
            }
        """
        )

    async def shipments(self) -> JsonObject:
        """Retrieve PostNL shipments."""
        return await self.call(
            """
        query {
          trackedShipments {
            receiverShipments {
              ...shipment
              __typename
            }
            senderShipments {
              ...shipment
              __typename
            }
            __typename
          }
        }
        fragment shipment on TrackedShipmentResultType {
          key
          creationDateTime
          title
          barcode
          delivered
          deliveredTimeStamp
          deliveryWindowFrom
          deliveryWindowTo
          deliveryWindowType
          detailsUrl
          shipmentType
          deliveryAddressType
          sourceAccountId
          sourceDisplayName
          __typename
        }
        """
        )
