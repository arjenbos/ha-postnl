import {Shipment} from "./shipment";

export interface DeliveryObject {
    attributes: {
        delivered: Shipment[];
        enroute: Shipment[];
    }
}