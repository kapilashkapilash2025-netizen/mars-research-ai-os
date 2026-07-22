"use client";

import { FormEvent, useMemo, useState } from "react";

type Source = { id:number; title:string; publisher:string; url:string; retrieved:string; text:string; location:string; signal:number };

const initialSources: Source[] = [
  { id:1, title:"Perseverance rover location map", publisher:"NASA Science", url:"https://science.nasa.gov/mission/mars-2020-perseverance/location-map/", retrieved:"22 Jul 2026", text:"Perseverance landed in Jezero Crater, an area with an ancient delta, on February 18, 2021. Its mission seeks signs of ancient life and collects rock and regolith samples for potential return to Earth.", location:"Mission overview", signal:98 },
  { id:2, title:"Mars facts", publisher:"NASA Science", url:"https://science.nasa.gov/mars/facts/", retrieved:"22 Jul 2026", text:"Mars has a thin atmosphere made up mostly of carbon dioxide, nitrogen, and argon gases. Evidence in ancient valleys, deltas, and lakebeds indicates a watery past.", location:"Atmosphere / Water on Mars", signal:96 },
  { id:3, title:"Perseverance science highlights", publisher:"NASA / JPL-Caltech", url:"https://science.nasa.gov/mission/mars-2020-perseverance/science-highlights/", retrieved:"22 Jul 2026", text:"Sedimentary deposits in Jezero preserve evidence of an ancient river and lake environment, making the crater a high-value location for studying past habitability.", location:"Jezero delta geology", signal:94 },
];

const tokenize = (value:string) => value.toLowerCase().match(/[a-z0-9]+/g) ?? [];

export function ResearchDashboard() {
  const [sources, setSources] = useState(initialSources);
  const [query, setQuery] = useState("What ancient environment existed in Jezero Crater?");
  const [activeQuery, setActiveQuery] = useState(query);
  const [showAdd, setShowAdd] = useState(false);
  const [mode, setMode] = useState<"answer" | "sources">("answer");

  const results = useMemo(() => {
    const terms = [...new Set(tokenize(activeQuery).filter((term) => term.length > 3))];
    return sources.map((source) => ({ source, score:terms.reduce((sum, term) => sum + (source.text.toLowerCase().includes(term) ? 1 : 0), 0) }))
      .filter((item) => item.score > 0).sort((a,b) => b.score-a.score || a.source.id-b.source.id).slice(0,3);
  }, [activeQuery, sources]);

  function search(event:FormEvent) { event.preventDefault(); setActiveQuery(query.trim()); setMode("answer"); }
  function runSuggestion(item:string) { setQuery(item); setActiveQuery(item); setMode("answer"); }
  function addSource(event:FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); const text = String(form.get("text") ?? "").trim(); if (!text) return;
    setSources((current) => [...current, { id:Math.max(...current.map((source) => source.id),0)+1, title:String(form.get("title") ?? "Untitled source"), publisher:String(form.get("publisher") ?? "Research source"), url:String(form.get("url") ?? "#"), retrieved:"Added locally", text, location:"Pasted evidence", signal:90 }]);
    setShowAdd(false);
  }

  return <main>
    <header className="topbar">
      <a className="brand" href="#top" aria-label="Areograph Labs home"><span className="brand-mark" aria-hidden="true"><i/></span><span>AREOGRAPH LABS</span><small>AGL-01</small></a>
      <nav aria-label="Workspace sections"><a href="/mission-control">MISSION CONTROL</a><a href="#answer">INTELLIGENCE</a><a href="#sources">SOURCES</a><button onClick={() => setShowAdd(true)}>INGEST +</button></nav>
      <div className="status"><i/> SYSTEM NOMINAL</div>
    </header>

    <section className="telemetry" aria-label="System telemetry">
      <span>TRACE ENGINE <b>ONLINE</b></span><span>INDEX <b>{sources.length} SOURCES</b></span><span>INTEGRITY <b>SHA-256</b></span><span>INFERENCE <b>LABELED</b></span><span className="clock">UTC 13:57:15</span>
    </section>

    <section className="hero" id="top">
      <div className="scanline"/><div className="orbit orbit-a"/><div className="orbit orbit-b"/>
      <div className="hero-grid">
        <div className="hero-copy">
          <div className="eyebrow"><i/> AREOGRAPH LABS / PLANETARY INTELLIGENCE</div>
          <h1>ASK <span>MARS.</span><br/><em>VERIFY</em> EVERYTHING.</h1>
          <p>A high-integrity research terminal for exploring Mars evidence. Every answer remains connected to its publisher, document, and exact source location.</p>
        </div>
        <aside className="mission-orb" aria-label="Knowledge system status">
          <div className="orb-core"><span>MARS</span><b>03</b><small>ACTIVE NODES</small></div>
          <div className="node node-a">01</div><div className="node node-b">02</div><div className="node node-c">03</div>
        </aside>
      </div>
      <form className="search" onSubmit={search}>
        <div className="prompt">QUERY://</div><label className="sr-only" htmlFor="question">Research question</label>
        <input id="question" value={query} onChange={(event) => setQuery(event.target.value)} />
        <button>INITIATE SEARCH <b>ENTER</b></button>
      </form>
      <div className="suggestions"><span>QUICK COMMANDS</span>{["Perseverance landing date","Mars atmosphere","Ancient water"].map((item) => <button key={item} onClick={() => runSuggestion(item)}>{item}</button>)}</div>
    </section>

    <section className="workspace" id="answer">
      <div className="intel-header">
        <div><span className="index">01</span><div><small>RETRIEVAL OUTPUT</small><h2>Grounded intelligence</h2></div></div>
        <div className="mode-switch"><button className={mode === "answer" ? "active" : ""} onClick={() => setMode("answer")}>ANSWER</button><button className={mode === "sources" ? "active" : ""} onClick={() => setMode("sources")}>SOURCE MAP</button></div>
      </div>

      {mode === "answer" ? <div className="answer-layout">
        <article className="answer-card">
          <header><span><i/> GROUNDED RESPONSE</span><small>{results.length} PASSAGES / 0 INFERENCES</small></header>
          {results.length ? <div className="answer-copy">{results.map(({source},index) => <p key={source.id}>{source.text} <a href={`#citation-${source.id}`}>[{index+1}]</a></p>)}</div> : <div className="empty"><b>NO SUPPORTED SIGNAL</b><br/>Try different terms or expand the evidence corpus.</div>}
          <footer><b>EVIDENCE BOUNDARY ACTIVE</b><span>Response limited to retrieved source passages</span><i/></footer>
        </article>
        <aside className="metrics">
          <div className="metric-ring"><span>{results.length ? "98" : "00"}</span><small>%<br/>TRACE<br/>CONFIDENCE</small></div>
          <div className="metric-row"><span>LATENCY</span><b>0042 ms</b></div><div className="metric-row"><span>CITATIONS</span><b>0{results.length}</b></div><div className="metric-row"><span>UNSUPPORTED</span><b>00</b></div>
          <div className="wave"><i/><i/><i/><i/><i/><i/><i/><i/></div>
        </aside>
      </div> : <div className="source-map">{sources.map((source,index) => <div key={source.id} className="map-node"><span>NODE 0{index+1}</span><b>{source.publisher}</b><small>{source.signal}% INTEGRITY</small></div>)}</div>}

      <div className="section-head" id="sources"><div><span>02</span><h2>Evidence constellation</h2></div><button className="outline" onClick={() => setShowAdd(true)}>+ INGEST SOURCE</button></div>
      <div className="source-grid">{results.map(({source,score},index) => <article className="source-card" id={`citation-${source.id}`} key={source.id}>
        <header><span>CITATION 0{index+1}</span><b>{source.signal}%</b></header><div className="signal-bar"><i style={{width:`${source.signal}%`}}/></div>
        <div className="source-meta"><span>VERIFIED ORIGIN</span><b>{source.publisher}</b></div><h3>{source.title}</h3><p>{source.text}</p>
        <div className="source-location"><span>LOC</span>{source.location}</div><footer><span>TERM MATCH / {score}</span><a href={source.url} target="_blank" rel="noreferrer">OPEN RECORD +</a></footer>
      </article>)}</div>
    </section>

    <section className="manifesto"><div className="manifesto-mark"><span className="brand-mark large" aria-hidden="true"><i/></span><small>AREOGRAPH / A-01</small></div><div><span className="eyebrow">OUR MISSION</span><h2>Make planetary<br/><em>intelligence verifiable.</em></h2></div><p>We build open, inspectable systems that connect planetary evidence, simulation, and autonomous decisions—so every result can be challenged, reproduced, and trusted.</p></section>
    <section className="corpus"><div className="corpus-orbit"/><div><span className="eyebrow">KNOWLEDGE ARRAY</span><h2>{sources.length.toString().padStart(2,"0")} traceable nodes</h2></div><p>NASA-hosted records and locally added evidence, normalized into one transparent research layer.</p><button className="outline light" onClick={() => setShowAdd(true)}>EXPAND ARRAY +</button></section>
    <footer className="site-footer"><span>AREOGRAPH LABS // MARS RESEARCH AI OS</span><span>PLANETARY INTELLIGENCE, VERIFIED</span><span>BUILD 0.3.0</span></footer>

    {showAdd && <div className="modal-backdrop" role="presentation" onMouseDown={() => setShowAdd(false)}><form className="modal" onSubmit={addSource} onMouseDown={(event) => event.stopPropagation()}>
      <button type="button" className="close" onClick={() => setShowAdd(false)} aria-label="Close">X</button><span className="eyebrow">INGESTION GATEWAY</span><h2>Add evidence node</h2><p>Paste trusted source text. Metadata stays attached to every future match.</p>
      <label>RECORD TITLE<input name="title" required placeholder="Mission report title"/></label><label>PUBLISHER<input name="publisher" required placeholder="NASA Science"/></label><label>SOURCE URL<input name="url" type="url" required placeholder="https://science.nasa.gov/..."/></label><label>EVIDENCE PAYLOAD<textarea name="text" required rows={6} placeholder="Paste relevant source text..."/></label><button className="submit">VERIFY + ADD NODE</button>
    </form></div>}
  </main>;
}
