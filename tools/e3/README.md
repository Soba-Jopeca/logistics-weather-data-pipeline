# P09-E3 isolated harness — preparation, not E3 authorization

Baseline: `70b02b044e36adaa0a29612da87cf8bf688567c9`.
Only these 13 new files are in scope. Operational scripts, DAG, Compose, contracts,
previous tests and historical records must remain byte-for-byte unchanged.
Pinned text-source hashes normalize CRLF to LF so a Windows checkout with
`core.autocrlf` preserves the approved baseline identity.

## Current status

Implementation under review. Offline validation remains **BLOCKED**, not approved.
C02 restored CPython 3.10.14 from the signed official source and compiled it in a
temporary prefix. Missing local Linux SQLite/libffi development headers prevented
building _sqlite3 and _ctypes, so Airflow 2.9.2 still cannot import. No new dependencies
were downloaded/installed. See document 27 (C02 update) for provenance and tracebacks.
The prior 315 passed / 14 failed / 8 errors are historical, not a new C02 regression.
Do not run this Compose, CLI runner, DAG or controller against operational services.

## Entry points

- `preflight`: read-only validation of pinned baseline hashes, campaign roots and
  externally collected isolation evidence. Default command verifies and exits;
  it never starts a scheduler or initializes a database.
- `ledger`: exclusive finite reservations. A busy/interrupted lock is blocked,
  never stolen. A successful reservation remains consumed after failure.
- `runtime`: dependency wrappers, finite phase clocks, original persistence,
  synthetic `requests.Response`/timeout, no real HTTP fallback.
- `dag_loader`: loads original DAG, wraps original Python callables, checks graph,
  retries/timeouts and provides a serializable timetable plugin for two slots.
- `cli_runner`: calls original `main` only after gates, B08 reservation and runtime
  context. Not invoked during P03.
- `controller`: injected trigger adapter, conservative containment, run-to-plan
  binding and generated runtime source strings. No implicit Docker/subprocess
  operations, schema initialization or metadata mutations.

## Future preparation gates (not executed)

1. Use a separate read-only baseline checkout; verify all pinned hashes.
2. Choose disjoint campaign root; inventory operational mounts/history separately.
3. Identify actual image digests, UID, Docker networks and Windows ACL/firewall.
4. Prepare campaign JSON, exact scenario plans and externally reviewed evidence.
   `campaign.example.json` is deliberately disabled; enabling it is not authorization.
5. Prepare scenario directories, identical `config/locations.json` snapshots,
   runtime DAG/plugin sources from `runtime_sources`, logs/tmp and metadata directory.
6. Secrets are campaign-only files, never operational `.env` and never Git.
7. Approve initialization of the new metadata schema separately. No command in
   this package automatically runs `airflow db migrate`.
8. Prove network and mount isolation BEFORE allowing task execution. Docker
   internal networking and Python guards are separate layers, not proof by assertion.
9. Only with explicit A/B authorization connect reviewed trigger adapter to the
   isolated Airflow. Keep operational DAG paused with schedule=None/retries=0.
10. C additionally requires two consecutive approved real dates, both run-budget
    reservations before scheduler start, plugin registration/serialization checked
    in real Airflow, explicit isolated timetable activation and monitoring.

## Campaign and evidence

Campaign: schema_version, campaign_id, baseline, enabled, root, code_root, hashes,
scenarios, slots, authorization. `hashes` must exactly match embedded baseline pins.
A JSON Schema is supplied; runtime also performs checks without an extra dependency.

Isolation evidence must bind `campaign_sha256` and confirm external_network_blocked,
operational_mounts_absent, exclusive_metadata, write_confinement, shared_root_verified.
Scenario plans are bound by `scenario_plan_sha256[scenario]`.
Windows additionally requires `windows_acl_and_firewall_verified`.
These are attestations from observed external controls, NOT cryptographic authorization
or a self-proving OS sandbox. Do not manufacture positive values to pass preflight.

A plan contains cycle_date, clocks and optional faults. Phase scripts: prepare
(admission), execute (dispatch and first transport), batch (batch timestamp),
city:<location_id> (city collection time), reconcile (assessment-started, assessed,
readiness observation, confirmation and evaluation). Every list is finite; extra
clock reads fail. Historical technical timestamps in weather_interface remain real
and must be labeled accordingly; global datetime/Airflow clocks are never patched.
Faults: locations mapping to none/null/corrupt/timeout; after_publish matching a
specific original persistence reference, e.g. claim.json or readiness.json.

## Budget and isolation limits

B01..B10: (runs, transports) = (2,5),(1,5),(1,7),(1,5),(1,0),(2,0),
(1,0),(1,5),(1,0),(2,5). C01=(1,5), C02=(1,0). One CLI only in B08.
Totals: 15 DAG runs, 37 simulated attempts. A has zero DAG runs.
Unit tests use disposable ledgers, not the future campaign budget.

Roots are scenario-specific. A shared-content witness proves visibility only;
block A is required for cross-platform atomicity. Python open/socket guards are
secondary defenses and do not confine arbitrary native syscalls or administrators.
Mounts/ACLs must enforce confinement. Windows is not claimed as verified here.
The controller cannot prevent manual out-of-protocol Airflow operations by an admin.
Do not expose a separate run producer. Freeze prevents new ledger operations, not
already running processes: reviewed PID-specific containment remains necessary.

## Rollback

Freeze campaign; stop only identified campaign producers/processes after authorization.
Preserve ledger, pending files, locks, database and artifacts. No automatic refunds,
clear, claim deletion, down, prune or volume cleanup. Never alter operational data
as compensation. This branch is additive; main remains untouched.

The metadata container is also opt-in: profile operational-approved plus a reviewed
`metadata-start.sha256` checksum gate. `metadata_gate_contents` requires explicit
metadata_initialization_authorized evidence and returns text only. Absence or hash
mismatch stops before the original PostgreSQL entrypoint. This gate does not replace
inspection of actual mounts/network and must never be created from invented evidence.
The Compose project name has fixed prefix p09-e3-, never logistics-weather.
