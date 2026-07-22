"""Deterministic orchestration over navigation intent and Mars physics prediction."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from mars_ai_os.mars_physics.engine import PhysicsEngine
from mars_ai_os.mars_physics.models import (
    MarsEnvironment,
    PhysicsState,
    SimulationIntent,
    Terrain,
    VehicleParameters,
)
from mars_ai_os.mission.contracts import (
    MODEL_VERSION,
    SCHEMA_VERSION,
    EnvironmentScenario,
    EvidenceReference,
    MissionEvent,
    MissionPlan,
    MissionRun,
    PredictedOutcome,
    PredictionAssumption,
    RouteCandidate,
    RoverStateSnapshot,
    SafetyDecision,
    ScoreComponent,
    TerrainSegment,
    content_hash,
    content_id,
    jsonable,
)
from mars_ai_os.mission.repository import MemoryMissionRepository, MissionRepository
from mars_ai_os.navigation import NavigationPlanner, Waypoint, WorldModel

LIMITATIONS = (
    "Deterministic research simulation; not calibrated for actual rover hardware.",
    "Terrain and environmental inputs are synthetic unless an evidence reference says otherwise.",
    "Candidate outcomes are advisory and are not measured real-world reliability.",
    "No command produced by this service has physical actuation authority.",
)
BASE_ASSUMPTIONS = (
    PredictionAssumption(
        "assumption_eight_wheel", "Reference vehicle uses an eight-wheel synthetic configuration."
    ),
    PredictionAssumption(
        "assumption_constant_segment", "Terrain properties are constant within each route segment."
    ),
    PredictionAssumption(
        "assumption_review",
        "A human reviewer remains responsible for simulated execution authorization.",
    ),
)
SCENARIOS = {
    "nominal": EnvironmentScenario("nominal", "Nominal sol", 0.10, 1.0, 1.0, 742.0, ()),
    "dust-storm": EnvironmentScenario(
        "dust-storm",
        "Dust storm",
        0.82,
        0.88,
        1.0,
        910.0,
        (PredictionAssumption("dust_model", "Dust opacity is a bounded synthetic stress case."),),
    ),
    "wheel-degradation": EnvironmentScenario(
        "wheel-degradation",
        "Single-wheel degradation",
        0.15,
        0.72,
        1.0,
        742.0,
        (
            PredictionAssumption(
                "wheel_model",
                "One degraded wheel is approximated through reduced mobility efficiency.",
            ),
        ),
    ),
    "low-battery": EnvironmentScenario(
        "low-battery",
        "Reduced battery reserve",
        0.10,
        1.0,
        0.58,
        742.0,
        (
            PredictionAssumption(
                "battery_model",
                "Initial stored energy is reduced to 58 percent of the reference state.",
            ),
        ),
    ),
    "communication-delay": EnvironmentScenario(
        "communication-delay",
        "Increased communication delay",
        0.15,
        0.95,
        1.0,
        1320.0,
        (
            PredictionAssumption(
                "comms_model", "Delay affects review risk but does not model a radio link budget."
            ),
        ),
    ),
}
SCORE_WEIGHTS = {
    "science_value": 0.30,
    "energy_risk": -0.20,
    "terrain_risk": -0.20,
    "thermal_risk": -0.10,
    "duration_risk": -0.10,
    "mobility_risk": -0.10,
}


class MissionOrchestrator:
    def __init__(self, repository: MissionRepository | None = None) -> None:
        self.repository = repository or MemoryMissionRepository()
        self.physics = PhysicsEngine()
        self.vehicle = VehicleParameters()

    def create_plan(self, request: dict[str, Any]) -> MissionPlan:
        normalized = self._normalize_request(request)
        request_hash = content_hash(normalized)
        routes = self._routes(normalized)
        scenario_ids = tuple(normalized["scenario_ids"])
        predictions = tuple(
            self._predict(route, SCENARIOS[sid], normalized)
            for route in routes
            for sid in scenario_ids
        )
        nominal = [item for item in predictions if item.scenario_id == scenario_ids[0]]
        ranked = sorted(nominal, key=lambda item: (-item.score, item.route_id))
        plan = MissionPlan(
            SCHEMA_VERSION,
            content_id("plan", normalized),
            request_hash,
            normalized["mission_name"],
            normalized["target"],
            tuple(normalized["start_position_m"]),
            routes,
            predictions,
            ranked[0].route_id,
            tuple(
                f"{item.route_id}: advisory utility {item.score:.2f}; transparent component sum."
                for item in ranked
            ),
            BASE_ASSUMPTIONS,
            LIMITATIONS,
            (
                EvidenceReference(
                    "ref_model",
                    "Areograph deterministic Mars physics model",
                    "synthetic",
                    "Areograph Labs",
                    "mars-physics/1.0",
                    "Engineering approximation; no flight calibration.",
                ),
            ),
            "review_required",
        )
        self.repository.save_plan(plan)
        return plan

    def predictions(self, request: dict[str, Any]) -> tuple[PredictedOutcome, ...]:
        if "plan_id" in request:
            return self.repository.load_plan(str(request["plan_id"])).predictions
        return self.create_plan(request).predictions

    def create_run(self, request: dict[str, Any]) -> MissionRun:
        plan = self.repository.load_plan(str(request.get("plan_id", "")))
        route_id = str(request.get("selected_route_id", ""))
        scenario_id = str(request.get("scenario_id", "nominal"))
        reviewer = str(request.get("authorized_by", "")).strip()
        authorized = request.get("human_authorized") is True and bool(reviewer)
        if not authorized:
            raise PermissionError("explicit human authorization and reviewer identity are required")
        if (
            route_id not in {route.route_id for route in plan.routes}
            or scenario_id not in SCENARIOS
        ):
            raise ValueError("unknown route or scenario")
        base = self._snapshot(
            "authorized", 0, 0.0, 4000.0 * SCENARIOS[scenario_id].battery_factor, 0, 20, 0
        )
        run_seed = {
            "plan_id": plan.plan_id,
            "route_id": route_id,
            "scenario_id": scenario_id,
            "reviewer": reviewer,
        }
        run = MissionRun(
            content_id("run", run_seed),
            plan,
            route_id,
            scenario_id,
            reviewer,
            "authorized",
            base,
            base,
        )
        self._record(
            run,
            "run_authorized",
            "authorize",
            base,
            base,
            True,
            ("Explicit simulated authorization recorded.",),
        )
        self.repository.save_run(run)
        return run

    def command(self, run_id: str, command: str) -> MissionRun:
        run = self.repository.load_run(run_id)
        command = command.lower().replace(" ", "_")
        current = run.current_snapshot
        transitions = {
            "start": ({"authorized", "paused", "safe_hold"}, "running"),
            "resume": ({"paused", "safe_hold"}, "running"),
            "pause": ({"running"}, "paused"),
            "safe_hold": ({"running", "paused"}, "safe_hold"),
            "abort": ({"authorized", "running", "paused", "safe_hold"}, "aborted"),
            "emergency_stop": ({"authorized", "running", "paused", "safe_hold"}, "aborted"),
            "reset": ({"completed", "aborted"}, "authorized"),
        }
        if command not in transitions or current.status not in transitions[command][0]:
            raise ValueError(f"invalid transition: {current.status} -> {command}")
        status = transitions[command][1]
        if command == "reset":
            after = replace(run.initial_snapshot, status=status)
        else:
            after = self._snapshot(
                status,
                current.sequence + 1,
                current.distance_travelled_m,
                current.battery_energy_wh,
                current.peak_wheel_slip,
                current.peak_temperature_c,
                current.elapsed_s,
            )
        self._record(run, f"mission_{status}", command, current, after, True, ())
        run.current_snapshot = after
        self.repository.save_run(run)
        return run

    def step(self, run_id: str) -> MissionRun:
        run = self.repository.load_run(run_id)
        before = run.current_snapshot
        if before.status != "running":
            raise ValueError("mission must be running before it can advance")
        route = next(item for item in run.plan.routes if item.route_id == run.selected_route_id)
        scenario = SCENARIOS[run.scenario_id]
        remaining = (
            sum(segment.distance_m for segment in route.segments) - before.distance_travelled_m
        )
        timestep = 30.0
        terrain_segment = route.segments[min(before.sequence, len(route.segments) - 1)]
        state = PhysicsState(
            before.elapsed_s,
            before.position_m,
            before.velocity_mps,
            before.velocity_mps / self.vehicle.wheel_radius_m,
            before.battery_energy_wh,
            before.peak_temperature_c,
            25,
            20,
            35,
            True,
        )
        terrain = Terrain(
            slope_deg=terrain_segment.slope_deg,
            roughness=terrain_segment.roughness,
            traction_coefficient=terrain_segment.traction_coefficient,
        )
        result = self.physics.step(
            state,
            SimulationIntent(0.4 * scenario.wheel_efficiency, 0.03),
            MarsEnvironment(dust_opacity=scenario.dust_opacity),
            terrain,
            self.vehicle,
            timestep_s=timestep,
            seed=before.sequence + 11,
        )
        travelled = min(
            remaining, max(0.1, result.predicted_state.position_m[0] - state.position_m[0])
        )
        total = before.distance_travelled_m + travelled
        completed = total >= sum(segment.distance_m for segment in route.segments) - 1e-6
        unsafe = result.slip_ratio >= 0.6 or result.predicted_state.battery_energy_wh <= 500
        status = "safe_hold" if unsafe else "completed" if completed else "running"
        after = self._snapshot(
            status,
            before.sequence + 1,
            total,
            result.predicted_state.battery_energy_wh,
            max(before.peak_wheel_slip, result.slip_ratio),
            max(before.peak_temperature_c, result.thermal.motor_c),
            before.elapsed_s + timestep,
        )
        reasons = tuple(result.warnings) or (
            "Physics step remained within simulated review bounds.",
        )
        self._record(run, "simulation_step", "step", before, after, not unsafe, reasons)
        run.current_snapshot = after
        self.repository.save_run(run)
        return run

    def replay(self, run_id: str) -> RoverStateSnapshot:
        run = self.repository.load_run(run_id)
        expected = run.initial_snapshot.snapshot_id
        for index, event in enumerate(run.events, 1):
            if event.sequence != index or event.previous_snapshot_id != expected:
                raise ValueError("event stream integrity failure")
            expected = event.new_snapshot_id
        if expected != run.current_snapshot.snapshot_id:
            raise ValueError("replay does not match current snapshot")
        return run.current_snapshot

    def report(self, run_id: str) -> dict[str, Any]:
        run = self.repository.load_run(run_id)
        self.replay(run_id)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "model_version": MODEL_VERSION,
            "mission_plan": jsonable(run.plan),
            "selected_route_id": run.selected_route_id,
            "scenario_id": run.scenario_id,
            "authorization": {"status": run.authorization_status, "reviewer": run.authorized_by},
            "initial_snapshot": jsonable(run.initial_snapshot),
            "current_snapshot": jsonable(run.current_snapshot),
            "events": jsonable(run.events),
            "assumptions": [item.text for item in run.plan.assumptions],
            "limitations": list(run.plan.limitations),
            "provenance": jsonable(run.plan.provenance),
        }
        payload["report_content_hash"] = content_hash(payload)
        return payload

    def _predict(
        self, route: RouteCandidate, scenario: EnvironmentScenario, normalized: dict[str, Any]
    ) -> PredictedOutcome:
        energy = 0.0
        duration = 0.0
        slip = 0.0
        temperature = 20.0
        risks: list[str] = []
        interventions: list[str] = []
        state = PhysicsState(
            0,
            tuple(normalized["start_position_m"]),
            0,
            0,
            4000 * scenario.battery_factor,
            20,
            25,
            20,
            35,
            True,
        )
        for index, segment in enumerate(route.segments):
            terrain = Terrain(
                slope_deg=segment.slope_deg,
                roughness=segment.roughness,
                traction_coefficient=segment.traction_coefficient,
            )
            speed = 0.4 * scenario.wheel_efficiency
            steps = max(1, round(segment.distance_m / speed / 60))
            for step in range(steps):
                result = self.physics.step(
                    state,
                    SimulationIntent(speed, 0.03),
                    MarsEnvironment(dust_opacity=scenario.dust_opacity),
                    terrain,
                    self.vehicle,
                    timestep_s=60,
                    seed=index * 1000 + step,
                )
                state = result.predicted_state
                energy += max(0, -result.energy.net_battery_change_wh)
                duration += 60
                slip = max(slip, result.slip_ratio)
                temperature = max(temperature, result.thermal.motor_c)
                risks.extend(result.warnings)
        if slip >= 0.6:
            interventions.append("safe-hold advisory: high simulated wheel slip")
        if state.battery_energy_wh <= 500:
            interventions.append("safe-hold advisory: reserve threshold")
        energy_risk = min(1.0, energy / 1200)
        terrain_risk = min(
            1.0, max(s.roughness + abs(s.slope_deg) / 45 for s in route.segments) / 2
        )
        thermal_risk = min(1.0, max(0, temperature - 45) / 55)
        duration_risk = min(1.0, duration / 7200)
        mobility_risk = min(1.0, slip)
        science = min(1.0, route.science_value / 100)
        values = {
            "science_value": science,
            "energy_risk": energy_risk,
            "terrain_risk": terrain_risk,
            "thermal_risk": thermal_risk,
            "duration_risk": duration_risk,
            "mobility_risk": mobility_risk,
        }
        components = tuple(
            ScoreComponent(
                name,
                round(values[name], 4),
                weight,
                round(values[name] * weight, 4),
                f"{name.replace('_', ' ')} × versioned weight {weight:+.2f}",
            )
            for name, weight in SCORE_WEIGHTS.items()
        )
        score = round(50 + sum(item.contribution for item in components) * 100, 2)
        pred_input = {
            "route": jsonable(route),
            "scenario": jsonable(scenario),
            "initial": normalized["initial_rover_state"],
            "weights": SCORE_WEIGHTS,
        }
        confidence = "medium" if scenario.scenario_id == "nominal" else "low"
        return PredictedOutcome(
            content_id("prediction", pred_input),
            route.route_id,
            scenario.scenario_id,
            "review_required" if interventions else "candidate_complete",
            duration,
            round(energy, 3),
            round(state.battery_energy_wh / self.vehicle.battery_capacity_wh * 100, 2),
            round(slip, 4),
            round(temperature, 2),
            tuple(interventions),
            (),
            tuple(sorted(set(risks))),
            score,
            components,
            confidence,
            BASE_ASSUMPTIONS + scenario.assumptions,
            LIMITATIONS,
            "simulated",
            MODEL_VERSION,
            content_hash(pred_input),
        )

    def _routes(self, request: dict[str, Any]) -> tuple[RouteCandidate, ...]:
        start = Waypoint("start", request["start_position_m"][0], request["start_position_m"][1])
        target = request["target"]
        goal = Waypoint(target["id"], target["x_m"], target["y_m"])
        planner = NavigationPlanner(
            WorldModel("synthetic-terrain/1", (start, goal), confidence=0.72)
        )
        intent = planner.plan(request["mission_name"], start, target["id"], 0)
        if intent is None:
            raise ValueError("navigation layer rejected target")
        distance = intent.estimated_distance_m
        templates = (
            ("safe", "Ridge-safe", "risk-minimizing", 1.12, 8, 0.18, 0.72, 72),
            ("balanced", "Science-optimal", "science-balanced", 1.0, 14, 0.30, 0.58, 92),
            ("fast", "Direct traverse", "time-minimizing", 0.86, 20, 0.48, 0.42, 62),
        )
        return tuple(
            RouteCandidate(
                route_id,
                name,
                strategy,
                (
                    TerrainSegment(
                        f"{route_id}-segment-1",
                        round(distance * factor, 3),
                        slope,
                        roughness,
                        traction,
                        science,
                    ),
                ),
                science,
            )
            for route_id, name, strategy, factor, slope, roughness, traction, science in templates
        )

    def _normalize_request(self, request: dict[str, Any]) -> dict[str, Any]:
        target = request.get("target") or {}
        target_id = str(target.get("id", "delta")).strip()
        distance = float(target.get("distance_m", 420))
        if not target_id or distance <= 0:
            raise ValueError("target id and positive distance are required")
        requested_scenarios = set(
            request.get("scenario_ids") or ("nominal", "dust-storm", "wheel-degradation")
        )
        scenario_ids = tuple(item for item in SCENARIOS if item in requested_scenarios)
        if not scenario_ids or any(item not in SCENARIOS for item in scenario_ids):
            raise ValueError("unsupported scenario")
        return {
            "mission_name": str(request.get("mission_name", "Jezero research traverse")).strip(),
            "target": {
                "id": target_id,
                "name": str(target.get("name", "Delta Scarp")),
                "distance_m": distance,
                "x_m": float(target.get("x_m", distance)),
                "y_m": float(target.get("y_m", 0)),
            },
            "start_position_m": tuple(
                float(item) for item in request.get("start_position_m", (0, 0, 0))
            ),
            "route_strategy": str(request.get("route_strategy", "compare")),
            "initial_rover_state": {
                "battery_energy_wh": float(
                    (request.get("initial_rover_state") or {}).get("battery_energy_wh", 4000)
                )
            },
            "constraints": request.get("constraints") or {},
            "scenario_ids": scenario_ids,
        }

    def _snapshot(
        self,
        status: str,
        sequence: int,
        distance: float,
        battery: float,
        slip: float,
        temperature: float,
        elapsed: float,
    ) -> RoverStateSnapshot:
        values = {
            "sequence": sequence,
            "status": status,
            "distance": round(distance, 6),
            "battery": round(battery, 6),
            "slip": round(slip, 6),
            "temperature": round(temperature, 6),
            "elapsed": round(elapsed, 6),
        }
        return RoverStateSnapshot(
            content_id("snapshot", values),
            sequence,
            status,
            (round(distance, 6), 0, 0),
            round(distance, 6),
            round(battery, 6),
            round(battery / 5000 * 100, 2),
            0.4 if status == "running" else 0,
            round(slip, 4),
            round(temperature, 2),
            round(elapsed, 3),
        )

    def _record(
        self,
        run: MissionRun,
        event_type: str,
        command: str,
        before: RoverStateSnapshot,
        after: RoverStateSnapshot,
        allowed: bool,
        reasons: tuple[str, ...],
    ) -> None:
        seq = len(run.events) + 1
        decision_seed = {
            "run": run.run_id,
            "sequence": seq,
            "command": command,
            "allowed": allowed,
            "reasons": reasons,
        }
        decision = SafetyDecision(
            content_id("decision", decision_seed),
            allowed,
            "approve simulated transition" if allowed else "safe hold",
            reasons,
            True,
        )
        event_seed = {
            "run": run.run_id,
            "sequence": seq,
            "before": before.snapshot_id,
            "after": after.snapshot_id,
            "command": command,
            "decision": decision.decision_id,
        }
        run.events.append(
            MissionEvent(
                content_id("event", event_seed),
                run.run_id,
                seq,
                event_type,
                before.snapshot_id,
                after.snapshot_id,
                command,
                decision,
                tuple(item.text for item in run.plan.assumptions),
                MODEL_VERSION,
                content_hash(event_seed),
                run.authorization_status,
            )
        )
