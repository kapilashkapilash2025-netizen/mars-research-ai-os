# Areograph Verifiable Mission Twin

## Purpose and boundary

The Verifiable Mission Twin is a deterministic research simulator. It is not calibrated for
actual rover hardware. Predictions are advisory candidate outcomes, not measured reliability,
flight readiness, safety certification, telemetry, or actuation commands. NASA is identified only
as a source publisher when an evidence record actually cites NASA; no affiliation or endorsement
is claimed.

The versioned API validates inputs; `MissionOrchestrator` obtains intent-only geometry from
`NavigationPlanner`; the existing `PhysicsEngine` evaluates every route and counterfactual; a
transparent utility model ranks candidates; explicit authorization creates a simulated run; and
immutable snapshot/event identities support replay and audit. The browser contains no mission
physics or route-scoring calculations.

## API v1

| Method | Path | Behavior |
| --- | --- | --- |
| `GET` | `/api/v1/mission/health` | Engine connectivity and schema status |
| `POST` | `/api/v1/mission/plans` | Generate three candidates, scenarios, and route ranking |
| `POST` | `/api/v1/mission/predictions` | Return or create predictions |
| `POST` | `/api/v1/mission/runs` | Require explicit human authorization and reviewer identity |
| `POST` | `/api/v1/mission/runs/{id}/step` | Advance one deterministic physics step |
| `POST` | `/api/v1/mission/runs/{id}/commands` | Start, pause, resume, safe hold, abort, emergency stop, or reset |
| `GET` | `/api/v1/mission/runs/{id}` | Current immutable state |
| `GET` | `/api/v1/mission/runs/{id}/events` | Ordered replayable events |
| `GET` | `/api/v1/mission/runs/{id}/report` | Versioned audit JSON with content hash |

Errors are structured as `{ "error": { "code": "...", "message": "..." } }`.

## Determinism and scoring

Canonical JSON and SHA-256 produce stable plan, prediction, run, decision, snapshot, event, input,
and report identities. Wall-clock timestamps and random IDs do not affect scientific results.
Fixed deterministic physics seeds make identical normalized requests produce identical outputs.

The advisory score is `50 + 100 × sum(component × weight)`. Versioned weights are science value
`+0.30`, energy risk `-0.20`, terrain risk `-0.20`, thermal risk `-0.10`, duration risk `-0.10`,
and mobility risk `-0.10`. Responses expose normalized values, weights, contributions, and an
explanation. This is not an opaque AI score or estimated success probability.

## Scenarios, safety, and replay

V1 supports nominal sol, dust storm, single-wheel degradation, reduced battery reserve, and
increased communication delay. All are synthetic engineering stress cases. Nominal output has
medium model confidence; stressed output has low model confidence. These labels describe model
completeness, not statistical accuracy.

Navigation creates intent only. Starting a run requires a reviewer identity and explicit simulated
authorization. Invalid transitions are denied. Pause, safe hold, abort, and emergency stop are
explicit. High simulated slip or low reserve enters safe hold. Recovery advisories are recorded,
but the existing recovery coordinator is not automatically executed in v1.

Every event binds its sequence, prior/next snapshots, command, safety decision, assumptions, model
version, content hash, and authorization status. Replay validates sequence and snapshot continuity
before the audit report is returned.

## Persistence, local development, and deployment

`MemoryMissionRepository` supports isolated tests. `JsonMissionRepository` atomically writes
versioned plan/run JSON and protects deterministic identities. Domain objects remain hydrated in
the current process; restart hydration and migrations are a documented next step.

```powershell
python -m mars_ai_os.mission.api
cd apps/dashboard
npm run dev
```

The local site proxies to `http://127.0.0.1:8788`. A hosted Sites deployment must set
`MISSION_API_ORIGIN` to an HTTPS deployment of the Python service. Sites hosts the frontend Worker,
not Python. Without that setting, Mission Control reports engine offline and never falls back to
browser calculations.

The repository root includes a non-root, Cloud Run-compatible `Dockerfile`. It listens on
`0.0.0.0`, consumes Cloud Run's injected `PORT`, writes ephemeral process data beneath `/tmp`, and
limits the reference deployment to three instances. After installing and authenticating the Google
Cloud CLI, deploy with:

```powershell
.\deploy\cloud-run.ps1 -ProjectId "your-google-cloud-project-id"
```

The returned HTTPS URL is the value required for the Sites `MISSION_API_ORIGIN` runtime setting.
Because `/tmp` is ephemeral and instances may scale independently, production cross-instance
persistence requires the repository's next database-backed adapter.

## Known limitations and next terrain phase

- Route templates use synthetic, single-segment terrain inputs.
- Communication delay does not yet model link budgets or delayed command queues.
- Wheel degradation is a mobility approximation, not a wheel-assembly model.
- JSON persistence does not yet hydrate runs after process restart.
- Reviewer identity is an audit label, not authenticated identity.
- Next, add a versioned evidence adapter for Mars elevation, slope, rock-abundance, and uncertainty
  rasters. Each tile needs publisher, product ID, spatial reference, checksum, processing lineage,
  and source classification before route generation may use it.
