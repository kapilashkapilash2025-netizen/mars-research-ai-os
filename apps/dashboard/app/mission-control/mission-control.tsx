"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { missionApi, scenarioLabels, type Plan, type Run, type ScenarioId } from "./api";

const targets = [
  {id:"delta",name:"Delta Scarp",code:"JSR-04",science:"Sedimentary layers",distance_m:420},
  {id:"ridge",name:"Crater Ridge",code:"JZR-11",science:"Mineral survey",distance_m:610},
  {id:"floor",name:"Crater Floor",code:"JZR-02",science:"Regolith sample",distance_m:315},
];

export function MissionControl() {
  const [targetId,setTargetId] = useState("delta");
  const [scenario,setScenario] = useState<ScenarioId>("nominal");
  const [plan,setPlan] = useState<Plan|null>(null);
  const [routeId,setRouteId] = useState("");
  const [run,setRun] = useState<Run|null>(null);
  const [reviewer,setReviewer] = useState("");
  const [authorized,setAuthorized] = useState(false);
  const [apiState,setApiState] = useState<"connecting"|"ready"|"offline">("connecting");
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState("");
  const target = targets.find(item=>item.id===targetId) ?? targets[0];

  const createPlan = useCallback(async () => {
    setBusy(true); setError(""); setRun(null); setAuthorized(false);
    try { const next = await missionApi.createPlan(target); setPlan(next); setRouteId(next.recommended_route_id); setApiState("ready"); }
    catch (cause) { setPlan(null); setApiState("offline"); setError(cause instanceof Error ? cause.message : "Mission API unavailable"); }
    finally { setBusy(false); }
  },[target]);

  useEffect(()=>{ missionApi.health().then(()=>setApiState("ready")).catch(()=>setApiState("offline")); },[]);
  useEffect(()=>{
    let active = true;
    missionApi.createPlan(target).then(next=>{
      if (!active) return;
      setPlan(next); setRouteId(next.recommended_route_id); setApiState("ready"); setError("");
    }).catch(cause=>{
      if (!active) return;
      setPlan(null); setApiState("offline"); setError(cause instanceof Error ? cause.message : "Mission API unavailable");
    });
    return ()=>{ active=false; };
  },[target]);

  const routes = plan?.routes ?? [];
  const predictions = useMemo(()=>plan?.predictions.filter(item=>item.scenario_id===scenario).sort((a,b)=>b.score-a.score||a.route_id.localeCompare(b.route_id)) ?? [],[plan,scenario]);
  const selectedPrediction = predictions.find(item=>item.route_id===routeId) ?? predictions[0];
  const snapshot = run?.current_snapshot;
  const status = snapshot?.status ?? (plan ? "planned" : "idle");
  const route = routes.find(item=>item.route_id===routeId);
  const totalDistance = route?.segments.reduce((sum,item)=>sum+item.distance_m,0) ?? target.distance_m;
  const progress = Math.min(100, Math.round((snapshot?.distance_travelled_m ?? 0)/totalDistance*100));

  async function authorizeRun() {
    if (!plan || !routeId || !authorized || !reviewer.trim()) return;
    await act(()=>missionApi.createRun(plan.plan_id,routeId,scenario,reviewer.trim()));
  }
  async function command(value:string) { if(run) await act(()=>missionApi.command(run.run_id,value)); }
  async function step() { if(run) await act(()=>missionApi.step(run.run_id)); }
  async function act(action:()=>Promise<Run>) { setBusy(true);setError("");try{setRun(await action());}catch(cause){setError(cause instanceof Error?cause.message:"Mission action failed");}finally{setBusy(false);} }
  async function exportReport() { if(!run)return; setBusy(true);try{const report=await missionApi.report(run.run_id);const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:"application/json"}));const link=document.createElement("a");link.href=url;link.download=`areograph-${run.run_id}-audit.json`;link.click();URL.revokeObjectURL(url);}catch(cause){setError(cause instanceof Error?cause.message:"Report failed");}finally{setBusy(false);} }

  return <main className="mc-shell">
    <header className="mc-topbar"><Link className="brand" href="/"><span className="brand-mark" aria-hidden="true"><i/></span><span>AREOGRAPH LABS</span></Link><div className="mc-title"><span>VERIFIABLE MISSION TWIN</span><b>JEZERO / RESEARCH SIM</b></div><div className={`api-pill ${apiState}`}><i/>{apiState.toUpperCase()} / PYTHON ENGINE</div></header>
    <div className="mc-warning">DETERMINISTIC RESEARCH SIMULATION / NOT CALIBRATED FOR REAL HARDWARE / HUMAN REVIEW REQUIRED</div>
    {error && <div className="api-error" role="alert"><b>ENGINE NOTICE</b><span>{error}</span><button onClick={()=>void createPlan()}>RETRY CONNECTION</button></div>}

    <section className="twin-layout">
      <aside className="mission-builder">
        <div className="mc-panel-title"><span>01</span><div><small>PLAN INPUT</small><b>Science target</b></div></div>
        <div className="target-list">{targets.map(item=><button key={item.id} className={targetId===item.id?"active":""} disabled={busy||Boolean(run)} onClick={()=>setTargetId(item.id)}><span>{item.code}</span><b>{item.name}</b><small>{item.science}</small><i>{item.distance_m} M</i></button>)}</div>
        <div className="mc-panel-title route-title"><span>02</span><div><small>PYTHON NAVIGATION INTENT</small><b>Candidate routes</b></div></div>
        <div className="route-list">{routes.map((item,index)=><button key={item.route_id} className={routeId===item.route_id?"active":""} disabled={busy||Boolean(run)} onClick={()=>setRouteId(item.route_id)}><header><b>{item.name}</b><span>0{index+1}</span></header><div><span>SCIENCE <b>{item.science_value}</b></span><span>SLOPE <b>{item.segments[0].slope_deg}°</b></span><span>DIST <b>{Math.round(item.segments[0].distance_m)}m</b></span></div></button>)}</div>
      </aside>

      <section className="twin-core">
        <header className="core-header"><div><small>IMMUTABLE SNAPSHOT</small><b>{snapshot?.snapshot_id ?? "AWAITING AUTHORIZED RUN"}</b></div><span className={`run-state ${status}`}>{status.toUpperCase()}</span></header>
        <div className="terrain-stage"><div className="terrain-grid"/><div className="route-vector"><i style={{width:`${progress}%`}}/></div><div className="rover-node" style={{left:`${12+progress*.75}%`}}><i/><span>ARES-SIM<br/><b>{Math.round(snapshot?.distance_travelled_m??0)} M</b></span></div><div className="target-node"><i/><span>{target.code}<b>{target.name}</b></span></div><div className="terrain-label l1">SYNTHETIC TERRAIN</div><div className="terrain-label l2">NAVIGATION INTENT ONLY</div></div>
        <div className="state-strip"><div><small>PROGRESS</small><b>{progress}%</b></div><div><small>BATTERY RESERVE</small><b>{snapshot?.battery_reserve_percent ?? selectedPrediction?.battery_reserve_percent ?? "—"}%</b></div><div><small>PEAK SLIP</small><b>{snapshot?.peak_wheel_slip ?? selectedPrediction?.peak_wheel_slip ?? "—"}</b></div><div><small>PEAK THERMAL</small><b>{snapshot?.peak_temperature_c ?? selectedPrediction?.peak_temperature_c ?? "—"}°C</b></div><div><small>MODEL TIME</small><b>{snapshot?.elapsed_s ?? 0} S</b></div></div>
        <div className="mission-actions"><button onClick={()=>void command(status==="paused"||status==="safe_hold"?"resume":"start")} disabled={busy||!run||!["authorized","paused","safe_hold"].includes(status)}>START / RESUME</button><button onClick={()=>void step()} disabled={busy||status!=="running"}>ADVANCE ONE STEP</button><button onClick={()=>void command("pause")} disabled={busy||status!=="running"}>PAUSE</button><button onClick={()=>void command("safe_hold")} disabled={busy||!["running","paused"].includes(status)}>SAFE HOLD</button><button className="abort" onClick={()=>void command("abort")} disabled={busy||!run||["aborted","completed"].includes(status)}>ABORT</button></div>
      </section>

      <aside className="review-rail">
        <div className="mc-panel-title"><span>03</span><div><small>AUTHORIZATION BOUNDARY</small><b>Human review</b></div></div>
        {!run?<div className="auth-card"><label>REVIEWER IDENTITY<input value={reviewer} onChange={event=>setReviewer(event.target.value)} placeholder="research-operator"/></label><label className="check"><input type="checkbox" checked={authorized} onChange={event=>setAuthorized(event.target.checked)}/><span>I authorize this deterministic simulated run. No physical actuation is permitted.</span></label><button onClick={()=>void authorizeRun()} disabled={busy||!plan||!routeId||!authorized||!reviewer.trim()}>CREATE AUTHORIZED RUN</button></div>:<div className="auth-record"><small>AUTHORIZATION RECORDED</small><b>{run.authorization_status.toUpperCase()}</b><span>Run {run.run_id}</span></div>}
        <div className="mc-panel-title log-title"><span>04</span><div><small>REPLAYABLE EVENT STREAM</small><b>Mission audit</b></div></div>
        <div className="event-log">{(run?.events??[]).slice().reverse().map(event=><div key={event.event_id}><time>#{String(event.sequence).padStart(3,"0")}</time><b>{event.command.toUpperCase()}</b><p>{event.event_type.replaceAll("_"," ")} · {event.safety_decision.allowed?"approved":"held"}</p></div>)}{!run&&<p className="empty-log">Events appear only after explicit authorization.</p>}</div>
        <button className="report-button full" onClick={()=>void exportReport()} disabled={!run||busy}>DOWNLOAD VERSIONED AUDIT JSON</button>
      </aside>
    </section>

    <section className="future-lab">
      <header className="future-head"><div><span>05</span><div><small>COUNTERFACTUAL PYTHON ENGINE</small><h2>Explainable Route Intelligence</h2></div></div><div className="scenario-switch">{(Object.keys(scenarioLabels) as ScenarioId[]).map(id=><button className={scenario===id?"active":""} key={id} disabled={Boolean(run)} onClick={()=>setScenario(id)}>{scenarioLabels[id]}</button>)}</div></header>
      {selectedPrediction&&<><div className="future-summary"><div><small>SELECTED CANDIDATE</small><h3>{routes.find(item=>item.route_id===selectedPrediction.route_id)?.name}</h3><p>{selectedPrediction.completion_status.replaceAll("_"," ")} · {selectedPrediction.confidence_classification} model confidence</p></div><div className="future-score"><span>{selectedPrediction.score}</span><small>ADVISORY<br/>UTILITY</small></div><div className="assumption"><b>CLASSIFICATION: {selectedPrediction.source_classification.toUpperCase()}</b><span>{selectedPrediction.model_version} · input {selectedPrediction.input_hash.slice(0,16)}…</span></div></div>
      <div className="prediction-grid">{predictions.map((prediction,index)=><article className={`prediction-card ${prediction.route_id===routeId?"recommended":""}`} key={prediction.prediction_id} onClick={()=>!run&&setRouteId(prediction.route_id)}><header><span>RANK 0{index+1}</span><b>{prediction.route_id===plan?.recommended_route_id?"PLAN RECOMMENDATION":"CANDIDATE"}</b></header><h3>{routes.find(item=>item.route_id===prediction.route_id)?.name}</h3><div className="metric-pair"><div><small>BATTERY</small><b>{prediction.battery_reserve_percent}%</b></div><div><small>DURATION</small><b>{Math.round(prediction.estimated_duration_s/60)}m</b></div><div><small>SLIP</small><b>{prediction.peak_wheel_slip}</b></div><div><small>ENERGY</small><b>{prediction.estimated_energy_use_wh}Wh</b></div></div><div className="score-breakdown">{prediction.score_components.map(item=><div key={item.name}><span>{item.name.replaceAll("_"," ")}</span><b>{item.normalized_value.toFixed(2)} × {item.weight.toFixed(2)}</b><i className={item.contribution>=0?"positive":""} style={{width:`${Math.min(100,Math.abs(item.contribution)*330)}%`}}/></div>)}</div></article>)}</div>
      <div className="evidence-panels"><article><b>ASSUMPTIONS</b>{selectedPrediction.assumptions.map(item=><p key={item.assumption_id}><span>{item.source_classification}</span>{item.text}</p>)}</article><article><b>LIMITATIONS</b>{selectedPrediction.limitations.map(item=><p key={item}>{item}</p>)}</article></div></>}
      <footer className="future-disclaimer"><b>ADVISORY / INFORMATION ONLY</b><span>All outcomes are deterministic candidate simulations. They are not real telemetry, measured reliability, flight readiness, or safety certification. NASA affiliation or endorsement is not claimed.</span></footer>
    </section>
  </main>;
}
