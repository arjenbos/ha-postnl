# PostNL Home Assistant integration

Track parcels received and sent by your PostNL account in Home Assistant. This
custom integration requires Home Assistant 2026.10.0 or newer and a PostNL account.
It creates an account device and two sensors:

| Sensor | State | Attributes |
| --- | --- | --- |
| Delivery | Number of incoming parcels still in transit | `enroute` and `delivered` lists of incoming parcels |
| Distribution | Number of outgoing parcels still in transit | `enroute` and `delivered` lists of outgoing parcels |

Package attributes include the tracking link, status, planned and expected delivery
windows, delivery address type, and last update when available. These retain the
existing package-card structure. Existing account-based unique IDs and registered
entity IDs are preserved; new sensors use the account device name and translated
sensor names. Use your actual entity IDs in dashboards and automations.

## Installation

1. Install the [PostNL browser extension](https://github.com/arjenbos/ha-postnl-browser-extensions).
   It bridges PostNL's mobile-app redirect to Home Assistant's OAuth callback.
2. Add this repository to HACS as an integration, install it, and restart Home Assistant.
3. Open **Settings → Devices & services → Add integration → PostNL**.
4. If prompted for application credentials, enter a name and placeholder Client ID
   and Client secret. The integration uses PostNL's registered public client;
   these two credential fields are ignored. Your password is entered only on
   PostNL's sign-in page.
5. Sign in to PostNL. Check that the browser extension sends the callback to your
   intended Home Assistant URL, then complete setup.

Each PostNL account can be configured once. Different accounts can be added as
separate entries. The integration validates account information before saving an
entry. There are no integration-specific options, service actions, custom triggers,
or custom conditions; the sensors can be used in Home Assistant's standard state
triggers, conditions, and templates.

## Updates and authentication

Both sensors share one update every 90 seconds while at least one sensor is enabled.
A normal cycle fetches a profile and shipment list, then tracking details for each
undelivered parcel. Delivered parcels do not need extra tracking requests. At most
four tracking requests run together. Each request has a 30-second timeout, and a
whole update is bounded to 60 seconds. Offline or invalid responses make the
sensors unavailable until a later update succeeds; an outage and recovery are
logged once each. Updates can be disabled using Home Assistant's system options.

Tokens are refreshed automatically. If PostNL revokes access, Home Assistant asks
you to reauthenticate. Use the same account: another account's credentials cannot
overwrite the existing entry. For older entries, identity can be recovered from
stored account data or the existing device. If identity cannot be established,
remove and re-add the entry for the intended account.

## Dashboard cards and examples

Optional package cards that use the package attributes:

- [lovelace-postnl-card](https://github.com/peternijssen/lovelace-postnl-card)
- [hki-postnl-card](https://github.com/jimz011/hki-postnl-card)

Cards are maintained separately and are not required to use the sensors. You can
show the counts in a standard Entities card, or use a Numeric state trigger when
Delivery rises above zero to notify you about incoming parcels. For templates,
replace the example entity ID with the one shown in your entity registry:

```jinja
{{ state_attr('sensor.your_account_delivery', 'enroute') | default([], true) | count }}
```

## Troubleshooting and limitations

- Setup depends on the browser extension, a reachable Home Assistant callback URL,
  and PostNL's cloud APIs. This repository does not implement the extension.
- If setup fails temporarily, Home Assistant retries. If credentials are rejected,
  use the reauthentication flow instead of repeatedly adding the account.
- If the response lacks a stable account ID, setup waits rather than creating
  invalid entities. Retry later and check whether your account works on PostNL's site.
- Some shipment details are optional. Missing status becomes `Unknown`; delivery
  windows fall back to shipment data when tracking details are unavailable.
- Shipment descriptions from PostNL remain in the language supplied by the API;
  tracking requests currently ask for Dutch.
- Upstream polling limits are not documented here; the existing 90-second interval
  is retained. Very large accounts may exceed the overall update deadline.
- Diagnostics are available from the integration menu. They include status and
  package counts, excluding account identifiers, email, tokens, barcodes, links,
  and raw parcel data. These are useful when reporting issues.

Report issues using the repository issue tracker, including your Home Assistant
version and diagnostics. Never attach OAuth tokens or raw account/parcel payloads.

## Removal

1. Open **Settings → Devices & services → PostNL** and delete the account entry.
2. Remove the integration from HACS and restart Home Assistant if you no longer
   use any PostNL entries. Manual installations can remove `custom_components/postnl`.
3. Remove unused application credentials from **Settings → Devices & services →
   Application credentials**, and uninstall the browser extension if no longer needed.

Removing the integration stops polling and removes its managed devices/entities.
Remove or update any dashboard cards and automations that reference those entities.

## Development

See [tests/README.md](tests/README.md) for the test environment and validation commands.
`quality_scale.yaml` tracks progress; it does not claim an
official Home Assistant quality tier. Core admission still requires extracting the
PostNL protocol client into a maintained PyPI package with public source, release
provenance, and an issue tracker, plus official documentation/branding review.
