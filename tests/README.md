# Testing the PostNL integration

Install the test dependencies with Python 3.14.2 or newer:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

`pytest-homeassistant-custom-component==0.13.371` supplies Home Assistant's test
fixtures for Home Assistant 2026.10.0. Both packages are pinned in
`requirements-dev.txt`; CI uses Python 3.14. Upgrade the test plugin and its
matching Python version together when updating the Home Assistant baseline.

When upgrading an existing Python 3.13 environment, recreate it first:

```sh
python3.14 -m venv --clear .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

Tests follow the [Home Assistant integration testing guidance](https://developers.home-assistant.io/docs/development_testing/):
use `hass`, `MockConfigEntry`, the flow/config-entry managers, state machine, and
entity/device registries. Integration tests mock PostNL service methods while
running real OAuth, setup, coordinator, and sensor code. Client tests and OAuth token exchanges mock HTTP
responses using `aioclient_mock`.
Fixture payloads and credentials are synthetic. External network sockets are
disabled for the entire suite; local Unix sockets remain available for asyncio.

Coverage includes branches and has a 95% minimum. The GitHub Actions test job
installs the same pinned environment, checks all Python formatting/lint and strict integration typing, runs the suite,
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
| `test_known_issues.py` | Six regression tests for the defects fixed after the review. |
| `test_validation.py` | Invalid responses, legacy identities, polling concurrency, diagnostics privacy, and migration safety. |

All six previously expected failures are now ordinary passing regression tests.
No tests are skipped or marked as expected failures.

Run the same checks as CI:

```sh
.venv/bin/ruff check custom_components tests
.venv/bin/ruff format --check custom_components tests
.venv/bin/mypy
.venv/bin/python -m pytest --cov-report=xml
```

The PostNL HTTP clients use Home Assistant's managed aiohttp session, explicit
request deadlines, and bounded tracking concurrency. The fixtures mock the async
service methods with AsyncMock while preserving the integration lifecycle.
