/* Demo console: vanilla JS, no build step. All text from the API is inserted with textContent (never innerHTML). */
const $ = (s, r = document) => r.querySelector(s);
function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) e.setAttribute(k, v);
  }
  for (const kid of kids.flat(Infinity)) { if (kid == null || kid === false) continue; e.append(kid.nodeType ? kid : document.createTextNode(String(kid))); }
  return e;
}
const fmt = (n) => (n == null ? "–" : Number(n).toLocaleString("en-US"));
const eur = (n) => (n == null ? "–" : "€" + Number(n).toFixed(4));
const secs = (ms) => (ms == null ? "–" : (ms / 1000).toFixed(1) + " s");
const put = (el, ...kids) => el.replaceChildren(...kids.flat(Infinity).filter((k) => k != null && k !== false));
const state = { under: false, mode: "live", cfg: null, sel: null, agents: {}, timer: null, health: null };

async function api(path, body) {
  const r = await fetch(path, { method: body ? "POST" : "GET", headers: { "content-type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
  if (!r.ok) { let m; try { m = (await r.json()).detail; } catch { m = r.statusText; } throw new Error(m); }
  return r.json();
}

/* ---------------------------------------------------------------- steps */
const ACTS = [
  { n: 1, title: "Wrong context", sub: "The vector can't tell 0117 from 0171. A stale policy version still ranks second.", items: [
    { id: "Q02", kind: "retrieve", label: "Contract 0117 vs 0171", say: "Identifiers are facts, not similarities." },
    { id: "Q03", kind: "retrieve", label: "Two policy versions", say: "A stale version still ranks second. Relevant is not the same as valid: a RAG that mixes the two versions says 'no action needed'." },
    { id: "Q04", kind: "retrieve", label: "Veltran vs Veltrano", say: "Names are not meaning: the right document is first, but the neighbours are other companies." },
    { id: "Q01", kind: "retrieve", label: "Q01 · right for the wrong reason", minor: true, say: "Semantic search finds 0117 by meaning only." },
    { id: "Q05", kind: "retrieve", label: "Q05 · German part code (control)", minor: true, say: "A control: every mode gets it right." } ] },
  { n: 2, title: "Too much context", sub: "Whole contracts in the prompt, and agents that rediscover everything.", items: [
    { id: "HERO", kind: "answer", llm: "naive", label: "Naive RAG on the HERO question", say: "Three whole contracts, a confident answer, and no hidden group." },
    { id: "Q06", kind: "compare", label: "Compare: long contracts (Q06)", say: "Same model, same data. Only the context changes." },
    { id: "clause", kind: "clause", label: "Wrong context lab: ask for any contract", say: "Ask for any contract: naive RAG keeps returning the same three documents." },
    { id: "Q07", kind: "compare", label: "Compare Q07", minor: true },
    { id: "Q08", kind: "compare", label: "Compare Q08", minor: true },
    { id: "agents-HERO", kind: "agents", q: "HERO", label: "Agents: baseline vs Context Engine", say: "Same tools and instructions. One has the AI index." },
    { id: "agents-Q09", kind: "agents", q: "Q09", label: "Agents · Q09 same group", minor: true },
    { id: "agents-Q10", kind: "agents", q: "Q10", label: "Agents · Q10 spend share", minor: true } ] },
  { n: 3, title: "Invisible context", sub: "Cost, time and correctness, visible.", items: [
    { id: "scoreboard", kind: "scoreboard", label: "The scoreboard", say: "Every number was measured, not copied from a slide." },
    { id: "links", kind: "links", label: "Dashboards and the alert", say: "Where each number lives." } ] },
];
const ITEMS = ACTS.flatMap((a) => a.items.map((i) => ({ ...i, act: a })));
const MODE_LABEL = { bm25: "BM25 · keywords", semantic: "Semantic · meaning only", hybrid: "Hybrid · + exact identifiers" };
const AGENT_LABEL = { "apex-analyst-baseline": "Baseline agent", "apex-analyst-context": "Context Engine agent" };

/* ---------------------------------------------------------------- chrome */
function setMode(m) {
  state.mode = m;
  $("#modeLive").classList.toggle("on", m === "live"); $("#modePractice").classList.toggle("on", m === "practice");
  const p = $("#modePill"); p.textContent = m === "live" ? "LIVE" : "PRACTICE · RECORDED, NOT NEW MEASUREMENTS"; p.className = "pill " + m;
}
function metaLine(d) {
  const m = d._meta || {};
  return m.mode === "practice" ? h("p", { class: "badge warn" }, "PRACTICE · recorded " + m.recorded_at + " · not a new measurement")
    : h("p", { class: "badge ok" }, "LIVE · " + (m.seconds != null ? m.seconds + " s" : "now"));
}
function loading(text) { put($("#stage"), h("div", { class: "loading" }, h("div", { class: "spin" }), text)); }
function errorBox(e, retry) {
  put($("#stage"), h("div", { class: "err" }, h("b", {}, "That did not work: "), e.message,
    h("div", { class: "row", style: "margin-top:10px" }, h("button", { class: "btn", onclick: retry }, "Try again"),
      state.mode === "live" ? h("button", { class: "btn primary", onclick: () => { setMode("practice"); retry(); } }, "Use the recorded run") : null)));
}
function setRight(m) {
  const r = $("#right"); if (!r) return;
  put(r, 
    h("div", { class: "eyebrow" }, "Check the answer"), h("h3", {}, m.title || "What happened?"),
    ...(m.bullets || []).length ? [h("ul", {}, m.bullets.map((b) => h("li", {}, b)))] : [],
    m.why ? h("div", { class: "sec" }, h("h4", {}, "Why it matters"), h("p", {}, m.why)) : null,
    (m.sources || []).length ? h("div", { class: "sec" }, h("h4", {}, "Documents"), m.sources.map((s) => h("div", { class: "mono" }, s))) : null,
    m.expected ? h("div", { class: "sec" }, h("h4", {}, "Expected answer"), h("p", {}, m.expected)) : null,
    m.details ? h("details", { class: "sec" }, h("summary", {}, "Technical details"), h("pre", {}, JSON.stringify(m.details, null, 1))) : null);
}
function tile(label, value) { return h("div", { class: "tile" }, h("b", {}, value), h("span", {}, label)); }

/* ---------------------------------------------------------------- pages */
function home() {
  put($("#app"), 
    h("section", { class: "hero" }, h("div", { class: "eyebrow" }, "AI Dev Night with Microsoft and Elastic · Köln"),
      h("h1", {}, "RAG is broken. ", h("em", {}, "Here is how Elastic and Azure fix it.")),
      h("p", {}, "Wrong context, too much context, invisible context. One question about third-party risk, answered three ways, with every token, euro and second measured."),
      h("div", { class: "row", style: "margin-top:26px" }, h("a", { class: "btn primary", href: "#/demo" }, "Start the demo"), h("a", { class: "btn", href: "#/how" }, "How it works"), h("a", { class: "btn", href: "#/status" }, "Service status")),
      h("div", { class: "stats" }, [["15", "indices"], ["9,264", "documents"], ["3", "acts"], ["1", "scoreboard"]].map(([b, s]) => h("div", { class: "stat" }, h("b", {}, b), h("span", {}, s))))),
    h("div", { class: "acts3" }, ACTS.map((a) => h("div", { class: "actcard" }, h("div", { class: "n" }, a.n), h("h3", {}, "Act " + a.n + " · " + a.title), h("p", {}, a.sub),
      h("a", { class: "btn", href: "#/demo", onclick: () => { state.sel = a.items[0].id; } }, "Open act " + a.n)))));
}

async function demo() {
  if (!state.cfg) state.cfg = await api("/api/config");
  put($("#app"), h("div", { class: "demo" },
    h("aside", { class: "panel side" }, h("div", { class: "eyebrow", style: "margin-bottom:10px" }, "Choose an act"),
      ACTS.map((a) => h("div", { class: "act" }, h("h4", {}, "Act " + a.n + " · " + a.title), h("p", {}, a.sub),
        a.items.map((i) => h("button", { class: "item" + (i.minor ? " minor" : ""), "data-id": i.id, onclick: () => select(i.id) }, i.label)))),
      h("p", {}, h("small", {}, h("span", { class: "kbd" }, "←"), " ", h("span", { class: "kbd" }, "→"), " next step · ", h("span", { class: "kbd" }, "R"), " run again · ", h("span", { class: "kbd" }, "M"), " live/practice · ", h("span", { class: "kbd" }, "D"), " queries"))),
    h("section", { class: "panel stage", id: "stage" }),
    h("aside", { class: "panel tint right", id: "right" })));
  const q = new URLSearchParams((location.hash.split("?")[1] || "")); if (q.get("mode") === "practice") setMode("practice"); if (q.get("run")) state.sel = q.get("run"); if (q.get("under")) state.under = true;
  if (state.sel) select(state.sel); else {
    put($("#stage"), h("div", { class: "eyebrow" }, "Start here"), h("h2", {}, "Three acts, one question"),
      h("div", { class: "qline" }, state.cfg.hero.question), h("button", { class: "btn primary", onclick: () => select("Q02") }, "Start with act 1"));
    setRight({ title: "What happened?", bullets: ["Pick a step on the left.", "Live runs the real thing; Practice shows the last recorded run."] });
  }
}

function select(id) {
  state.sel = id; const it = ITEMS.find((i) => i.id === id);
  document.querySelectorAll(".item").forEach((b) => b.classList.toggle("on", b.dataset.id === id));
  run(it);
}
function step(delta) { const i = ITEMS.findIndex((x) => x.id === state.sel); const n = ITEMS.filter((x) => !x.minor); const cur = n.findIndex((x) => x.id === state.sel);
  const next = n[(Math.max(cur, 0) + delta + n.length) % n.length]; if (location.hash === "#/demo" && next) select(next.id); }

async function run(it) {
  clearInterval(state.timer); const retry = () => run(it);
  if (it.kind === "agents") return renderAgents(it);
  if (it.kind === "clause") return renderClause(it);
  loading(it.kind === "compare" ? "Running naive and engineered prompts…" : it.kind === "answer" ? "Sending three whole contracts to the model…" : it.kind === "scoreboard" ? "Reading the scoreboard from Observability…" : "Running…");
  try {
    if (it.kind === "retrieve") renderRetrieve(it, await api("/api/retrieve", { q: it.id, mode: state.mode }));
    else if (it.kind === "answer") renderAnswer(it, await api("/api/answer", { q: it.id, llm: it.llm, mode: state.mode }));
    else if (it.kind === "compare") renderCompare(it, await api("/api/compare", { q: it.id, mode: state.mode }));
    else if (it.kind === "scoreboard") renderScoreboard(it, await api("/api/scoreboard", { mode: state.mode }));
    else if (it.kind === "links") renderLinks(it, await api("/api/links"));
  } catch (e) { errorBox(e, retry); }
}
const head = (it) => [h("div", { class: "eyebrow" }, "Act " + it.act.n + " · " + it.act.title), h("h2", {}, it.label)];

function codeBlock(text, label, full) {
  const btn = h("button", { class: "copy", onclick: async () => { try { await navigator.clipboard.writeText(full || text); } catch { const r = document.createRange(); r.selectNodeContents(pre); getSelection().removeAllRanges(); getSelection().addRange(r); document.execCommand("copy"); } btn.textContent = "Copied ✓"; setTimeout(() => (btn.textContent = "Copy"), 1500); } }, "Copy");
  const pre = h("pre", {}, text);
  return h("div", { class: "code" }, h("div", { class: "codehead" }, h("span", {}, label || "Dev Tools"), btn), pre);
}
function underHood(rows) {
  if (!rows[0] || !rows[0].request) return null;
  const lab = (t, x) => h("p", { class: "how" }, h("b", {}, t + " "), x);
  const one = (r) => h("div", { class: "uh" }, h("h4", {}, MODE_LABEL[r.mode], h("span", { class: "badge " + (r.hit ? "ok" : "bad"), style: "margin-left:10px" }, r.hit ? "✓ right" : "✗ wrong")),
    r.behavior ? lab("How this query behaves.", r.behavior) : lab("How it works.", r.how),
    r.why ? h("p", { class: "how why " + (r.hit ? "good" : "bad") }, r.why) : h("p", { class: "how" }, h("b", {}, r.outcome)),
    r.weak ? lab("Where it usually fails.", r.weak) : null, codeBlock(r.request, "Kibana Dev Tools · paste and run"));
  return h("details", { class: "under", open: state.under ? "" : null }, h("summary", {}, "Under the hood: the queries behind these results (D)"), h("div", { class: "uhgrid" }, rows.map(one)));
}
const slim = (d) => JSON.parse(JSON.stringify(d, (k, v) => (k === "prompt_text" || k === "request" || k === "trace" ? undefined : v)));
function whyBox(lines, ok) { return h("div", { class: "how why " + (ok === false ? "bad" : "good") }, h("ul", { style: "margin:0; padding-left:18px" }, lines.map((l) => h("li", {}, l)))); }
function answerHood(r, title) {
  if (!r.parts) return null;
  const LIM = 1800, pt = r.prompt_text || "";
  return h("div", { class: "uh" }, h("h4", {}, title, r.correct == null ? null : h("span", { class: "badge " + (r.correct ? "ok" : "bad"), style: "margin-left:10px" }, r.correct ? "✓ correct" : "✗ wrong")),
    h("p", { class: "how" }, r.behavior),
    h("table", { class: "t" }, h("tr", {}, ["document in the prompt", "characters", "share", "kept"].map((x) => h("th", {}, x))),
      r.parts.map((p) => h("tr", {}, h("td", { class: "mono" }, p.id), h("td", {}, fmt(p.chars)), h("td", {}, h("div", { class: "bar", style: "margin:0 0 2px" }, h("i", { style: "width:" + p.share + "%" })), p.share + "%"), h("td", {}, p.fragments ? p.fragments + " fragments" : "whole document")))),
    h("p", { class: "how" }, h("b", {}, "Why this answer is " + (r.correct == null ? "what it is" : r.correct ? "right" : "wrong"))), whyBox(r.why || [], r.correct),
    h("p", { class: "how" }, h("b", {}, "How the documents were picked")), codeBlock(r.request, "Kibana Dev Tools"),
    h("p", { class: "how" }, h("b", {}, "What the model received "), h("small", {}, "(system prompt: \"" + (state.cfg.system_prompt || "") + "\"; Copy gives the whole user message)")),
    codeBlock(pt.slice(0, LIM) + (pt.length > LIM ? "\n\n… " + fmt(pt.length - LIM) + " more characters (Copy gives all of it)" : ""), "User message · " + fmt(pt.length) + " characters", pt));
}
function underAnswer(sections) {
  const s = sections.filter(Boolean); if (!s.length) return null;
  return h("details", { class: "under", open: state.under ? "" : null }, h("summary", {}, "Under the hood: what went into the prompt, and why (D)"), h("div", { class: "uhgrid" }, s));
}
function traceView(trace) {
  const isCE = (t) => t === "apex_context_lookup" || (t || "").startsWith("platform.context_engine");
  let n = 0;
  return h("div", {}, trace.map((st) => st.type === "reasoning" ? h("p", { class: "how" }, h("i", {}, "The agent thinks: " + st.text))
    : h("div", { class: "uh" }, h("span", { class: "tool" + (isCE(st.tool) ? " ce" : "") }, (++n) + " · " + st.tool), h("small", {}, st.rows != null ? " " + st.rows + " rows returned" : st.found != null ? " " + st.found + " results returned" : ""),
      codeBlock(st.params, "parameters sent to the tool"), st.esql ? codeBlock(st.esql, "ES|QL that ran") : null)));
}
function agentHood(q) {
  const box = $("#agentHood"); if (!box) return;
  const sec = (a) => { const r = state.agents[a + ":" + q + ":" + state.mode]; return r && r.trace ? h("div", { class: "uh" }, h("h4", {}, AGENT_LABEL[a], h("span", { class: "badge " + (r.correct ? "ok" : "bad"), style: "margin-left:10px" }, r.correct ? "✓ all key facts" : "✗ key facts missing")), whyBox([r.why], r.correct), traceView(r.trace)) : null; };
  const s = state.cfg.agents.map(sec).filter(Boolean);
  put(box, s.length ? h("details", { class: "under", open: state.under ? "" : null }, h("summary", {}, "Under the hood: what each agent did, step by step (D)"), h("div", { class: "uhgrid" }, s)) : null);
}
function renderClause(it, cid) {
  cid = cid || state.clause || state.cfg.clause_ids[0]; state.clause = cid;
  const go = (c) => renderClause(it, c), inp = h("input", { id: "cid", value: cid, size: 22, style: "padding:8px 10px; border:1.5px solid var(--blue); border-radius:10px; font:inherit" });
  put($("#stage"), ...head(it), h("p", {}, "Ask for the notice period of any contract. The truth is read from the contract itself (clause 15.3), so every answer can be checked."),
    h("div", { class: "row", style: "margin-bottom:12px" }, state.cfg.clause_ids.map((c, i) => h("button", { class: "btn" + (c === cid ? " primary" : ""), onclick: () => go(c) }, c.replace("APX-MSA-", "") + (i === state.cfg.clause_ids.length - 1 ? " (control)" : ""))),
      state.mode === "live" ? [inp, h("button", { class: "btn", onclick: () => go(inp.value.trim().toUpperCase()) }, "Ask")] : null),
    h("div", { id: "clauseout" }, h("div", { class: "loading" }, h("div", { class: "spin" }), "Asking naive and engineered RAG about " + cid + "…")));
  api("/api/clause", { q: cid, mode: state.mode }).then((d) => {
    const doc = (r) => [...(r.docs.includes(cid) ? [] : [h("span", { class: "chip bad" }, "✗ " + cid + " not retrieved")]), ...r.docs.slice(0, 5).map((x) => h("span", { class: "chip" + (x === cid ? " ok" : ""), style: x === cid ? "" : "background:var(--gray)" }, (x === cid ? "✓ " : "") + x))];
    const card = (title, r, hl) => h("div", { class: "card" + (hl ? " hl" : "") }, h("h3", {}, title, h("span", { class: "badge " + (r.correct ? "ok" : "bad") }, r.correct ? "✓ right" : "✗ wrong")),
      h("div", { class: "tiles" }, tile("answer says", r.days && r.days.length ? r.days.join(" / ") + " days" : "no number"), tile("truth", d.truth + " days"), tile("prompt tokens", fmt(r.prompt)), tile("cost", eur(r.cost))),
      h("small", {}, "Documents in the prompt"), h("div", { class: "chips" }, doc(r)),
      h("details", {}, h("summary", {}, "Show the answer"), h("div", { class: "answer" }, r.answer)));
    put($("#clauseout"), metaLine(d), h("div", { class: "qline" }, d.question), h("div", { class: "cols2" }, card("Naive · semantic top-3, whole contracts", d.naive, false), card("Engineered · hybrid + fragments", d.engineered, true)),
      underAnswer([answerHood(d.naive, "Naive · whole contracts"), answerHood(d.engineered, "Engineered · relevant fragments")]));
    setRight({ title: "What happened?", bullets: ["Truth from the contract: " + d.truth + " days.", "Naive: " + (d.naive.days.length ? d.naive.days.join(" / ") + " days" : "no number") + " → " + (d.naive.correct ? "right" : "wrong") + ".", "Engineered: " + (d.engineered.days.length ? d.engineered.days.join(" / ") + " days" : "no number") + " → " + (d.engineered.correct ? "right" : "wrong") + "."],
      why: "The vector cannot tell contract numbers apart, so naive RAG pulls the same near-duplicate documents whatever you ask. The answer then sounds confident and is about the wrong contract. Bigger prompts do not fix wrong context.", sources: [...new Set([...d.naive.docs, ...d.engineered.docs])], details: slim(d) });
  }).catch((e) => put($("#clauseout"), h("div", { class: "err" }, e.message)));
}
function renderRetrieve(it, d) {
  put($("#stage"), ...head(it), metaLine(d), h("div", { class: "qline" }, d.question),
    h("div", { class: "cols3" }, d.rows.map((r) => h("div", { class: "card" + (r.hit ? "" : "") }, h("h3", {}, MODE_LABEL[r.mode], h("span", { class: "badge " + (r.hit ? "ok" : "bad") }, r.hit ? "✓ right" : "✗ wrong")),
      r.ids.map((id, i) => h("div", { class: "rank" + (i === 0 ? " first" : "") }, h("span", { class: "no" }, i + 1), h("div", { style: "min-width:0" }, h("span", { class: "mono" }, id), (d.labels || {})[id] ? [h("small", { class: "lab" }, d.labels[id].text), d.labels[id].note ? h("small", { class: "lab " + (d.labels[id].flag || "") }, (d.labels[id].flag === "warn" ? "⚠ " : "✓ ") + d.labels[id].note) : null] : null), r.scores ? h("small", { class: "mono", style: "margin-left:auto" }, r.scores[i]) : null)), h("small", {}, r.ms + " ms")))),
    h("p", {}, "Expected first: ", d.expected.map((x) => h("span", { class: "mono" }, x + " "))),
    underHood(d.rows));
  const bad = d.rows.filter((r) => !r.hit).map((r) => MODE_LABEL[r.mode].split(" ·")[0]);
  setRight({ title: "What happened?", bullets: d.rows.map((r) => MODE_LABEL[r.mode].split(" ·")[0] + " returned " + (r.ids[0] || "nothing") + " first: " + (r.hit ? "right" : "wrong")),
    why: (it.say || "") + (d.trap ? " The trap: " + d.trap + "." : "") + (bad.length ? "" : " Every mode gets this one right."), sources: [...new Set(d.rows.flatMap((r) => r.ids))], expected: d.expected_answer, details: d });
}

function answerChips(text, must) { return must.map((t) => ({ term: t, found: new RegExp(t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "i").test(text || "") })); }
function chipRow(chips) { return h("div", { class: "chips" }, chips.map((c) => h("span", { class: "chip " + (c.found ? "ok" : "bad") }, (c.found ? "✓ " : "✗ ") + c.term))); }
function resultCard(title, r, base, hl) {
  const rel = (v, b) => Math.max(4, Math.round((v / (b || v || 1)) * 100)) + "%";
  return h("div", { class: "card" + (hl ? " hl" : "") }, h("h3", {}, title, r.correct == null ? null : h("span", { class: "badge " + (r.correct ? "ok" : "bad") }, r.correct ? "✓ correct" : "✗ wrong")),
    h("div", { class: "tiles" }, tile("prompt tokens", fmt(r.prompt)), tile("cost", eur(r.cost)), tile("LLM time", secs(r.llm_ms)), tile("retrieval", secs(r.ret_ms))),
    h("small", {}, "prompt size vs naive"), h("div", { class: "bar" }, h("i", { style: "width:" + rel(r.prompt, base.prompt) })),
    h("details", {}, h("summary", {}, "Show the answer"), h("div", { class: "answer" }, r.answer)), h("small", {}, "Sources: ", r.docs.slice(0, 3).join(" · ")));
}
function renderAnswer(it, d) {
  const must = state.cfg.agent_questions.HERO.must, chips = answerChips(d.answer, must), hit = chips.filter((c) => c.found).length;
  put($("#stage"), ...head(it), metaLine(d), h("div", { class: "qline" }, d.question),
    h("div", { class: "cols2" }, h("div", { class: "card hl" }, h("h3", {}, "Prompt sent to " + state.cfg.deployment), h("div", { class: "tiles" }, tile("prompt tokens", fmt(d.prompt)), tile("cost", eur(d.cost)), tile("completion tokens", fmt(d.completion)), tile("LLM time", secs(d.llm_ms))),
      h("p", {}, h("small", {}, "This is the number of the bet."))),
      h("div", { class: "card" }, h("h3", {}, "What the answer contains"), chipRow(chips), h("details", { open: "" }, h("summary", {}, "The answer"), h("div", { class: "answer" }, d.answer)))),
    underAnswer([answerHood(d, "Naive RAG · the bet")]));
  setRight({ title: "What happened?", bullets: ["Three whole contracts went into the prompt: " + fmt(d.prompt) + " tokens, " + eur(d.cost) + ".", "The answer mentions " + hit + " of " + must.length + " key facts" + (chips.find((c) => c.term === "Veltrano" && !c.found) ? " and never names the Veltrano group." : ".")],
    why: "The hidden risk is in news and registry extracts in other languages, not in these contracts. More context did not find it.", sources: d.docs, expected: d.expected_answer, details: slim(d) });
}
function renderCompare(it, d) {
  const dl = d.delta;
  put($("#stage"), ...head(it), metaLine(d), h("div", { class: "qline" }, d.question),
    h("div", { class: "row", style: "margin-bottom:12px" }, h("span", { class: "delta good" }, "prompt tokens " + (dl.prompt > 0 ? "+" : "") + dl.prompt + "%"), h("span", { class: "delta good" }, "cost " + (dl.cost > 0 ? "+" : "") + dl.cost + "%"),
      h("span", { class: "delta flat" }, "LLM time " + (dl.latency > 0 ? "+" : "") + dl.latency + "% · varies run to run")),
    h("div", { class: "cols2" }, resultCard("Naive · whole contracts", d.naive, d.naive, false), resultCard("Engineered · relevant fragments", d.engineered, d.naive, true)),
    h("p", {}, h("small", {}, "About " + (d.naive.cost * 10000).toFixed(0) + " EUR vs " + (d.engineered.cost * 10000).toFixed(0) + " EUR for 10,000 questions.")),
    underAnswer([answerHood(d.naive, "Naive · whole contracts"), answerHood(d.engineered, "Engineered · relevant fragments")]));
  setRight({ title: "What happened?", bullets: ["Prompt tokens " + fmt(d.naive.prompt) + " → " + fmt(d.engineered.prompt) + " (" + dl.prompt + "%).", "Cost " + eur(d.naive.cost) + " → " + eur(d.engineered.cost) + " (" + dl.cost + "%).",
    "Judge: naive " + (d.naive.correct ? "correct" : "wrong") + ", engineered " + (d.engineered.correct ? "correct" : "wrong") + "."],
    why: "The win is tokens and cost. Latency is dominated by the length of the answer, so a single call is about the same.", sources: [...new Set([...d.naive.docs, ...d.engineered.docs])], expected: d.expected_answer, details: slim(d) });
}

/* agents */
function renderAgents(it) {
  const q = it.q, qd = state.cfg.agent_questions[q];
  const col = (agent, desc, hl) => h("div", { class: "card" + (hl ? " hl" : ""), id: "ag-" + agent }, h("h3", {}, AGENT_LABEL[agent]), h("p", {}, h("small", {}, desc)),
    h("div", { class: "row" }, h("button", { class: "btn primary", id: "run-" + agent, onclick: () => runAgent(agent, q) }, "Run this agent")), h("div", { id: "res-" + agent }));
  put($("#stage"), ...head(it), h("div", { class: "qline" }, qd.question),
    h("div", { class: "row", style: "margin-bottom:12px" }, h("button", { class: "btn primary", onclick: () => Promise.all(state.cfg.agents.map((a) => runAgent(a, q))) }, "Run both"), h("small", {}, state.mode === "live" ? "Each run takes 10–40 s." : "Practice shows the last recorded run.")),
    h("div", { class: "cols2" }, col("apex-analyst-baseline", "The same five search tools and the same instructions. No AI index.", false),
      col("apex-analyst-context", "The same tools and instructions, plus the Context Engine AI index and a lookup tool on top of it.", true)),
    h("div", { id: "agentHood", style: "margin-top:14px" }));
  setRight({ title: "What happened?", bullets: ["Run the baseline first, then the Context Engine agent while it works."], why: it.say });
  state.cfg.agents.forEach((a) => { const r = state.agents[a + ":" + q + ":" + state.mode]; if (r) paintAgent(a, q, r); });
  if (state.mode === "practice") state.cfg.agents.forEach((a) => { if (!state.agents[a + ":" + q + ":practice"]) runAgent(a, q); });
}
async function runAgent(agent, q) {
  const box = $("#res-" + agent), btn = $("#run-" + agent); if (!box) return;
  btn.disabled = true; const t0 = Date.now();
  put(box, h("div", { class: "loading" }, h("div", { class: "spin" }), h("span", { id: "el-" + agent }, "working… 0 s")));
  const tick = setInterval(() => { const e = $("#el-" + agent); if (e) e.textContent = "working… " + Math.round((Date.now() - t0) / 1000) + " s"; }, 500);
  try {
    const r = await api("/api/agent", { agent, q, mode: state.mode }); state.agents[agent + ":" + q + ":" + state.mode] = r; paintAgent(agent, q, r);
  } catch (e) { put(box, h("div", { class: "err" }, e.message)); } finally { clearInterval(tick); btn.disabled = false; }
}
function paintAgent(agent, q, r) {
  const box = $("#res-" + agent); if (!box) return;
  const isCE = (t) => t.startsWith("platform.context_engine") || t === "apex_context_lookup";
  put(box, metaLine(r), r.sample ? h("p", {}, h("small", {}, "Typical of " + r.sample.runs + " recorded runs: " + r.sample.correct + " of " + r.sample.runs + " found all key facts.")) : null, h("span", { class: "badge " + (r.correct ? "ok" : "bad") }, r.correct ? "✓ all key facts found" : "✗ key facts missing"),
    h("div", { class: "tiles" }, tile("run time", r.seconds + " s"), tile("LLM calls", r.llm_calls), tile("tool calls", r.tool_calls), tile("input tokens", fmt(r.input_tokens))),
    chipRow(r.chips), h("div", {}, h("small", {}, "Tool calls, in order"), h("div", {}, r.tools.map((t) => h("span", { class: "tool" + (isCE(t) ? " ce" : "") }, t.replace("platform.context_engine.", "CE · "))))),
    h("details", {}, h("summary", {}, "Show the answer"), h("div", { class: "answer" }, r.answer)));
  agentHood(q);
  const b = state.agents["apex-analyst-baseline:" + q + ":" + state.mode], c = state.agents["apex-analyst-context:" + q + ":" + state.mode];
  const bl = [];
  if (b) bl.push("Baseline: " + b.seconds + " s, " + b.llm_calls + " LLM calls, " + b.tool_calls + " tool calls, " + (b.correct ? "all key facts" : "key facts missing") + ".");
  if (c) bl.push("Context Engine: " + c.seconds + " s, " + c.llm_calls + " LLM calls, " + c.tool_calls + " tool calls, " + (c.correct ? "all key facts" : "key facts missing") + ".");
  setRight({ title: "What happened?", bullets: bl, why: "Same question, same model, same tools. The agent with the AI index asks it first instead of rediscovering the data. It uses a lookup tool of ours on top of the AI index; Context Engine is a private preview.", details: slim({ baseline: b, context: c }) });
}

/* scoreboard + links */
function renderScoreboard(it, d) {
  const act2 = d.act2 || [], by = (m) => act2.find((x) => x.mode === m) || {};
  const row = (m) => { const x = by(m); return h("tr", { class: m === "engineered" ? "hlrow" : "" }, h("td", {}, m), h("td", {}, fmt(x.prompt_tokens)), h("td", {}, x.cost_eur != null ? "€" + x.cost_eur : "–"), h("td", { style: "white-space:nowrap" }, secs(x.llm_ms)), h("td", { style: "white-space:nowrap" }, x.accuracy_pct != null ? [x.accuracy_pct + "%", h("br"), h("small", {}, x.correct_n + " of " + x.judged + " judged")] : "–"), h("td", {}, x.runs)); };
  const az = (d.azure || [])[0] || {}, al = d.alert;
  put($("#stage"), ...head(it), metaLine(d),
    h("div", { class: "cols2" },
      h("div", { class: "card hl" }, h("h3", {}, "Act 2 · naive vs engineered (last " + (d.window || "24 hours") + ")"), h("table", { class: "t" }, h("tr", {}, ["mode", "prompt tokens", "cost / question", "LLM time", "accuracy", "runs"].map((x) => h("th", {}, x))), row("naive"), row("engineered"))),
      h("div", { class: "card" }, h("h3", {}, "Act 1 · hit@1 by retrieval mode"), ["bm25", "semantic", "hybrid"].map((m) => { const x = (d.act1 || []).find((y) => y.mode === m) || {}; return h("div", {}, h("small", {}, MODE_LABEL[m] + (x.hit_at_1_pct != null ? " · " + x.hit_at_1_pct + "% (" + x.runs + " questions)" : "")), h("div", { class: "bar" }, h("i", { style: "width:" + (x.hit_at_1_pct || 0) + "%;background:" + (m === "hybrid" ? "var(--blue)" : "var(--mgray)") }))); }))),
    h("div", { class: "cols2", style: "margin-top:16px" },
      h("div", { class: "card" }, h("h3", {}, "Azure OpenAI, from Azure's own logs (last " + (d.window || "24 hours") + ")"), h("div", { class: "tiles" }, tile("calls", fmt(az.calls)), tile("p95 latency", secs(az.p95_ms)), tile("tokens in / out", fmt(az.prompt_tokens) + " / " + fmt(az.completion_tokens)), tile("estimated cost", az.cost_eur != null ? "€" + az.cost_eur : "–"))),
      h("div", { class: "card" }, h("h3", {}, "Agents · from Agent Builder traces"), h("table", { class: "t" }, h("tr", {}, ["agent", "runs", "run time", "LLM calls", "tools"].map((x) => h("th", {}, x))),
        (d.agents || []).map((a) => h("tr", { class: /Context/.test(a.agent) ? "hlrow" : "" }, h("td", {}, a.agent.replace("Apex Analyst ", "")), h("td", {}, a.runs), h("td", {}, a.avg_run_s + " s"), h("td", {}, a.avg_llm_calls), h("td", {}, a.avg_tool_calls)))))),
    d.billing && d.billing.available ? h("div", { class: "card hl", style: "margin-top:16px" }, h("h3", {}, "Cost: billed by Azure vs estimated from tokens", h("span", { class: "badge ok" }, d.billing.period[0] + " to " + d.billing.period[1] + " · invoiced up to " + d.billing.billed_through)),
      h("div", { class: "cols2" },
        h("div", {}, h("div", { class: "tiles" }, tile("billed so far (Azure OpenAI)", "€" + d.billing.openai_total.toFixed(2)), tile("estimated, same days", "€" + d.billing.estimated.cost.toFixed(2)), tile("difference", (d.billing.delta_pct > 0 ? "+" : "") + d.billing.delta_pct + "%"), tile("calls in logs", fmt(d.billing.estimated.calls))),
          d.billing.not_invoiced && d.billing.not_invoiced.calls ? h("p", {}, h("small", {}, "Not invoiced yet: about €" + d.billing.not_invoiced.cost.toFixed(2) + " estimated for " + fmt(d.billing.not_invoiced.calls) + " calls since " + d.billing.not_invoiced.from + ". The invoice follows the next day.")) : null,
          h("small", {}, "Azure Cost Management, pretax. The estimate is tokens times the public price list; the invoice also prices cached input tokens separately.")),
        h("div", {}, h("table", { class: "t" }, h("tr", {}, ["billed line", "EUR"].map((x) => h("th", {}, x))), d.billing.openai.map((b) => h("tr", {}, h("td", {}, b.product), h("td", {}, "€" + b.cost.toFixed(3))))),
          h("p", {}, h("small", {}, "Monitoring plumbing" + (d.billing.other_period ? ", " + d.billing.other_period[0] + " to " + d.billing.other_period[1] : "") + ": €" + d.billing.other_total.toFixed(2) + " (" + d.billing.other.slice(0, 3).map((x) => x.product.replace(/ - .*/, "")).join(", ") + ")."))))) : null,
    h("div", { class: "row", style: "margin-top:16px" }, h("span", { class: "badge " + (al && al.active ? "bad" : "ok") }, al ? "Alert: " + (al.active ? "FIRING" : "quiet") + " · prompt over 10,000 tokens in one call" : "Alert rule not found"), h("a", { class: "btn", href: "#/demo", onclick: (e) => { e.preventDefault(); select("links"); } }, "Open the dashboards")),
    d.errors && d.errors.length ? h("p", { class: "err", style: "margin-top:12px" }, d.errors.join(" · ")) : null);
  setRight({ title: "What happened?", bullets: ["Naive " + fmt(by("naive").prompt_tokens) + " tokens vs engineered " + fmt(by("engineered").prompt_tokens) + ".", "Cost per question " + (by("naive").cost_eur != null ? "€" + by("naive").cost_eur : "–") + " vs " + (by("engineered").cost_eur != null ? "€" + by("engineered").cost_eur : "–") + ".", "Azure p95 latency " + secs(az.p95_ms) + " over " + fmt(az.calls) + " calls."].concat(d.billing && d.billing.available ? ["Billed Azure OpenAI €" + d.billing.openai_total.toFixed(2) + " vs estimated €" + d.billing.estimated.cost.toFixed(2) + " (" + (d.billing.delta_pct > 0 ? "+" : "") + d.billing.delta_pct + "%)."] : []),
    why: "Every number comes from traces, logs and the Azure invoice, not slides. The live cost is an estimate from tokens times the public price list; the invoice arrives the next day and is lower when caching kicks in (agents resend the same context).", details: d });
}
function renderLinks(it, d) {
  const order = ["scoreboard", "azure", "foundry", "agents", "agent_overview", "billing", "alerts", "agent_builder"];
  put($("#stage"), ...head(it), h("p", {}, "Each opens in a new tab, on the last hour."),
    h("div", { class: "linkgrid" }, order.filter((k) => d[k]).map((k) => { const l = d[k]; return h("div", { class: "card" }, h("h3", {}, l.title.replace(/^\[.*?\]\s*/, "")), h("small", {}, l.project === "obs" ? "Observability project" : "Search project"),
      h("div", { style: "margin-top:10px" }, l.url ? h("a", { class: "btn primary", href: l.url, target: "_blank", rel: "noopener" }, "Open") : h("span", { class: "badge warn" }, l.error || "not available"))); })),
    h("div", { class: "card", style: "margin-top:16px" }, h("h3", {}, "The alert: prompt over 10,000 tokens in one call"), h("div", { id: "alertbox" }, h("div", { class: "loading" }, "Checking the alert…"))));
  loadAlert();
  setRight({ title: "Where each number lives", bullets: ["Scoreboard: tokens, cost and accuracy (CLI traces).", "Azure usage and cost: Azure's own logs.", "Foundry overview: Azure Monitor metrics.", "Agents: our comparison from Agent Builder traces (Search project).", "Agent Builder Overview: Elastic's own dashboard for the agents, tools and conversations (Search project).", "Billing: the invoice, the next day.", "The alert is active for about 5 minutes after a big call, then it recovers: look at All statuses."], details: d });
}
async function loadAlert() {
  const box = $("#alertbox"); if (!box) return;
  let a; try { a = await api("/api/alert-status"); } catch (e) { put(box, h("div", { class: "err" }, e.message)); return; }
  if (!a.found) { put(box, h("span", { class: "badge warn" }, "alert rule not found")); return; }
  const when = (t) => (t ? new Date(t).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "now");
  const fire = h("button", { class: "btn primary", onclick: async (e) => { e.target.disabled = true; e.target.textContent = "Sending one naive call…"; try { await api("/api/answer", { q: "Q06", llm: "naive", mode: "live" }); e.target.textContent = "Sent. The alert goes active in 1–2 minutes"; } catch (x) { e.target.textContent = "Failed: " + x.message; } setTimeout(loadAlert, 70000); } }, "Fire the alert now");
  put(box, h("p", { class: "badge " + (a.active ? "bad" : "ok") }, a.active ? "ACTIVE now" : "quiet now · " + (a.enabled ? "rule enabled" : "rule DISABLED") + " · last run " + a.outcome),
    h("p", {}, h("small", {}, "The rule looks at the last 5 minutes, every minute, so an alert stays active for about 5 minutes after the last call over 10,000 tokens and then shows as recovered.")),
    a.alerts.length ? h("table", { class: "t" }, h("tr", {}, ["status", "started", "ended"].map((x) => h("th", {}, x))), a.alerts.map((x) => h("tr", {}, h("td", {}, x.status), h("td", {}, when(x.start)), h("td", {}, x.end ? when(x.end) : "–")))) : h("p", {}, "No alert has fired yet."),
    state.mode === "live" ? h("div", { class: "row", style: "margin-top:10px" }, fire, h("a", { class: "btn", href: a.alerts_url, target: "_blank", rel: "noopener" }, "Open alerts (all statuses)"), h("a", { class: "btn", href: a.rule_url, target: "_blank", rel: "noopener" }, "Rule history")) : h("p", {}, h("small", {}, "Switch to Live to fire it.")));
}

/* other pages */
function how() {
  const rows = [["Demo console", "Python · OpenAI SDK · EDOT", "OpenTelemetry (OTLP)", "managed OTLP endpoint", "Observability project", "traces-*", "Scoreboard + alert"],
    ["Agent Builder agents", "baseline vs Context Engine", "Built-in trace collection", "agent runs · LLM calls · tools", "Elasticsearch project", "traces-agent_builder.otel-*", "Agents dashboard"],
    ["Azure Monitor metrics", "requests · tokens · availability", "Azure AI Foundry integration", "agentless · service principal", "Observability project", "metrics-azure.ai_foundry-*", "Foundry overview"],
    ["Azure diagnostic logs", "one record per model call", "Event Hub → Elastic Agent", "agent in a container", "Observability project", "logs-azure_ai_foundry.logs-*", "Azure usage and cost"],
    ["Azure Cost Management", "billed cost, per day", "Azure Billing integration", "agentless · Cost Management API", "Observability project", "metrics-azure.billing-*", "Cognitive Services billing"]];
  put($("#app"), h("section", { class: "hero" }, h("div", { class: "eyebrow" }, "How it works"), h("h1", {}, "Every number has ", h("em", {}, "an address.")), h("p", {}, "Two Serverless projects on purpose: Search holds the data, the Context Engine and the agents. Observability holds everything that is measured.")),
    h("section", { class: "arch" }, h("div", { class: "eyebrow" }, "The architecture, in motion"), h("h2", { style: "margin:4px 0 4px; font-size:1.6rem" }, "What the demo does, end to end"), h("div", { id: "archHost" })),
    h("div", { class: "flow", style: "margin-top:22px" }, h("div", { class: "flowrow flowhead" }, ["SOURCE", "HOW IT GETS IN", "LANDS IN", "YOU SEE IT IN"].map((x) => h("div", {}, x))),
      rows.map((r) => h("div", { class: "flowrow" }, h("div", {}, h("b", {}, r[0]), h("small", {}, r[1])), h("div", {}, h("b", {}, r[2]), h("small", {}, r[3])), h("div", {}, h("b", {}, r[4]), h("small", { class: "where mono" }, r[5])), h("div", {}, h("b", {}, r[6]))))),
    h("div", { class: "acts3", style: "margin-top:22px" }, [["Why it is trustworthy", "Live mode runs the real retrieval, Azure OpenAI and Agent Builder. Practice shows the last recorded run and says so."], ["What it does not claim", "Latency of a single call is about the same: the win is tokens and cost. The Context Engine is a private preview."], ["Where to look", "Technical guides, the repo (after the event) and the Service status page."]].map(([t, p]) => h("div", { class: "actcard" }, h("h3", {}, t), h("p", {}, p)))));
  if (window.initArch) state.archStop = window.initArch($("#archHost"));
}
async function status(fresh) {
  put($("#app"), h("section", { class: "hero" }, h("div", { class: "eyebrow" }, "Check before a live demo"), h("h1", {}, "Service status"), h("div", { id: "stat" }, h("div", { class: "loading" }, h("div", { class: "spin" }), "Checking the services…"))));
  try {
    const d = await api("/api/health" + (fresh ? "?fresh=true" : "")); state.health = d;
    const lab = { OK: "GO", WARN: "GO with warnings", FAIL: "NO-GO" };
    put($("#stat"), h("p", { class: "badge " + (d.overall === "OK" ? "ok" : d.overall === "WARN" ? "warn" : "bad") }, lab[d.overall] + " · checked " + d.checked_at),
      h("table", { class: "t" }, h("tr", {}, ["check", "status", "detail"].map((x) => h("th", {}, x))), d.rows.map((r) => h("tr", {}, h("td", {}, r.name), h("td", {}, h("span", { class: "dot " + r.status }), r.status), h("td", {}, r.detail)))),
      h("div", { class: "row", style: "margin-top:14px" }, h("button", { class: "btn primary", onclick: () => status(true) }, "Check again")));
  } catch (e) { put($("#stat"), h("div", { class: "err" }, e.message)); }
}
function guides() {
  const g = [["Runbook", "docs/RUNBOOK.md", "The 45-minute running order, checklist and what to do when something fails."], ["Measured results", "docs/RESULTS.md", "Every number, with its conditions and caveats."], ["The story", "docs/STORY.md", "The answers (keep private until after the talk)."], ["Agents setup", "agents/SETUP.md", "Tools, instructions and the lookup tool."], ["Observability", "observability/README.md", "Azure monitoring, dashboards, the alert, the queries."], ["Stage driver", "demo/stage.py", "python3 stage.py list | preflight | warmup | show | replay"]];
  put($("#app"), h("section", { class: "hero" }, h("div", { class: "eyebrow" }, "Technical guides"), h("h1", {}, "Everything is in ", h("em", {}, "the repo."))),
    h("div", { class: "linkgrid" }, g.map(([t, p, d]) => h("div", { class: "card" }, h("h3", {}, t), h("p", {}, d), h("span", { class: "mono" }, p)))));
}


/* admin: preparation commands behind buttons (local only) */
async function admin() {
  put($("#app"), h("section", { class: "hero" }, h("div", { class: "eyebrow" }, "Before the talk, not during"), h("h1", {}, "Admin: ", h("em", {}, "get ready.")),
    h("p", {}, "Three moments matter. Nothing here is needed while you are on stage.")),
    h("div", { class: "acts3" },
      [["The day before (21 Oct)", "Run the agent evaluation, then record Practice. That fills the Agents dashboard and gives you the fallback data."],
       ["30 and 5 minutes before", "Run the preflight (must say GO), then the warmup. The scoreboard sees only the last 2 hours."],
       ["During the talk", "Nothing to run. Use Try the demo and Kibana. If something fails, press M for Practice."]].map(([t, p]) => h("div", { class: "actcard" }, h("h3", {}, t), h("p", {}, p)))),
    h("div", { id: "adm", style: "margin-top:22px" }, h("div", { class: "loading" }, h("div", { class: "spin" }), "Loading…")));
  let jobs;
  try { jobs = await api("/api/admin/jobs"); } catch (e) { put($("#adm"), h("div", { class: "err" }, "Admin is disabled in this version.")); return; }
  const groups = [["stage", "Before going on stage (T-30 and T-5)"], ["day_before", "The day before"]];
  const logbox = h("pre", { id: "admlog", class: "answer", style: "max-height:420px; font-size:.8rem; background:var(--gray)" }, "Nothing run yet.");
  const bar = h("p", { id: "admbar", class: "badge warn" }, "idle");
  const btns = {};
  const card = (j) => { const b = h("button", { class: "btn primary", onclick: () => run(j.id) }, "Run"); btns[j.id] = b;
    return h("div", { class: "card" }, h("h3", {}, j.title, h("span", { class: "badge warn" }, j.minutes)),
      h("p", {}, h("b", {}, "When: "), j.when), h("p", {}, h("b", {}, "What it does: "), j.what), h("p", {}, h("small", {}, j.tip)),
      h("p", {}, h("small", {}, "Cost: " + j.cost + " · command: "), h("span", { class: "mono" }, j.cmd)), b); };
  put($("#adm"), bar, logbox, groups.map(([g, t]) => [h("h2", { style: "margin:22px 0 10px" }, t), h("div", { class: "cols2" }, jobs.filter((j) => j.group === g).map(card))]));
  async function run(id) {
    try { await api("/api/admin/run", { id }); } catch (e) { put(bar, e.message); bar.className = "badge bad"; return; }
    poll(); bar.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  async function poll() {
    clearInterval(state.timer);
    const tick = async () => {
      let s; try { s = await api("/api/admin/status"); } catch { return; }
      Object.values(btns).forEach((b) => (b.disabled = s.running));
      if (!s.id) return;
      logbox.textContent = s.lines.join("\n") || "Starting…"; logbox.scrollTop = logbox.scrollHeight;
      const j = jobs.find((x) => x.id === s.id);
      if (s.running) { bar.className = "badge warn"; put(bar, "Running: " + j.title + " · " + Math.round(s.elapsed) + " s"); }
      else { clearInterval(state.timer); bar.className = "badge " + (s.rc === 0 ? "ok" : "bad"); put(bar, (s.rc === 0 ? "Done: " : "Failed (exit " + s.rc + "): ") + j.title + " · " + Math.round(s.elapsed) + " s"); }
    };
    await tick(); state.timer = setInterval(tick, 2000);
  }
  poll();
}

/* ---------------------------------------------------------------- router */
function route() {
  const r = (location.hash.replace("#/", "") || "").split("?")[0];
  document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("on", a.dataset.r === r));
  clearInterval(state.timer); if (state.archStop) { state.archStop(); state.archStop = null; }
  ({ "": home, demo, how, status: () => status(false), guides, admin }[r] || home)();
  $("#app").focus({ preventScroll: true });
}
$("#modeLive").addEventListener("click", () => { setMode("live"); if (location.hash === "#/demo" && state.sel) select(state.sel); });
$("#modePractice").addEventListener("click", () => { setMode("practice"); if (location.hash === "#/demo" && state.sel) select(state.sel); });
window.addEventListener("hashchange", route);
window.addEventListener("keydown", (e) => {
  if (location.hash !== "#/demo" || e.metaKey || e.ctrlKey || /INPUT|TEXTAREA/.test(document.activeElement.tagName)) return;
  if (e.key === "ArrowRight") step(1); else if (e.key === "ArrowLeft") step(-1); else if (e.key.toLowerCase() === "r" && state.sel) select(state.sel);
  else if (e.key.toLowerCase() === "d") { state.under = !state.under; document.querySelectorAll("details.under").forEach((x) => (x.open = state.under)); }
  else if (e.key.toLowerCase() === "m") { setMode(state.mode === "live" ? "practice" : "live"); if (state.sel) select(state.sel); }
});
setMode("live"); route();
api("/api/config").then((c) => { if (c.admin) $("#navAdmin").hidden = false; }).catch(() => {});
