"""Serializable package data exposed to package cards."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Package:
    """A tracked parcel and its optional delivery windows."""

    key: str
    name: str
    url: str
    shipment_type: str
    status_message: str
    delivered: bool
    delivery_date: str | None = None
    delivery_address_type: str | None = None
    planned_date: str | None = None
    planned_from: str | None = None
    planned_to: str | None = None
    expected_datetime: str | None = None
    expected_from: str | None = None
    expected_to: str | None = None
    last_update: str | None = None
