# Testing the PostNL integration

Install the test dependencies with Python 3.13:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

`pytest-homeassistant-custom-component==0.13.287` supplies Home Assistant's test
fixtures and pins Home Assistant to 2025.10.2. This deliberately reproduces the
existing development environment; it does not certify compatibility with newer
Home Assistant releases. Upgrade the test plugin and its matching Python version
together when updating the supported Home Assistant baseline.

Tests follow the [Home Assistant integration testing guidance](https://developers.home-assistant.io/docs/development_testing/):
use `hass`, `MockConfigEntry`, the flow/config-entry managers, state machine, and
entity/device registries. Integration tests mock PostNL service methods while
running real OAuth, setup, coordinator, and sensor code. Client tests mock HTTP
responses using `requests_mock`; OAuth token exchanges use `aioclient_mock`.
Fixture payloads and credentials are synthetic. External network sockets are
disabled for the entire suite; local Unix sockets remain available for asyncio.

Coverage includes branches and has a 95% minimum. The GitHub Actions test job
installs the same pinned environment, checks test formatting/lint, runs the suite,
and uploads `coverage.xml`. Config-flow and application-credentials coverage
should remain at 100%.

## Test modules

| Module | Behavior |
| --- | --- |
| `test_config_flow.py` | PKCE authorization/code exchange, cancellation, token failures, missing credentials, reauthentication. |
| `test_init.py` | Setup, registries, connection retries, entity-ID migration, unloading. |
| `test_sensor.py` | Counts, package attributes, delivery windows, polling failures/recovery, stale attribute removal. |
| `test_auth.py` | Expired/rejected access-token refresh and refresh-token rejection. |
| `test_api.py` | REST/GraphQL authentication, operations, JSON results, query errors. |
| `test_known_issues.py` | Six desired behaviors currently broken in production. |

The six known issues are secret logging, OAuth connection error handling, initial
refresh retries, duplicate accounts, account identity during reauthentication,
and nullable shipment status. They have `xfail(strict=True)` markers accepting
only assertion failures. Unexpected passes fail the suite, requiring the marker
to be removed when the implementation is fixed. Unexpected exception types are not suppressed. These tests do not make those behaviors compliant.

To see the failures without expected-failure handling:

```sh
.venv/bin/python -m pytest tests/test_known_issues.py --runxfail --no-cov
```

To check coverage from passing tests alone:

```sh
.venv/bin/python -m pytest --ignore=tests/test_known_issues.py
```
