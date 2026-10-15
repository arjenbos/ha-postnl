# Home Assistant development standards review

Review date: 15 October 2026. Repository revision: `8969f05` (`Bug fix`).

**Verdict: the integration does not meet the current Home Assistant Core development baseline.** It implements several useful Home Assistant patterns, but has baseline compliance gaps and confirmed error-handling defects. Formatting alone will not resolve them.

This is a custom integration distributed through HACS. Home Assistant does not require custom integrations to pass Core admission review or obtain Bronze certification before loading them. This report distinguishes Core requirements, Bronze requirements for new Core integrations, higher-tier rules, and ordinary correctness defects. It is an independent code review, not an official quality-scale assessment. See the [quality-scale scope and tiers](https://developers.home-assistant.io/docs/core/integration-quality-scale/).

## Scope and verification

Reviewed all 11 Python files under `custom_components`, including the empty namespace initializer: 756 source lines, 10 nonempty integration files, 38 functions/methods. Also reviewed the manifest, strings, requirements, README, and both validation workflows. Browser-extension implementation is in another repository and was outside this review.

The requested knowledge-graph tools were tried first; they reported this project is not indexed. Source was then read directly.

Local environment: Python 3.13.16, Home Assistant 2025.10.2, gql 4.0.0, Ruff 0.15.13, pytest 8.4.2. Developer documentation was checked online on the review date. Current Core `dev` source was consulted where relevant; it is a moving development branch, not a claim about a tested stable release.

| Check | Result |
| --- | --- |
| AST parsing | All 11 Python files parse successfully. |
| `ruff check custom_components --output-format concise` | Fails: one unused import at `sensor.py:9`. Uses Ruff defaults because the repository has no Ruff configuration. |
| `ruff format --check custom_components` | Fails: all 10 nonempty integration files would be reformatted; the empty initializer passes. |
| Expanded lint, command below | 37 findings: 8 D100, 6 D101, 10 D102, 1 D104, 5 D107, 2 D202, 4 I001, 1 F401. |
| `python -m pytest -q` | No tests collected. This is not a passing test suite; pytest's no-tests exit status is 5. |
| Mocked OAuth connection failure | Reproduces `AttributeError: 'ClientConnectionError' object has no attribute 'status'`. |
| Mocked REST HTTP 401 | Both REST helpers return the error JSON instead of raising; neither GET supplies timeout arguments. |
| Mocked shipment with `statusPhase: null` | Reproduces `AttributeError: 'NoneType' object has no attribute 'get'`. |
| Sensor inheritance inspection | `PostNLDelivery` does not inherit `SensorEntity`; it also leaves `has_entity_name` at the default false value. |

The expanded lint command was:

```sh
.venv/bin/ruff check custom_components/postnl \
  --select E,F,I,D,B,UP,S113 --ignore E501,D203,D213
```

This is a diagnostic selection, not a reproduction of Core CI. Current Core has a larger [Ruff configuration](https://github.com/home-assistant/core/blob/dev/pyproject.toml), different exclusions, and a newer required Ruff version. No claim is made that the 37 findings are the exact Core CI result. No mypy, pylint, hassfest, HACS action, current-version Home Assistant boot, live PostNL request, or browser OAuth round trip was executed. Existing CI workflow files do not establish that their latest runs passed.

Only this review document was added; implementation files were not changed. All mocked requests used synthetic values and made no network calls.

## Findings, ordered by priority

### 1. High: bearer token and personal payloads are logged

Evidence: [`__init__.py:43`](custom_components/postnl/__init__.py#L43) writes the complete access token to debug logs. [`sensor.py:30`](custom_components/postnl/sensor.py#L30) logs the complete user-information object. [`coordinator.py:49`](custom_components/postnl/coordinator.py#L49), line 88, and line 99 log shipment or tracking payloads.

The bearer-token log directly violates Home Assistant's instruction to keep authentication secrets out of logs. Debug level does not make a secret safe to expose. User/profile and tracking payloads can also contain identifying data, depending on the upstream response.

Remove the token log. Replace full-payload logging with counts and non-sensitive operational details; redact any data retained for troubleshooting. Source: [logging guidance](https://developers.home-assistant.io/docs/development_guidelines/#log-messages).

### 2. High: authentication failures are classified incorrectly, and a connection failure crashes the handler

Evidence: [`__init__.py:127`](custom_components/postnl/__init__.py#L127) catches both `ClientResponseError` and its broader `ClientError` family, then unconditionally accesses `exception.status`. A `ClientConnectionError` has no such property. The mocked failure reproduced the resulting `AttributeError`.

The handler only starts reauthentication for HTTP 400, wraps errors in generic `HomeAssistantError`, and the surrounding setup catches only `requests.exceptions.ConnectionError`. Consequently, several OAuth/network failures bypass the intended setup retry handling. Expired credentials from the REST helpers are not classified at all. Every `TransportQueryError` is treated as a reason to refresh a token, although a GraphQL query error does not necessarily mean authentication expired.

Use separate handling for transport failures, HTTP responses, and the OAuth helper's version-appropriate exceptions. Raise `ConfigEntryAuthFailed` for confirmed invalid/revoked authentication and `ConfigEntryNotReady` for transient setup failures; use `UpdateFailed` for transient polling failures. Retrying a genuinely expired token is appropriate, but must preserve the distinction between authentication and other API errors. Sources: [setup/authentication failure handling](https://developers.home-assistant.io/docs/integration_setup_failures/) and the Silver [reauthentication rule](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/reauthentication-flow/).

### 3. High: REST requests have no timeout or HTTP status validation

Evidence: [`login_api.py:28`](custom_components/postnl/login_api.py#L28) and [`jouw_api.py:30`](custom_components/postnl/jouw_api.py#L30) call `Session.get()` without a timeout and immediately parse JSON without `raise_for_status()`.

An executor keeps these calls off the event loop, but does not bound the underlying request. A stalled call can occupy a worker indefinitely. Retry settings are not a substitute for a timeout. A 401 JSON response is returned as ordinary data in the mocked check. For tracking requests, an error object with no `colli` can reach the fallback path and appear as an ordinary package with an unknown status. Userinfo error objects are treated as retryable setup failures even if authentication is invalid. Invalid JSON can raise; successful JSON with an unexpected shape is not validated.

Set explicit connect/read timeouts, check HTTP statuses, validate response shapes, and translate failures into a small set of API exceptions before handing them to Home Assistant. GraphQL already supplies a 60-second transport timeout, so the missing-timeout finding applies specifically to the two REST helpers. Source: [Requests timeouts and response handling](https://requests.readthedocs.io/en/latest/user/quickstart/).

### 4. High: the coordinator's first refresh happens too late for reliable setup retries

Evidence: [`sensor.py:22`](custom_components/postnl/sensor.py#L22) constructs the coordinator and calls `async_config_entry_first_refresh()` in the sensor platform. The integration entry point at [`__init__.py:84`](custom_components/postnl/__init__.py#L84) forwards platforms before it has established that shipment data can be fetched.

Home Assistant explicitly documents that `ConfigEntryNotReady` raised in a platform setup is too late for normal config-entry retry handling. A failed first coordinator refresh can therefore leave platform setup unsuccessful without the expected entry retry behavior.

Create the coordinator in the integration's `async_setup_entry`, await its first refresh there, store it on the entry, then forward platforms. Pass `config_entry=entry` explicitly to `DataUpdateCoordinator`. The current [coordinator implementation](https://github.com/home-assistant/core/blob/dev/homeassistant/helpers/update_coordinator.py) treats implicit entry lookup as an error for Core integrations while retaining a custom-integration exemption; omission is not, by itself, proof this custom integration cannot load. Source: [setup failure lifecycle](https://developers.home-assistant.io/docs/integration_setup_failures/).

### 5. High: config entries have no account-level duplicate prevention or reauth identity check

Evidence: [`config_flow.py:39`](custom_components/postnl/config_flow.py#L39) delegates new entries directly to the OAuth base class. It never obtains an account identifier, calls `async_set_unique_id`, or rejects an existing account. The inherited creation method was inspected locally and in current Core source; it simply creates the entry.

The reauthentication branch replaces entry data and reloads without checking that the newly authenticated account matches the original account. Logging in as a different account can silently change the account behind an entry while its old devices remain associated with it.

Fetch and validate the account after OAuth, use a stable account identifier for the config-entry unique ID, reject duplicates, and verify identity before updating an entry during reauthentication. Use Home Assistant's update/reload/abort helper where suitable. Account-based entity IDs already exist, but do not prevent duplicate config entries. Sources: Bronze [unique-config-entry](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/unique-config-entry/) and Silver [reauthentication-flow](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/reauthentication-flow/).

### 6. High for Core admission: PostNL protocol code lives inside the integration

Evidence: [`graphql.py:9`](custom_components/postnl/graphql.py#L9), [`login_api.py:10`](custom_components/postnl/login_api.py#L10), and [`jouw_api.py:10`](custom_components/postnl/jouw_api.py#L10) implement PostNL endpoints, queries, request authentication, and response handling locally.

Using generic `gql` and `requests` does not satisfy the requirement to encapsulate product/service communication in a separate library. Core expects the PostNL protocol client to be independently distributed on PyPI, with source distributions and an enabled issue tracker. Home Assistant adapters should coordinate that library and expose entities.

Extract the service client and its models into a maintained package, leaving config flows, OAuth integration, coordinators, and entities here. This is a Core admission requirement, not a custom-component loader constraint. Source: [development checklist](https://developers.home-assistant.io/docs/development_checklist/).

### 7. Medium: sensor implementation bypasses the sensor base class and Bronze naming conventions

Evidence: [`sensor.py:49`](custom_components/postnl/sensor.py#L49) derives from `CoordinatorEntity, Entity`, implements `state` and `unit_of_measurement`, and uses hard-coded `PostNL_delivery` / `PostNL_distribution` names. No `has_entity_name` flag is set.

Use `CoordinatorEntity[PostNLCoordinator], SensorEntity`, with `native_value` and `native_unit_of_measurement` or the corresponding `_attr_` fields. Set `_attr_has_entity_name = True` and choose an entity name relative to the account device. This follows the sensor contract and Bronze naming rule. Entity-name translations are a separate Gold requirement. A package-count sensor does not automatically need a special device class, nor should it use an accumulating-total state class.

Sources: [sensor entity contract](https://developers.home-assistant.io/docs/core/entity/sensor/) and [has-entity-name](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/has-entity-name/).

### 8. Medium: runtime state is stored in `hass.data`, and common auth code is in the entry-point module

Evidence: [`__init__.py:28`](custom_components/postnl/__init__.py#L28) creates an untyped domain dictionary; coordinator and sensor code retrieve auth/userinfo from it. `AsyncConfigEntryAuth` is also defined in `__init__.py`, and [`coordinator.py:10`](custom_components/postnl/coordinator.py#L10) imports auth and an indirectly imported API class from that module.

Define typed runtime state, put it on `ConfigEntry.runtime_data`, and pass the entry/coordinator directly to consumers. Move shared auth code into an appropriate module such as `api.py` or `auth.py`; import `PostNLGraphql` from its own module. Legacy `hass.data` usage can run, but fails the current Bronze runtime-data rule. Sources: [runtime-data](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/runtime-data/) and [common-modules](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/common-modules/).

### 9. Medium: dependency declaration does not request gql's chosen transport

Evidence: [`manifest.json:12`](custom_components/postnl/manifest.json#L12) declares only `gql`, while `graphql.py` imports `gql.transport.requests`. Installed gql 4.0.0 metadata shows that `requests_toolbelt` is supplied through its `requests` extra rather than its base dependencies. A development environment with that package already installed can hide the missing declaration.

Declare the required extra/dependencies for the transport, or replace them with the extracted client's properly declared dependencies. Core requires pinned requirements. An unpinned requirement is not automatically a custom-integration hassfest violation: current [hassfest requirement validation](https://github.com/home-assistant/core/blob/dev/script/hassfest/requirements.py) distinguishes Core and custom integrations and also checks conflicts with packages supplied by Home Assistant. Choose versions compatible with the target Home Assistant release; do not blindly pin Core-owned packages.

The integration's `version` and repository issue/documentation URLs are appropriate for custom distribution. For a Core submission, remove the custom version and issue-tracker fields and supply the official integration documentation URL. Source: [manifest requirements](https://developers.home-assistant.io/docs/creating_integration_manifest/).

### 10. Medium: required formatting, import hygiene, and documentation conventions fail

All 10 integration files fail the installed formatter check. The baseline lint failure is an unused entity-registry import in `sensor.py:9`. Expanded lint also identifies import ordering and missing module/class/method docstrings. Only `sensor.py` has a module docstring among the 10 integration modules.

Run the target-compatible Ruff formatter and lint configuration, remove the unused import, organize imports, and add useful docstrings. Add checks to CI: the current workflows run hassfest and HACS validation, but no Python formatter, lint, or pytest job. Home Assistant enforces formatting and Python/docstring conventions for submitted code; a HACS action does not replace those checks. Source: [style guidelines](https://developers.home-assistant.io/docs/development_guidelines/).

### 11. High for Bronze admission: config-flow tests are absent

No test source files were present; pytest collects zero tests. The directory named `tests` does not provide a test suite. Bronze requires complete config-flow coverage. Existing external validation workflows cannot establish behavior such as duplicate prevention, token recovery, or setup retries.

Add Home Assistant fixture-based tests for OAuth success/failure, duplicate accounts, cancellation, reauth success, reauth with a different account, and connection failures. Also cover first-refresh failures, sensor values/availability, unload, HTTP errors/timeouts, and nullable API fields as targeted regression tests. Whole-integration coverage above 95% is a Silver rule; it should not be confused with Bronze's config-flow coverage requirement. Sources: [config-flow coverage](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/config-flow-test-coverage/) and [quality checklist](https://developers.home-assistant.io/docs/core/integration-quality-scale/checklist/).

### 12. Medium: configuration is created before validating the account/service contract

The token exchange validates the OAuth exchange, but [`config_flow.py:39`](custom_components/postnl/config_flow.py#L39) never calls the account or shipment client before saving the entry. Userinfo is fetched only later in entry setup. A token response alone does not establish that the PostNL account has the identifier and API access needed to create the sensors.

Fetch account information during flow completion, validate its stable ID, and report actionable errors before saving. The same request can support duplicate and reauth identity checks. This is a gap in application-level validation; OAuth connectivity is already exercised. Source: Bronze [test-before-configure](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/test-before-configure/).

### 13. Medium: custom integration translations are missing

[`strings.json`](custom_components/postnl/strings.json) contains only an application-credentials description. There is no `translations/en.json`, no text for the custom reauth confirmation step, and no integration-provided OAuth abort translations. Custom integrations distribute language files directly; they cannot rely on the Core translation pipeline to generate them from `strings.json`.

Ship an English translation file and provide strings for the flow steps and abort reasons that are actually used. Entity/exception/icon translations can then be added for Gold compliance. Source: [custom integration localization](https://developers.home-assistant.io/docs/internationalization/custom_integration/).

### 14. Medium: API clients are recreated without an explicit session lifecycle

[`coordinator.py:39`](custom_components/postnl/coordinator.py#L39) recreates both clients every poll. `PostNLJouwAPI` owns a `requests.Session`; `PostNLLoginAPI` also creates one during setup. Neither class exposes cleanup and neither caller explicitly closes those sessions.

Reuse clients where possible, update their authorization safely, and define ownership/cleanup at unload or use bounded contexts for short-lived clients. An async library accepting Home Assistant's managed websession is the preferred long-term design. Async dependencies and injectable sessions are Platinum rules, not universal Bronze requirements. Existing HTTP operations are dispatched through `async_add_executor_job`, so the use of synchronous libraries alone is not evidence of blocking network I/O on the event loop. Sources: [blocking I/O guidance](https://developers.home-assistant.io/docs/asyncio_blocking_operations/) and [quality checklist](https://developers.home-assistant.io/docs/core/integration-quality-scale/checklist/).

### 15. Medium: polling logs duplicate coordinator reporting, and request fan-out is unbounded

[`coordinator.py:58`](custom_components/postnl/coordinator.py#L58) emits INFO on every successful poll. Lines 62 and 145 emit error tracebacks before raising `UpdateFailed`, adding logs beyond the coordinator's own failure/recovery handling. Missing tracking data also generates repeated warnings.

Use debug for routine counts, let the coordinator handle recurring failure/recovery reporting, and reserve additional warnings for actionable conditions. Add `PARALLEL_UPDATES = 0` for the coordinator-driven sensor platform to satisfy the explicit Silver declaration rule. This flag does not limit the `asyncio.gather` fan-out at lines 52 and 56; bound that separately if needed. With N undelivered shipments the current successful cycle normally makes about 2 + N API calls every 90 seconds, before retries. There is no upstream rate-limit evidence in this repository, so 90 seconds cannot be certified as appropriate or declared invalid solely by inspection.

Sources: [log-when-unavailable](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/log-when-unavailable/), [parallel-updates](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/parallel-updates/), and [appropriate-polling](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/appropriate-polling/).

### 16. Medium: nullable data assumptions and inaccurate type annotations obscure failures

[`coordinator.py:120`](custom_components/postnl/coordinator.py#L120) assumes a present `statusPhase` is a dictionary. The mock with a null value crashes. Similar `.get(..., {})` chains do not handle explicitly null `trackedShipments`, shipment arrays, or `colli`. Whether PostNL sends those forms was not established, but the parser is not robust to them.

`userinfo.get('account_id')` is used as a mandatory string in `__init__.py` and `sensor.py` without validation. A missing ID can cause string operations to fail. Validate required fields and normalize optional fields at the API boundary rather than scattering defensive assumptions throughout entity code.

Specific typing problems include `async_setup_entry(...) -> True` (`__init__.py:24`, use `bool`), `_attributes: dict[str, list[Package]]` even though dictionaries from `vars(package)` are appended (`sensor.py:56`), bare `dict`/coordinator/entity generic types, and nullable `.get()` results passed to nonnullable package fields. Of 38 functions/methods, 19 lack return annotations. Strict typing is a Platinum rule; incorrect annotations are still defects worth fixing at any tier. A dataclass is a reasonable optional simplification for `Package`, not a Home Assistant requirement.

## Bronze rule disposition

This records source-review evidence, not an awarded tier. Full rule definitions: [official checklist](https://developers.home-assistant.io/docs/core/integration-quality-scale/checklist/).

| Rule | Assessment |
| --- | --- |
| action-setup | Exempt: no actions. |
| appropriate-polling | Unverified: 90 seconds; rate limits undocumented. |
| brands | Partial: local icon; Core branding unverified. |
| common-modules | Partial: coordinator separated; auth misplaced. |
| config-flow-test-coverage | Fail: no tests. |
| config-flow | Partial: OAuth UI; localization/validation gaps. |
| dependency-transparency | Unverified: no package provenance audit. |
| docs-actions | Exempt: no actions. |
| docs-triggers | Exempt: no custom triggers. |
| docs-conditions | Exempt: no custom conditions. |
| docs-high-level-description | Partial: very brief README. |
| docs-installation-instructions | Present: extension/HACS steps. |
| docs-removal-instructions | Fail: absent. |
| entity-event-setup | Pass by inspection: CoordinatorEntity lifecycle. |
| entity-unique-id | Present: account plus sensor suffix; validation missing. |
| has-entity-name | Fail. |
| runtime-data | Fail. |
| test-before-configure | Partial: OAuth only; account unchecked. |
| test-before-setup | Partial: userinfo/profile; first refresh misplaced. |
| unique-config-entry | Fail. |

For Core admission, also supply a `quality_scale.yaml` recording completed/exempt rules, the required official documentation, and the external client package. Local branding does not establish acceptance in the Core brands repository. README installation instructions are useful, but removal instructions and a clearer description of the resulting sensors are missing. The dependency-transparency rule includes public licensing, distribution, release tags, and build provenance; those were not audited for gql. Sources: [branding](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/brands/), [removal documentation](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/docs-removal-instructions/), and [dependency transparency](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/dependency-transparency/).

## Existing strengths

- Uses config entries and an OAuth helper rather than YAML credential setup.
- Awaits `async_forward_entry_setups` and implements platform unloading.
- Uses one coordinator for both package-count entities, rather than separate polling per entity.
- Runs synchronous service requests through the executor; entity properties read cached data.
- Uses account-derived entity/device identifiers and contains an entity-ID migration attempt.
- Uses TLS verification and specifies a timeout for GraphQL transport.
- Uses lazy logging interpolation, `CoordinatorEntity` callbacks, and platform enums.
- Includes custom manifest version, code owner, cloud-polling classification, issue tracker, hassfest workflow, and HACS validation workflow.

These are positive design choices, but do not establish successful end-to-end behavior. The migration's account-ID validation and collision cases need tests before changing it.

## Higher tiers and optional improvements

Silver remains incomplete: auth recovery and repeated-error logging need work, `PARALLEL_UPDATES` is absent, and there is no automated coverage. Unloading and coordinator-derived availability have an implementation foundation, but need verification.

Gold features such as diagnostics, translated entity/exception/icon strings, richer documentation, and relevant reconfiguration/repair behavior are absent. Discovery and firmware updates may be exempt for this cloud-account integration; their absence is not automatically a defect.

Platinum remains incomplete because dependencies perform synchronous I/O, websessions are not injected, and typing is incomplete. Those are higher-tier goals, not additional mandatory Bronze requirements.

Other review observations: `integration_type: hub` deserves review because the code represents a cloud account/service rather than a gateway. `service` may describe it better; this is a classification recommendation, not a demonstrated schema violation. The browser extension and ignored client-credential fields create a usability/dependency concern that would need evaluation before a Core submission. Hard-coded public OAuth client identifiers are not automatically secrets; the logged bearer token is the concrete secret exposure found here.

## Recommended implementation order

1. Remove credential/personal-payload logging; fix authentication exception classification and the reproduced `.status` crash.
2. Add REST timeouts, status checking, schema validation, and explicit client cleanup.
3. Move coordinator creation/first refresh into entry setup; pass the entry explicitly and adopt typed runtime data.
4. Validate account identity during OAuth completion; reject duplicate accounts and mismatched reauthentication.
5. Convert sensors to `SensorEntity`, adopt entity naming, and ship complete English flow translations.
6. Add config-flow and focused lifecycle/error regression tests; run them against the declared supported Home Assistant versions.
7. Configure and enforce formatter/lint/test checks alongside existing hassfest/HACS validation.
8. If targeting Core, extract and publish the client library, satisfy dependency provenance requirements, complete documentation/branding, and record the Bronze rule assessment.

The first seven steps improve this custom integration directly. The final step addresses the additional distribution and review requirements of inclusion in Home Assistant Core.
