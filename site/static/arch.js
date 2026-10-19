/* Animated architecture of the demo: isometric blocks, SVG, no libraries.
   window.initArch(host) draws into `host` and returns a stop() function. Scenes: overview, act1, act2, act3 (+ auto-play).
   Debug: ?archScene=act2&archT=6.5 renders one frame and stops. All numbers shown are the measured ones (docs/RESULTS.md). */
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const C = { blue: "#0B64DD", dev: "#101C3F", sky: "#45A8FF", teal: "#02BCB7", lteal: "#48EFCF", pink: "#F04E98", yel: "#FEC514", orange: "#FF7A50", ink: "#1C1E23", muted: "#5A6270",
    azure: "#0078D4", red: "#E5484D", g1: "#F4F6FA", g2: "#DDE2EB", g3: "#B9C2D3", g4: "#8E99AD", dark: "#343741" };
  const R3 = 0.866;
  const el = (n, a = {}, p) => { const x = document.createElementNS(NS, n); for (const k in a) x.setAttribute(k, a[k]); if (p) p.appendChild(x); return x; };
  const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
  const sm = (v) => { v = clamp(v); return v * v * (3 - 2 * v); };
  const mod = (a, b) => ((a % b) + b) % b;

  /* ---------------------------------------------------------------- isometric cube */
  function cube(p, cx, cy, a, b, h, f, o = {}) {
    const ux = R3 * a, uy = 0.5 * a, vx = -R3 * b, vy = 0.5 * b;
    const F = [cx + ux + vx, cy + uy + vy], Rr = [cx + ux - vx, cy + uy - vy], B = [cx - ux - vx, cy - uy - vy], L = [cx - ux + vx, cy - uy + vy];
    const up = (q) => [q[0], q[1] - h], pts = (arr) => arr.map((q) => q[0].toFixed(1) + "," + q[1].toFixed(1)).join(" ");
    const g = el("g", {}, p), st = { stroke: o.stroke || "#fff", "stroke-width": o.sw || 1.5, "stroke-linejoin": "round" };
    el("polygon", { points: pts([up(L), up(F), F, L]), fill: f.left, ...st }, g);
    el("polygon", { points: pts([up(F), up(Rr), Rr, F]), fill: f.right, ...st }, g);
    el("polygon", { points: pts([up(B), up(Rr), up(F), up(L)]), fill: f.top, ...st }, g);
    return { g, top: { B: up(B), R: up(Rr), F: up(F), L: up(L) }, base: { B, R: Rr, F, L } };
  }
  const SLAB = { top: "#FFFFFF", left: C.g2, right: C.g3 };

  /* ---------------------------------------------------------------- scene geometry */
  const BL = {
    dom: { cx: 150, cy: 890, a: 46, b: 46, h: 30, f: { top: "#fff", left: C.g3, right: C.g4 }, name: "DOMAIN DATA", d: ["Apex: 15 indices", "9,264 documents"] },
    ing: { cx: 300, cy: 600, a: 46, b: 46, h: 24, f: SLAB, name: ["INGEST &", "TRANSFORM"], d: ["IMPORT SCRIPT", "SEMANTIC_TEXT · JINA V5"] },
    sec: { cx: 560, cy: 600, a: 46, b: 46, h: 48, f: { top: "#fff", left: C.orange, right: C.dark }, name: ["SECURE &", "GOVERN"], d: ["LIFECYCLE FILTER", "DOCUMENT · FIELD SECURITY"] },
    ret: { cx: 820, cy: 600, a: 46, b: 46, h: 32, f: SLAB, name: ["RETRIEVE &", "RANK"], d: ["BM25 + VECTORS", "+ EXACT-ID LEG"] },
    bld: { cx: 1080, cy: 600, a: 46, b: 46, h: 44, f: { top: "#fff", left: C.teal, right: C.dark }, name: ["BUILD & OPERATE", "AGENTS"], d: ["AGENT BUILDER · 2 AGENTS", "CONTEXT ENGINE · TOOL"] },
    obs: { cx: 1340, cy: 600, a: 46, b: 46, h: 66, f: { top: "#fff", left: C.pink, right: C.dark }, name: ["EVALUATE &", "OBSERVE"], d: ["ELASTIC OBSERVABILITY", "TRACES · LOGS · ALERT"] },
    es: { cx: 820, cy: 905, a: 70, b: 70, h: 70, f: { top: "#fff", left: C.blue, right: C.dev }, name: "ELASTICSEARCH", d: ["15 apex_* indices", "BM25 + semantic_text"] },
    agt: { cx: 820, cy: 340, a: 150, b: 48, h: 28, f: SLAB, name: "AGENT LAYER", d: ["demo console", "prompt construction · orchestration"] },
    llm: { cx: 1400, cy: 340, a: 60, b: 60, h: 62, f: { top: "#fff", left: C.azure, right: C.dev }, name: "AZURE OPENAI", d: ["azure-openai-gpt-5-4-mini", "Data Zone EU"] },
  };
  // label: "M" = centred under the block; "L"/"R" = text left/right of a leader line that touches the block
  const LB = {
    agt: { side: "M", x: 820, y: 150 }, llm: { side: "M", x: 1400, y: 150 },
    dom: { side: "M", x: 150, y: 985 }, ing: { side: "M", x: 300, y: 690 }, sec: { side: "M", x: 560, y: 690 },
    ret: { side: "M", x: 820, y: 690 }, bld: { side: "M", x: 1080, y: 690 }, obs: { side: "M", x: 1340, y: 690 },
    es: { side: "R", x: 1010, y: 930, at: [890, 905] },
  };
  const PA = {
    dom_ing: [[180, 860], [275, 640]],
    ing_es: [[335, 630], [540, 790], [745, 890]],
    agt_ret: [[820, 380], [820, 540]],
    ret_es: [[820, 630], [820, 800]],
    agt_bld: [[895, 395], [1080, 545]],
    bld_es: [[1080, 635], [890, 830]],
    agt_sec: [[745, 395], [560, 545]],
    sec_ret: [[605, 625], [775, 625]],
    agt_llm: [[930, 335], [1335, 335]],
    llm_agt: [[1335, 360], [930, 360]],
    llm_obs: [[1405, 420], [1385, 480], [1350, 540]],
    agt_obs: [[930, 395], [1140, 455], [1310, 535]],
    ret_obs: [[845, 575], [1060, 440], [1305, 545]],
  };
  const cat = (...ks) => ks.flatMap((k, i) => (i ? PA[k] : PA[k]));
  PA.dom_es = cat("dom_ing", "ing_es"); PA.agt_es = cat("agt_ret", "ret_es"); PA.es_agt = PA.agt_es.slice().reverse();

  function seg(path) { const s = []; let L = 0; for (let i = 1; i < path.length; i++) { const d = Math.hypot(path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1]); s.push(d); L += d } return { s, L } }
  const SEG = {}; Object.keys(PA).forEach((k) => (SEG[k] = seg(PA[k])));
  function at(name, u, off = 0) {
    const p = PA[name], { s, L } = SEG[name]; let d = clamp(u) * L;
    for (let i = 0; i < s.length; i++) { if (d <= s[i] || i === s.length - 1) { const q = s[i] ? clamp(d / s[i]) : 0, x0 = p[i][0], y0 = p[i][1], x1 = p[i + 1][0], y1 = p[i + 1][1], dx = x1 - x0, dy = y1 - y0, n = Math.hypot(dx, dy) || 1;
        return [x0 + dx * q - (dy / n) * off, y0 + dy * q + (dx / n) * off] } d -= s[i] }
    return p[p.length - 1];
  }

  /* ---------------------------------------------------------------- particle styles */
  const KIND = {
    doc: { f: { top: "#fff", left: C.g3, right: C.g4 }, glow: C.g3 }, frag: { f: { top: "#fff", left: C.teal, right: "#0B7F7B" }, glow: C.lteal },
    vec: { f: { top: "#fff", left: C.sky, right: C.blue }, glow: C.sky }, bm25: { f: { top: "#fff", left: C.yel, right: "#C79A0A" }, glow: C.yel },
    exact: { f: { top: "#fff", left: C.teal, right: "#0B7F7B" }, glow: C.lteal }, prompt: { f: { top: "#fff", left: C.dev, right: "#0A1330" }, glow: C.blue },
    ans: { f: { top: "#fff", left: C.yel, right: "#C79A0A" }, glow: C.yel }, q: { f: { top: "#fff", left: C.yel, right: "#C79A0A" }, glow: C.yel },
    tel: { f: { top: "#fff", left: C.pink, right: "#A8205F" }, glow: C.pink }, tool: { f: { top: "#fff", left: C.dev, right: "#0A1330" }, glow: C.sky },
    fat: { f: { top: "#fff", left: C.red, right: "#8F1D21" }, glow: C.red }, inv: { f: { top: "#fff", left: C.g3, right: C.g4 }, glow: C.g3 },
  };

  /* ---------------------------------------------------------------- scenes: each returns {focus, lines, parts, panel, caption} for time t */
  const SC = {};
  const part = (name, u, kind, s = 20, o = {}) => ({ name, u, kind, s, off: o.off || 0, op: o.op == null ? 1 : o.op, label: o.label });
  const fmt = (n) => Math.round(n).toLocaleString("en-US");

  SC.overview = { L: 12, title: "Overview",
    caption: "Data flows in, the question goes to the agent layer, retrieval finds the context, Azure OpenAI answers, and every call is measured.",
    f(t) {
      const parts = [];
      for (let k = 0; k < 6; k++) { const age = mod(t - 2 * k, 12), u = age / 4.2; if (u <= 1) parts.push(part("dom_es", u, "doc", 20, { op: u > .92 ? 1 - (u - .92) / .08 : 1 })); }
      const T = mod(t, 12);
      if (T < 2.6) parts.push(part("agt_es", T / 2.6, "q", 18)); else if (T < 5) parts.push(part("es_agt", (T - 2.6) / 2.4, "frag", 18, { off: -8 }));
      if (T > 5 && T < 7.4) parts.push(part("agt_llm", (T - 5) / 2.4, "prompt", 22, { off: -2 })); if (T > 7.4 && T < 9.8) parts.push(part("llm_agt", (T - 7.4) / 2.4, "ans", 20));
      for (let k = 0; k < 8; k++) { const age = mod(t - 1.5 * k, 12) / 2.2; if (age <= 1) parts.push(part(k % 2 ? "llm_obs" : "agt_obs", age, "tel", 11)) }
      return { focus: null, lines: ["dom_ing", "ing_es", "agt_ret", "ret_es", "agt_bld", "bld_es", "agt_sec", "sec_ret", "agt_llm", "llm_agt", "llm_obs", "agt_obs", "ret_obs"], parts, panel: null };
    } };

  SC.act1 = { L: 11, title: "Act 1 · wrong context",
    caption: "Same question, three ways to search. The vector can't tell contract 0171 from 0125; keywords and the exact-identifier leg can. Hybrid fuses them.",
    f(t) {
      const T = mod(t, 11), parts = [];
      if (T > .3 && T < 1.6) parts.push(part("agt_ret", (T - .3) / 1.3, "q", 18));
      const pr = [["bm25", -18], ["vec", 0], ["exact", 18]];
      if (T > 1.6 && T < 2.9) pr.forEach(([k, o]) => parts.push(part("ret_es", (T - 1.6) / 1.3, k, 15, { off: o })));
      if (T > 2.9 && T < 4.2) pr.forEach(([k, o]) => parts.push(part("ret_es", 1 - (T - 2.9) / 1.3, k, 15, { off: o })));
      if (T > 5.1 && T < 6.5) parts.push(part("agt_ret", 1 - (T - 5.1) / 1.4, "frag", 20));
      const show = (a) => sm((T - a) / .35) * (T > 10.2 ? clamp(1 - (T - 10.2) / .6) : 1);
      return { focus: ["agt", "ret", "es"], lines: ["agt_ret", "ret_es"], parts, panel: { kind: "rows", title: "Q02 · NOTICE PERIOD OF CONTRACT 0171", rows: [
        { t: "BM25 · keywords", v: "0171", ok: true, a: show(4.3) }, { t: "Semantic · vectors", v: "0125", ok: false, a: show(4.6), note: "scores 0.773 · 0.767 · 0.759" }, { t: "Hybrid · + exact id", v: "0171", ok: true, a: show(4.9) }] } };
    } };

  SC.act2 = { L: 16, title: "Act 2 · too much context",
    caption: "Same question, same model, same data: only the context changes. Then the agents: one rediscovers the data every time, the other asks the prepared index first.",
    f(t) {
      const T = mod(t, 16), parts = [], P = { rows: [] };
      const cnt = (a, b, v) => v * sm((T - a) / (b - a));
      // A1: naive (0-4.6), A2: engineered (4.6-9)
      if (T < 4.6) for (let k = 0; k < 3; k++) { const u = clamp((T - k * .45) / 3.2); if (u > 0 && u < 1) parts.push(part(u < .55 ? "es_agt" : "agt_llm", u < .55 ? u / .55 : (u - .55) / .45, "doc", 34, { off: (k - 1) * 8 })) }
      else if (T < 9) for (let k = 0; k < 6; k++) { const u = clamp((T - 4.6 - k * .22) / 2.8); if (u > 0 && u < 1) parts.push(part(u < .6 ? "es_agt" : "agt_llm", u < .6 ? u / .6 : (u - .6) / .4, "frag", 16, { off: (k % 3 - 1) * 7 })) }
      // B1: baseline agent (9-12.6), B2: context agent (12.6-16)
      if (T >= 9 && T < 12.6) for (let k = 0; k < 9; k++) { const u = mod((T - 9) * 1.5 - k * .5, 4.5); if (u < 1) parts.push(part(k % 2 ? "ret_es" : "agt_ret", k % 3 ? u : 1 - u, "tool", 14, { off: (k % 3 - 1) * 10 })) }
      if (T >= 12.6) { const u = clamp((T - 12.7) / 1.4); if (u > 0 && u < 1) parts.push(part("agt_bld", u, "tool", 20)); const w = clamp((T - 14.1) / 1.4); if (w > 0 && w < 1) parts.push(part("agt_bld", 1 - w, "frag", 18)) }
      const rows = [
        { t: "NAIVE PROMPT", v: fmt(13649 * sm((T - .2) / 3.8)), u: "tokens · €0.011", bar: 1, c: C.g4, a: sm((T - .2) / .4) },
        { t: "ENGINEERED PROMPT", v: fmt(7815 * sm((T - 4.8) / 3.5)), u: "tokens · €0.007 · -43%", bar: 7815 / 13649, c: C.teal, a: sm((T - 4.8) / .4) },
        { t: "BASELINE AGENT", v: fmt(14 * sm((T - 9.2) / 3)), u: "LLM calls · 20 s · 141k tokens", bar: 1, c: C.dev, a: sm((T - 9.2) / .4) },
        { t: "CONTEXT ENGINE AGENT", v: fmt(2 * sm((T - 12.8) / 2.2)), u: "LLM calls · 4 s · 25k tokens", bar: 2 / 14, c: C.teal, a: sm((T - 12.8) / .4) }];
      const phase = T < 9 ? ["agt", "ret", "es", "llm"] : (T < 12.6 ? ["agt", "ret", "es"] : ["agt", "bld", "es"]);
      return { focus: phase, lines: T < 9 ? ["agt_ret", "ret_es", "agt_llm"] : (T < 12.6 ? ["agt_ret", "ret_es"] : ["agt_bld", "bld_es"]), parts, panel: { kind: "bars", title: "WHAT THE MODEL PAYS FOR", rows } };
    } };

  SC.act3 = { L: 14, title: "Act 3 · invisible context",
    caption: "Every call leaves a trace: our traces, Azure logs and metrics, the invoice the next day. A prompt over 10,000 tokens trips the alert before the bill does.",
    f(t) {
      const T = mod(t, 14), parts = [];
      // normal traffic
      for (let k = 0; k < 4; k++) { const u = mod(T - 3.4 * k, 14) / 2.4; if (u > 0 && u < 1 && !(T > 6.5 && T < 9.6)) parts.push(part("agt_llm", u, "prompt", 20, { off: -2 })) }
      for (let k = 0; k < 10; k++) { const u = mod(T - 1.4 * k, 14) / 2.4; if (u < 1) parts.push(part(k % 3 == 0 ? "llm_obs" : (k % 3 == 1 ? "agt_obs" : "ret_obs"), u, "tel", 11)) }
      // fat prompt
      const fu = clamp((T - 6.5) / 2.2); if (fu > 0 && fu < 1) parts.push(part("agt_llm", fu, "fat", 38)); const fo = clamp((T - 8.7) / 2); if (fo > 0 && fo < 1) parts.push(part("llm_obs", fo, "fat", 24));
      // invoice, the next day (slow, dotted)
      const iu = mod(T / 14, 1); parts.push(part("llm_obs", iu, "inv", 12, { off: 18, op: .9 }));
      const alert = T > 10.4 ? sm((T - 10.4) / .4) : 0;
      const lbl = [["Scoreboard · traces", 1.2], ["Azure usage & cost · logs", 3], ["Foundry overview · metrics", 4.8], ["Billing · next day", 6.6], ["Alert · over 10,000 tokens", 10.4]];
      return { focus: ["agt", "llm", "ret", "obs"], lines: ["agt_llm", "llm_obs", "agt_obs", "ret_obs"], parts, alert, panel: { kind: "list", title: "WHAT SHOWS UP IN KIBANA", rows: lbl.map(([t0, a], i) => ({ t: t0, a: sm((T - a) / .4), hot: i === 4 })) } };
    } };
  const ORDER = ["overview", "act1", "act2", "act3"];

  /* ---------------------------------------------------------------- build the page */
  window.initArch = function (host) {
    const q = new URLSearchParams(location.search), freeze = q.get("archT") != null, reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
    host.innerHTML = "";
    const bar = document.createElement("div"); bar.className = "arch-tabs"; host.appendChild(bar);
    const svg = el("svg", { viewBox: "0 90 1600 960", width: "100%", role: "img", "aria-label": "Animated architecture of the demo" }); svg.style.display = "block"; host.appendChild(svg);
    const cap = document.createElement("p"); cap.className = "arch-cap"; host.appendChild(cap);
    const defs = el("defs", {}, svg);
    const gb = el("filter", { id: "ag-blur", x: "-60%", y: "-60%", width: "220%", height: "220%" }, defs); el("feGaussianBlur", { stdDeviation: "6" }, gb);
    const sh = el("filter", { id: "ag-sh", x: "-40%", y: "-40%", width: "180%", height: "200%" }, defs); el("feGaussianBlur", { stdDeviation: "14" }, sh);
    const bg = el("radialGradient", { id: "ag-bg", cx: "50%", cy: "50%", r: "60%" }, defs); el("stop", { offset: "0", "stop-color": "#EAF3FF" }, bg); el("stop", { offset: "1", "stop-color": "#fff" }, bg);
    el("rect", { x: 0, y: 0, width: 1600, height: 1060, fill: "url(#ag-bg)" }, svg);
    // dashed plane like the reference picture
    el("polygon", { points: "820,195 1570,610 820,1000 70,610", fill: "rgba(255,255,255,.6)", stroke: C.g3, "stroke-width": 2, "stroke-dasharray": "7 7" }, svg);
    const lineG = el("g", {}, svg), blockG = {}, labG = {}, labelG = el("g", {}, svg), partG = el("g", {}, svg), overG = el("g", {}, svg);
    // draw blocks back to front
    const order = ["agt", "llm", "ing", "sec", "ret", "bld", "obs", "dom", "es"];
    order.forEach((k) => {
      const b = BL[k], g = el("g", {}, svg); blockG[k] = g;
      el("ellipse", { cx: b.cx, cy: b.cy + b.b * .5, rx: (b.a + b.b) * .9, ry: (b.a + b.b) * .34, fill: C.dev, opacity: ".16", filter: "url(#ag-sh)" }, g);
      const cb = cube(g, b.cx, b.cy, b.a, b.b, b.h, b.f), mid = (p, q, t) => [p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t];
      if (k === "dom") { cube(g, b.cx, b.cy - b.h - 5, b.a, b.b, 8, b.f); cube(g, b.cx, b.cy - b.h - 18, b.a, b.b, 8, b.f); }
      if (k === "ret") [1, 2, 3].forEach((i) => { const t = i / 4, P0 = mid(cb.top.L, cb.top.B, t), P1 = mid(cb.top.F, cb.top.R, t); el("line", { x1: P0[0], y1: P0[1], x2: P1[0], y2: P1[1], stroke: [C.yel, C.sky, C.teal][i - 1], "stroke-width": 5, "stroke-linecap": "round" }, g) });
      if (k === "agt") [-1, 0, 1].forEach((s, i) => { const px = b.cx + s * R3 * b.a * .6, py = b.cy - b.h + s * .5 * b.a * .6; cube(g, px, py, 13, 13, 16, { top: "#fff", left: [C.sky, C.teal, C.blue][i], right: C.dev }) });
      if (k === "es") [1, 2].forEach((i) => { const t = i / 3, P0 = mid(cb.top.L, cb.base.L, t), P1 = mid(cb.top.F, cb.base.F, t); el("line", { x1: P0[0], y1: P0[1], x2: P1[0], y2: P1[1], stroke: "#fff", "stroke-width": 2, opacity: ".55" }, g) });
      if (k === "llm") { const cx0 = (cb.top.L[0] + cb.top.F[0]) / 2, cy0 = (cb.top.L[1] + cb.top.F[1] + cb.base.L[1] + cb.base.F[1]) / 4; el("path", { d: "M0 -22 C2 -8 8 -2 22 0 C8 2 2 8 0 22 C-2 8 -8 2 -22 0 C-8 -2 -2 -8 0 -22 Z", transform: `translate(${cx0.toFixed(1)},${cy0.toFixed(1)}) scale(.8)`, fill: "#fff", opacity: ".95" }, g) }
    });
    // labels (reference style): bold uppercase name + light description; leader line for the outer blocks
    Object.keys(LB).forEach((k) => {
      const l = LB[k], b = BL[k], g = el("g", {}, labelG); labG[k] = g; const anc = l.side === "M" ? "middle" : (l.side === "L" ? "end" : "start");
      if (l.at) { const lead = [l.x + (l.side === "L" ? 12 : -12), l.y - 7]; el("polyline", { points: `${l.at[0]},${l.at[1]} ${lead[0]},${lead[1]}`, fill: "none", stroke: C.ink, "stroke-width": 1.2, opacity: ".55" }, g); el("circle", { cx: l.at[0], cy: l.at[1], r: 3.5, fill: C.ink }, g) }
      const nm = Array.isArray(b.name) ? b.name : [b.name], halo = { "paint-order": "stroke", stroke: "#fff", "stroke-width": 7, "stroke-linejoin": "round" };
      nm.forEach((n, i) => { el("text", { x: l.x, y: l.y + i * 22, "text-anchor": anc, "font-size": 19, "font-weight": 800, fill: C.ink, "letter-spacing": "1", ...halo }, g).textContent = n });
      b.d.forEach((t, i) => { el("text", { x: l.x, y: l.y + nm.length * 22 + 2 + i * 19, "text-anchor": anc, "font-size": 15, fill: C.muted, "letter-spacing": ".6", ...halo }, g).textContent = (typeof t === "string" ? t : "").toUpperCase() });
    });
    // static faint flow lines
    const lines = {};
    Object.keys(PA).forEach((k) => { const pts = PA[k].map((p) => p.join(",")).join(" ");
      lines[k] = { base: el("polyline", { points: pts, fill: "none", stroke: C.g3, "stroke-width": 2.5, "stroke-dasharray": "3 9", "stroke-linecap": "round", opacity: ".7" }, lineG),
        hot: el("polyline", { points: pts, fill: "none", stroke: C.blue, "stroke-width": 3.5, "stroke-dasharray": "10 8", "stroke-linecap": "round", opacity: 0 }, lineG) } });
    // tabs
    let scene = q.get("archScene") || "overview", auto = !freeze && !reduce, t0 = performance.now(), raf = 0, lastT = 0;
    const tabs = {};
    ORDER.forEach((k) => { const b = document.createElement("button"); b.className = "arch-tab"; b.textContent = SC[k].title; b.onclick = () => { auto = false; setScene(k); autoBtn.classList.remove("on") }; bar.appendChild(b); tabs[k] = b });
    const autoBtn = document.createElement("button"); autoBtn.className = "arch-tab arch-auto" + (auto ? " on" : ""); autoBtn.textContent = "▶ Auto"; autoBtn.onclick = () => { auto = !auto; autoBtn.classList.toggle("on", auto); t0 = performance.now() }; bar.appendChild(autoBtn);
    function setScene(k) { scene = k; t0 = performance.now(); ORDER.forEach((s) => tabs[s].classList.toggle("on", s === k)); cap.textContent = SC[k].caption }
    // opacity state per block (smooth dimming)
    const op = {}; Object.keys(BL).forEach((k) => (op[k] = 1));

    function drawPanel(pn) {
      overG.innerHTML = ""; if (!pn) return;
      const x = 24, y = 130, w = 420; const g = el("g", {}, overG);
      const rows = pn.rows, h = 62 + rows.length * (pn.kind === "list" ? 44 : 70);
      el("rect", { x, y, width: w, height: h, rx: 18, fill: "#fff", stroke: C.g2, "stroke-width": 2, filter: "" }, g);
      const tt = el("text", { x: x + 22, y: y + 36, "font-size": 15, "font-weight": 800, fill: C.blue, "letter-spacing": "2" }, g); tt.textContent = pn.title;
      rows.forEach((r, i) => {
        const ry = y + 62 + i * (pn.kind === "list" ? 44 : 70), gg = el("g", { opacity: (r.a == null ? 1 : r.a).toFixed(2) }, g);
        if (pn.kind === "rows") {
          el("text", { x: x + 22, y: ry + 12, "font-size": 20, "font-weight": 700, fill: C.ink }, gg).textContent = r.t;
          el("rect", { x: x + w - 150, y: ry - 12, width: 128, height: 34, rx: 17, fill: r.ok ? "#D7F7F1" : "#FDE1EE" }, gg);
          el("text", { x: x + w - 86, y: ry + 12, "text-anchor": "middle", "font-size": 20, "font-weight": 800, fill: r.ok ? "#0B7F7B" : "#C2185B" }, gg).textContent = (r.ok ? "✓ " : "✗ ") + r.v;
          if (r.note) el("text", { x: x + 22, y: ry + 34, "font-size": 15, fill: C.muted }, gg).textContent = r.note;
        } else if (pn.kind === "bars") {
          el("text", { x: x + 22, y: ry, "font-size": 14, "font-weight": 800, fill: C.muted, "letter-spacing": "1.5" }, gg).textContent = r.t;
          el("text", { x: x + 22, y: ry + 30, "font-size": 28, "font-weight": 800, fill: C.ink }, gg).textContent = r.v;
          el("text", { x: x + 22 + (String(r.v).length * 17) + 10, y: ry + 28, "font-size": 15, fill: C.muted }, gg).textContent = r.u;
          el("rect", { x: x + 22, y: ry + 42, width: w - 44, height: 8, rx: 4, fill: C.g1 }, gg);
          el("rect", { x: x + 22, y: ry + 42, width: Math.max(8, (w - 44) * r.bar * clamp(r.a == null ? 1 : r.a)), height: 8, rx: 4, fill: r.c }, gg);
        } else {
          el("circle", { cx: x + 30, cy: ry - 6, r: 7, fill: r.hot ? C.red : C.pink }, gg);
          el("text", { x: x + 48, y: ry, "font-size": 19, "font-weight": r.hot ? 800 : 600, fill: r.hot ? C.red : C.ink }, gg).textContent = r.t;
        }
      });
    }
    function frame(now) {
      const S = SC[scene]; let t = freeze ? parseFloat(q.get("archT")) : (now - t0) / 1000;
      if (auto && !freeze && t > S.L) { setScene(ORDER[(ORDER.indexOf(scene) + 1) % ORDER.length]); t = 0 }
      const r = S.f(t), dt = Math.min(.1, (now - lastT) / 1000 || .016); lastT = now;
      // blocks: dim the ones outside the focus
      Object.keys(BL).forEach((k) => { const target = (!r.focus || r.focus.includes(k)) ? 1 : .32; op[k] = freeze ? target : op[k] + (target - op[k]) * Math.min(1, dt * 6); blockG[k].setAttribute("opacity", op[k].toFixed(2)); if (labG[k]) labG[k].setAttribute("opacity", Math.max(.35, op[k]).toFixed(2));
        const lift = r.focus && r.focus.includes(k) ? -5 : 0; blockG[k].setAttribute("transform", `translate(0,${lift})`) });
      Object.keys(lines).forEach((k) => { const hot = r.lines.includes(k); lines[k].hot.setAttribute("opacity", hot ? ".9" : "0"); lines[k].hot.setAttribute("stroke-dashoffset", (-t * 60).toFixed(1)); lines[k].base.setAttribute("opacity", r.focus && !hot ? ".25" : ".7") });
      // particles
      partG.innerHTML = "";
      r.parts.forEach((p) => { const [x, y] = at(p.name, p.u, p.off), K = KIND[p.kind], g = el("g", { opacity: p.op }, partG);
        el("circle", { cx: x, cy: y, r: p.s * .9, fill: K.glow, opacity: ".45", filter: "url(#ag-blur)" }, g);
        cube(g, x, y + p.s * .3, p.s * .4, p.s * .4, p.s * .5, K.f, { sw: 1.1 });
        if (p.kind === "q") { const tx = el("text", { x, y: y - p.s * .42 + 1, "text-anchor": "middle", "font-size": p.s * .7, "font-weight": 800, fill: C.ink }, g); tx.textContent = "?" } });
      // alert ring on Observability
      if (r.alert) { const b = BL.obs, g = el("g", {}, partG); const pulse = (Math.sin(t * 8) + 1) / 2;
        el("ellipse", { cx: b.cx, cy: b.cy - b.h * .4, rx: 120 + 18 * pulse, ry: 70 + 10 * pulse, fill: "none", stroke: C.red, "stroke-width": 4, opacity: (.8 * r.alert).toFixed(2) }, g);
        el("rect", { x: b.cx - 195, y: b.cy - b.h - 98, width: 390, height: 44, rx: 22, fill: C.red, opacity: r.alert.toFixed(2) }, g);
        el("text", { x: b.cx, y: b.cy - b.h - 68, "text-anchor": "middle", "font-size": 18, "font-weight": 800, fill: "#fff", opacity: r.alert.toFixed(2) }, g).textContent = "ALERT · PROMPT > 10,000 TOKENS" }
      drawPanel(r.panel);
      if (!freeze && !reduce) raf = requestAnimationFrame(frame);
    }
    setScene(scene); if (freeze || reduce) { frame(performance.now()) } else raf = requestAnimationFrame(frame);
    return function stop() { cancelAnimationFrame(raf) };
  };
})();
