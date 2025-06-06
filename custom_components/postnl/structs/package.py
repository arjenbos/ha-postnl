class Package:
    key: str
    name: str
    url: str
    shipment_type: str
    status_message: str
    delivered: bool
    delivery_date: str | None
    delivery_address_type: str | None
    planned_date: str | None
    planned_from: str | None
    planned_to: str | None
    expected_datetime: str | None

    def __init__(
            self,
            key: str,
            name: str,
            url: str,
            shipment_type: str,
            status_message: str,
            delivered: bool,
            delivery_date: str | None = None,
            delivery_address_type: str | None = None,
            planned_date: str | None = None,
            planned_from: str | None = None,
            planned_to: str | None = None,
            expected_datetime: str | None = None,
    ):
        self.key = key
        self.name = name
        self.url = url
        self.shipment_type = shipment_type
        self.status_message = status_message
        self.delivered = delivered
        self.delivery_date = delivery_date
        self.delivery_address_type = delivery_address_type
        self.planned_date = planned_date
        self.planned_from = planned_from
        self.planned_to = planned_to
        self.expected_datetime = expected_datetime
