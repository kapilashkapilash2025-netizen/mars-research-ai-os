export type ScenarioId = "nominal" | "dust-storm" | "wheel-degradation" | "low-battery" | "communication-delay";

export type ScoreComponent = { name:string; normalized_value:number; weight:number; contribution:number; explanation:string };
export type Prediction = {
  prediction_id:string; route_id:string; scenario_id:ScenarioId; completion_status:string;
  estimated_duration_s:number; estimated_energy_use_wh:number; battery_reserve_percent:number;
  peak_wheel_slip:number; peak_temperature_c:number; safety_interventions:string[];
  recovery_events:string[]; key_risk_factors:string[]; score:number; score_components:ScoreComponent[];
  confidence_classification:string; assumptions:{assumption_id:string;text:string;source_classification:string}[];
  limitations:string[]; source_classification:string; model_version:string; input_hash:string;
};
export type Route = { route_id:string; name:string; strategy:string; science_value:number; segments:{distance_m:number;slope_deg:number;roughness:number}[] };
export type Plan = { plan_id:string; schema_version:string; target:{id:string;name:string;distance_m:number}; routes:Route[]; predictions:Prediction[]; recommended_route_id:string; ranking_explanation:string[]; assumptions:{text:string}[]; limitations:string[] };
export type Snapshot = { snapshot_id:string; sequence:number; status:string; distance_travelled_m:number; battery_reserve_percent:number; velocity_mps:number; peak_wheel_slip:number; peak_temperature_c:number; elapsed_s:number };
export type MissionEvent = { event_id:string; sequence:number; event_type:string; command:string; previous_snapshot_id:string|null; new_snapshot_id:string; human_authorization_status:string; safety_decision:{allowed:boolean;reasons:string[]} };
export type Run = { run_id:string; selected_route_id:string; scenario_id:ScenarioId; authorization_status:string; current_snapshot:Snapshot; events:MissionEvent[] };

async function request<T>(path:string, init?:RequestInit):Promise<T> {
  const response = await fetch(`/api/v1/mission${path}`, { ...init, headers:{"content-type":"application/json", ...(init?.headers ?? {})} });
  const body = await response.json() as T & {error?:{message:string}};
  if (!response.ok) throw new Error(body.error?.message ?? `Mission API returned ${response.status}`);
  return body;
}

export const missionApi = {
  health: () => request<{status:string}>("/health"),
  createPlan: (target:{id:string;name:string;distance_m:number}) => request<Plan>("/plans", {method:"POST", body:JSON.stringify({mission_name:"Jezero verification traverse",target,scenario_ids:["nominal","dust-storm","wheel-degradation","low-battery","communication-delay"]})}),
  createRun: (plan_id:string, selected_route_id:string, scenario_id:ScenarioId, authorized_by:string) => request<Run>("/runs", {method:"POST",body:JSON.stringify({plan_id,selected_route_id,scenario_id,human_authorized:true,authorized_by})}),
  command: (runId:string, command:string) => request<Run>(`/runs/${runId}/commands`, {method:"POST",body:JSON.stringify({command})}),
  step: (runId:string) => request<Run>(`/runs/${runId}/step`, {method:"POST",body:"{}"}),
  report: (runId:string) => request<Record<string,unknown>>(`/runs/${runId}/report`),
};

export const scenarioLabels:Record<ScenarioId,string> = {nominal:"Nominal sol","dust-storm":"Dust storm","wheel-degradation":"Wheel degradation","low-battery":"Low battery","communication-delay":"Comms delay"};
