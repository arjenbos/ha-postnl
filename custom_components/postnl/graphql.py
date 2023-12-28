import logging

import requests
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport
from graphql import DocumentNode

_LOGGER = logging.getLogger(__name__)


class PostNLGraphql:
    endpoint: str = "https://jouw.postnl.nl/account/api/graphql"
    client: Client

    def __init__(self, access_token: str):
        self.client = Client(transport=RequestsHTTPTransport(
            url=self.endpoint,
            verify=True,
            retries=3,
            timeout=60,
            headers={
                'Authorization': 'Bearer ' + access_token
            }
        ))

    def call(self, query: str):
        query = gql(query)

        return self.client.execute(query)

    def profile(self):
        _LOGGER.debug('Fetching profile')
        query = """
            query {
              profile {
                ...ProfileData
                __typename
              }
            }
            
            fragment ProfileData on Profile {
              username
              countryOfRegistration
              mobilePhoneNumber
              preferredLanguage
              created
              person {
                gender
                initials
                firstName
                middleName
                lastName
                __typename
              }
              homeAddress {
                street
                houseNumber
                houseNumberSuffix
                postalCode
                city
                country
                addressFeatures {
                  featureType
                  creationDate
                  __typename
                }
                availablePreferences {
                  delivery {
                    overall
                    parcel
                    retail
                    publicParcelLocker
                    availableForValidation
                    __typename
                  }
                  notAtHome {
                    overall
                    availableForValidation
                    __typename
                  }
                  __typename
                }
                deliveryPreferences {
                  defaultDeliveryLocation
                  __typename
                }
                notAtHomePreferences {
                  safePlace
                  instructions
                  consentDate
                  deliveryLocation
                  lastUpdated
                  __typename
                }
                __typename
              }
              extraEmailAddresses {
                emailAddress
                __typename
              }
              optIns {
                optInType
                optIn
                optInCreatedAt
                optInChangedAt
                __typename
              }
              profileFeatures {
                featureType
                creationDate
                creationSource
                __typename
              }
              antiPhishing {
                code
                __typename
              }
              __typename
            }
        """

        result = self.call(query)

        return result

    def shipments(self):
        _LOGGER.debug('Fetching shipments')

        query = """
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

        result = self.call(query)

        return result
