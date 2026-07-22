"""Dependency-free versioned HTTP API for the verifiable mission twin."""

from __future__ import annotations

import json
import os
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from mars_ai_os.mission.contracts import jsonable
from mars_ai_os.mission.orchestrator import MissionOrchestrator
from mars_ai_os.mission.repository import JsonMissionRepository

RUN_ROUTE = re.compile(r"^/api/v1/mission/runs/([^/]+)(?:/(step|commands|events|report))?$")


class MissionApi:
    def __init__(self, orchestrator: MissionOrchestrator) -> None:
        self.orchestrator = orchestrator

    def dispatch(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> tuple[int, object]:
        body = body or {}
        try:
            if method == "GET" and path == "/api/v1/mission/health":
                return 200, {
                    "status": "ready",
                    "service": "areograph-mission-api",
                    "schema_version": "areograph.mission.v1",
                }
            if method == "POST" and path == "/api/v1/mission/plans":
                return 201, jsonable(self.orchestrator.create_plan(body))
            if method == "POST" and path == "/api/v1/mission/predictions":
                return 200, {"predictions": jsonable(self.orchestrator.predictions(body))}
            if method == "POST" and path == "/api/v1/mission/runs":
                return 201, jsonable(self.orchestrator.create_run(body))
            match = RUN_ROUTE.match(path)
            if match:
                run_id, action = match.groups()
                if method == "GET" and action is None:
                    return 200, jsonable(self.orchestrator.repository.load_run(run_id))
                if method == "POST" and action == "step":
                    return 200, jsonable(self.orchestrator.step(run_id))
                if method == "POST" and action == "commands":
                    return 200, jsonable(
                        self.orchestrator.command(run_id, str(body.get("command", "")))
                    )
                if method == "GET" and action == "events":
                    return 200, {
                        "events": jsonable(self.orchestrator.repository.load_run(run_id).events)
                    }
                if method == "GET" and action == "report":
                    return 200, self.orchestrator.report(run_id)
            return 404, {"error": {"code": "not_found", "message": "Mission API route not found."}}
        except PermissionError as error:
            return 403, {"error": {"code": "authorization_required", "message": str(error)}}
        except KeyError:
            return 404, {
                "error": {
                    "code": "mission_not_found",
                    "message": "Mission plan or run was not found.",
                }
            }
        except (TypeError, ValueError) as error:
            return 422, {"error": {"code": "validation_error", "message": str(error)}}


def handler_factory(api: MissionApi) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_OPTIONS(self) -> None:
            self.send_response(HTTPStatus.NO_CONTENT)
            self._headers()
            self.end_headers()

        def do_GET(self) -> None:
            self._respond(*api.dispatch("GET", self.path.split("?", 1)[0]))

        def do_POST(self) -> None:
            try:
                length = int(self.headers.get("content-length", "0"))
                body = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError("JSON body must be an object")
            except (json.JSONDecodeError, ValueError) as error:
                self._respond(400, {"error": {"code": "invalid_json", "message": str(error)}})
                return
            self._respond(*api.dispatch("POST", self.path.split("?", 1)[0], body))

        def _headers(self) -> None:
            self.send_header(
                "access-control-allow-origin",
                os.getenv("AREOGRAPH_ALLOWED_ORIGIN", "http://localhost:3000"),
            )
            self.send_header("access-control-allow-headers", "content-type")
            self.send_header("access-control-allow-methods", "GET, POST, OPTIONS")
            self.send_header("cache-control", "no-store")

        def _respond(self, status: int, value: object) -> None:
            payload = json.dumps(value, sort_keys=True).encode()
            self.send_response(status)
            self._headers()
            self.send_header("content-type", "application/json; charset=utf-8")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            return

    return Handler


def serve(
    host: str = "127.0.0.1", port: int = 8788, data_directory: str | Path = ".areograph-missions"
) -> None:
    repository = JsonMissionRepository(data_directory)
    server = ThreadingHTTPServer(
        (host, port), handler_factory(MissionApi(MissionOrchestrator(repository)))
    )
    print(f"Areograph Mission API listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    serve(
        host=os.getenv("AREOGRAPH_API_HOST", "0.0.0.0"),
        port=int(os.getenv("AREOGRAPH_API_PORT", os.getenv("PORT", "8788"))),
        data_directory=os.getenv("AREOGRAPH_DATA_DIR", ".areograph-missions"),
    )
