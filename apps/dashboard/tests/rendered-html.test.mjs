import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);

async function render(path = "/mission-control") {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(new Request(`http://localhost${path}`, {headers:{accept:"text/html"}}), {ASSETS:{fetch:async()=>new Response("Not found",{status:404})}}, {waitUntil(){},passThroughOnException(){}});
}

test("server renders the verifiable mission twin shell", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /VERIFIABLE MISSION TWIN/i);
  assert.match(html, /NOT CALIBRATED FOR REAL HARDWARE/i);
  assert.match(html, /HUMAN REVIEW REQUIRED/i);
  assert.match(html, /PYTHON ENGINE/i);
  assert.doesNotMatch(html, /NASA (AFFILIATED|ENDORSED|APPROVED)/i);
});

test("frontend delegates scientific calculations to the versioned API", async () => {
  const [component, api, typography] = await Promise.all([
    readFile(new URL("app/mission-control/mission-control.tsx", root), "utf8"),
    readFile(new URL("app/mission-control/api.ts", root), "utf8"),
    readFile(new URL("app/typography.css", root), "utf8"),
  ]);
  assert.match(component, /missionApi\.createPlan/);
  assert.match(component, /missionApi\.step/);
  assert.match(component, /AUTHORIZATION BOUNDARY/);
  assert.match(api, /\/api\/v1\/mission/);
  assert.doesNotMatch(component, /predictMission|successProbability/);
  assert.match(typography, /prefers-reduced-motion:reduce/);
});

test("worker fails closed when a hosted Python origin is absent", async () => {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("api-test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  const response = await worker.fetch(new Request("https://example.test/api/v1/mission/health"), {ASSETS:{fetch:async()=>new Response("Not found",{status:404})}}, {waitUntil(){},passThroughOnException(){}});
  assert.equal(response.status, 503);
  assert.equal((await response.json()).error.code, "mission_engine_unconfigured");
});
