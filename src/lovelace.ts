import {
  LitElement, html, css, unsafeCSS, property, customElement
} from 'lit-element';
import moment from 'moment';
import {DeliveryObject} from "./structs/deliveryObject";
import {Shipment} from "./structs/shipment";

interface HideOptions {
  delivered: boolean;
  header: boolean;
}

interface LanguagePack {
  unavailable_entities: string;
  title: string;
  status: string;
  delivery_date: string;
  enroute: string;
  delivered: string;
  delivery: string;
  distribution: string;
  unknown: string;
}

const DEFAULT_HIDE: HideOptions = {
  delivered: false,
  header: false,
};

const LANG: Record<string, LanguagePack> = {
  en: {
    unavailable_entities: 'The given entities are not available. Please check your card configuration',
    title: 'Title',
    status: 'Status',
    delivery_date: 'Delivery date',
    enroute: 'Enroute',
    delivered: 'Delivered',
    delivery: 'Delivery',
    distribution: 'Distribution',
    unknown: 'Unknown',
  },
  nl: {
    unavailable_entities: 'De opgegeven entiteiten zijn niet beschikbaar. Controleer je card configuratie',
    title: 'Titel',
    status: 'Status',
    delivery_date: 'Bezorgdatum',
    enroute: 'Onderweg',
    delivered: 'Bezorgd',
    delivery: 'Bezorging',
    distribution: 'Versturen',
    unknown: 'Onbekend',
  },
};

class PostNL extends LitElement {
  private _hass: any = null;
  private config: any = null;
  private deliveryObject: DeliveryObject | null = null;
  private distributionObject: DeliveryObject | null = null;
  private distributionEnroute: Shipment[] = [];
  private distributionDelivered: Shipment[] = [];
  private deliveryEnroute: Shipment[] = [];
  private deliveryDelivered: Shipment[] = [];
  private icon: string | null = null;
  private name: string | null = null;
  private dateFormat: string | null = null;
  private timeFormat: string | null = null;
  private pastDays: number | null = null;
  private _language: string = 'en';
  private _hide: HideOptions = DEFAULT_HIDE;
  private _lang: Record<string, LanguagePack> = LANG;

  set hass(hass: any) {
    this._hass = hass;

    if (this.config.delivery) {
      this.deliveryObject = hass.states[this.config.delivery];
    }

    if (this.config.distribution) {
      this.distributionObject = hass.states[this.config.distribution];
    }

    if (this.config.hide) {
      this._hide = { ...this._hide, ...this.config.hide };
    }

    if (typeof this.config.name === 'string') {
      this.name = this.config.name;
    } else {
      this.name = "PostNL";
    }

    if (this.config.icon) {
      this.icon = this.config.icon;
    } else {
      this.icon = "mdi:mailbox";
    }

    if (this.config.date_format) {
      this.dateFormat = this.config.date_format;
    } else {
      this.dateFormat = "DD MMM YYYY";
    }

    if (this.config.time_format) {
      this.timeFormat = this.config.time_format;
    } else {
      this.timeFormat = "HH:mm";
    }

    if (typeof this.config.past_days !== 'undefined') {
      this.pastDays = parseInt(this.config.past_days, 10);
    } else {
      this.pastDays = 1;
    }

    this._language = hass.language;
    // Lazy fallback
    if (this._language !== 'nl') {
      this._language = 'en';
    }

    this.deliveryEnroute = [];
    this.deliveryDelivered = [];
    this.distributionEnroute = [];
    this.distributionDelivered = [];

    // Format deliveries
    if (this.deliveryObject) {
      Object.entries(this.deliveryObject.attributes.enroute)
          .sort(
              ([, a], [, b]) => new Date(b.planned_date).getTime() - new Date(a.planned_date).getTime()
          )
          .forEach(([_, shipment]: [string, shipment: Shipment]) => {
            this.deliveryEnroute.push(shipment);
          });


      Object.entries(this.deliveryObject.attributes.delivered)
          .sort(
              (a, b) => new Date(b[1].delivery_date).getTime() - new Date(a[1].delivery_date).getTime()
          )
          .forEach(([_, shipment]) => {
            if (shipment.delivery_date != null && moment(shipment.delivery_date).isBefore(moment().subtract(this.pastDays, 'days').startOf('day'))) {
              return;
            }
            console.log('Delivery added', shipment);

            this.deliveryDelivered.push(shipment);
          });
    }

    // Format distribution
    if (this.distributionObject) {
      Object.entries(this.distributionObject.attributes.enroute)
          .sort(
              ([, a], [, b]) => new Date(b.planned_date).getTime() - new Date(a.planned_date).getTime()
          )
          .forEach(([_, shipment]: [string, shipment: Shipment]) => {
            this.distributionEnroute.push(shipment);
          });

      Object.entries(this.distributionObject.attributes.delivered)
          .sort(
              (a, b) => new Date(b[1].delivery_date).getTime() - new Date(a[1].delivery_date).getTime()
          )
          .forEach(([_, shipment]) => {
            if (shipment.delivery_date != null && moment(shipment.delivery_date).isBefore(moment().subtract(this.pastDays, 'days').startOf('day'))) {
              return;
            }

            this.distributionDelivered.push(shipment);
          });
    }
  }

  setConfig(config: any) {
    if (!config.delivery && !config.distribution) {
      throw new Error('Please define entities');
    }

    this.config = config;
  }

  private initializeObjects() {
    if (this.config) {
      this.deliveryObject = this.config.delivery ? this._hass.states[this.config.delivery] : null;
      this.distributionObject = this.config.distribution ? this._hass.states[this.config.distribution] : null;
      this._hide = { ...this._hide, ...(this.config.hide || {}) };
      this.name = this.config.name || 'PostNL';
      this.icon = this.config.icon || 'mdi:mailbox';
      this.dateFormat = this.config.date_format || 'DD MMM YYYY';
      this.timeFormat = this.config.time_format || 'HH:mm';
      this.pastDays = this.config.past_days ? parseInt(this.config.past_days, 10) : 1;
      this._language = this._hass.language || 'en';
    }
  }

  render() {
    return html`
      ${this.renderStyles()}
      <ha-card class="postnl-card">
        ${this.renderHeader()}
        <section class="info-body">
          ${this.renderDeliveryInfo()}
          ${this.renderDistributionInfo()}
        </section>
        ${this.renderDelivery()}
        ${this.renderDistribution()}
      </ha-card>
    `;
  }

  private renderHeader() {
    if (this._hide.header) return '';
    return html`
      <header>
        <ha-icon class="header__icon" .icon=${this.icon}></ha-icon>
        <h2 class="header__title">${this.name}</h2>
      </header>
    `;
  }

  private renderDeliveryInfo() {
    if (!this.deliveryObject) return '';
    return html`
      <div class="info">
        <ha-icon class="info__icon" icon="mdi:truck-delivery"></ha-icon><br />
        <span>${this.deliveryEnroute.length} ${this.translateString('enroute')}</span>
      </div>
      <div class="info">
        <ha-icon class="info__icon" icon="mdi:package-variant"></ha-icon><br />
        <span>${this.deliveryDelivered.length} ${this.translateString('delivered')}</span>
      </div>
    `;
  }

  private renderDistributionInfo() {
    if (!this.distributionObject) return '';
    return html`
      <div class="info">
        <ha-icon class="info__icon" icon="mdi:truck-delivery"></ha-icon><br />
        <span>${this.distributionEnroute.length} ${this.translateString('enroute')}</span>
      </div>
      <div class="info">
        <ha-icon class="info__icon" icon="mdi:package-variant"></ha-icon><br />
        <span>${this.distributionDelivered.length} ${this.translateString('delivered')}</span>
      </div>
    `;
  }

  private renderDelivery() {
    if (!this.deliveryObject || (!this.deliveryEnroute.length && this._hide.delivered && !this.deliveryDelivered.length)) return '';
    return html`
      <header>
        <ha-icon class="header__icon" icon="mdi:package-variant"></ha-icon>
        <h2 class="header__title">${this.translateString('delivery')}</h2>
      </header>
      <section class="detail-body">
        <table>
          <thead>
            <tr>
              <th>${this.translateString('title')}</th>
              <th>${this.translateString('status')}</th>
              <th>${this.translateString('delivery_date')}</th>
            </tr>
          </thead>
          <tbody>
            ${this.deliveryEnroute.map((delivery: any) => this.renderShipment(delivery))}
            ${this._hide.delivered ? '' : this.deliveryDelivered.map((delivery: any) => this.renderShipment(delivery))}
          </tbody>
        </table>
      </section>
    `;
  }

  private renderShipment(shipment: Shipment) {
    let delivery_date = this.translateString('unknown');
    let className = "delivered";

    // Conversion Time
    if (shipment.delivery_date != null) {
      delivery_date = this.dateConversion(shipment.delivery_date);
    } else if (shipment.planned_date != null) {
      className = "enroute";

      if (shipment.expected_datetime != null) {
        delivery_date = `${this.dateConversion(shipment.expected_datetime)} ${
            this.timeConversion(shipment.expected_datetime)}`;
      } else {
        delivery_date = `${this.dateConversion(shipment.planned_date)} ${
            this.timeConversion(shipment.planned_from)} - ${
            this.timeConversion(shipment.planned_to)}`;
      }
    }

    return html`
      <tr class="${className}">
        <td class="name"><a href="${shipment.url}" target="_blank">${shipment.name}</a></td>
        <td>${shipment.status_message}</td>
        <td>${delivery_date}</td>
      </tr>
    `;
  }

  timeConversion(date: string) {
    const momentDate = moment(date);
    momentDate.locale(this._language);

    return momentDate.format(this.timeFormat);
  }

  private renderDistribution() {
    if (!this.distributionObject || (!this.distributionEnroute.length && this._hide.delivered && !this.distributionDelivered.length)) return '';
    return html`
      <header>
        <ha-icon class="header__icon" icon="mdi:truck-delivery"></ha-icon>
        <h2 class="header__title">${this.translateString('distribution')}</h2>
      </header>
      <section class="detail-body">
        <table>
          <thead>
            <tr>
              <th>${this.translateString('title')}</th>
              <th>${this.translateString('status')}</th>
              <th>${this.translateString('delivery_date')}</th>
            </tr>
          </thead>
          <tbody>
            ${this.distributionEnroute.map((distribution: any) => this.renderShipment(distribution))}
            ${this._hide.delivered ? '' : this.distributionDelivered.map((distribution: any) => this.renderShipment(distribution))}
          </tbody>
        </table>
      </section>
    `;
  }

  private dateConversion(date: string) {
    const momentDate = moment(date);
    momentDate.locale(this._language);

    return momentDate.calendar(null, {
      sameDay: '[Today]',
      nextDay: '[Tomorrow]',
      sameElse: this.dateFormat
    });
  }

  private translateString(key: keyof LanguagePack): string {
    return this._lang[this._language][key] || key;
  }

  private renderStyles() {
    return html`
      <style is="custom-style">
          ha-card {
            -webkit-font-smoothing: var(
              --paper-font-body1_-_-webkit-font-smoothing
            );
            font-size: var(--paper-font-body1_-_font-size);
            font-weight: var(--paper-font-body1_-_font-weight);
            line-height: var(--paper-font-body1_-_line-height);
            padding-bottom: 16px;
          }
          ha-card.no-header {
            padding: 16px 0;
          }
          .info-body,
          .detail-body {
            display: flex;
            flex-direction: row;
            justify-content: space-around;
            align-items: center;
          }
          .info {
            text-align: center;
          }

          .info__icon {
            color: var(--paper-item-icon-color, #44739e);
          }
          .detail-body table {
            padding: 0px 16px;
            width: 100%;
          }
          .detail-body td {
            padding: 2px;
          }
          .detail-body thead th {
            text-align: left;
          }
          .detail-body tbody tr:nth-child(odd) {
            background-color: var(--paper-card-background-color);
          }
          .detail-body tbody tr:nth-child(even) {
            background-color: var(--secondary-background-color);
          }
          .detail-body tbody td.name a {
            color: var(--primary-text-color);
            text-decoration-line: none;
            font-weight: normal;
          }
          .img-body {
            margin-bottom: 10px;
            text-align: center;
          }
          .img-body img {
            padding: 5px;
            background: repeating-linear-gradient(
              45deg,
              #B45859,
              #B45859 10px,
              #FFFFFF 10px,
              #FFFFFF 20px,
              #122F94 20px,
              #122F94 30px,
              #FFFFFF 30px,
              #FFFFFF 40px
            );
          }

          header {
            display: flex;
            flex-direction: row;
            align-items: center;
            font-family: var(--paper-font-headline_-_font-family);
            -webkit-font-smoothing: var(
              --paper-font-headline_-_-webkit-font-smoothing
            );
            font-size: var(--paper-font-headline_-_font-size);
            font-weight: var(--paper-font-headline_-_font-weight);
            letter-spacing: var(--paper-font-headline_-_letter-spacing);
            line-height: var(--paper-font-headline_-_line-height);
            text-rendering: var(
              --paper-font-common-expensive-kerning_-_text-rendering
            );
            opacity: var(--dark-primary-opacity);
            padding: 24px
              16px
              16px;
          }
          .header__icon {
            margin-right: 8px;
            color: var(--paper-item-icon-color, #44739e);
          }
          .header__title {
            font-size: var(--thermostat-font-size-title);
            line-height: var(--thermostat-font-size-title);
            font-weight: normal;
            margin: 0;
            align-self: left;
          }

          footer {
            padding: 16px;
            color: red;
          }
      </style>`
  }
}

customElements.define("postnl-card", PostNL);