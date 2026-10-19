# Talk script: "RAG is Broken: How Elastic & Azure Fix Context, Latency, and Token Bills"
AI Dev Night with Microsoft and Elastic, Köln, 22 Oct 2026, 19:30, 45 minutes. English lines in quotes, stage directions in plain text.
The speech word for word is in `docs/SPEECH_SCRIPT.md`; this file is the cheat sheet (numbers, tables, what to do if something fails).
Numbers are from 14 and 18 Oct (`docs/RESULTS.md`): say the live ones when they differ.

Guiding question: *"Which of our suppliers could expose ApexPharm to compliance risk, and what do our contracts let us do about it?"*
One sentence for the whole talk: **more context is not better context.** Act 1: the wrong context. Act 2: too much context. Act 3: invisible context.

## Timing (45 min)
| Min | Part | Where |
|---|---|---|
| 0-3 | Bridge from Mike + the bet | slides 1-2 |
| 3-6 | The reveal: naive RAG on the HERO question, live | console (Act 2, HERO) |
| 6-7 | What you just saw: RAG isn't dead | slide 3 |
| 7-10 | Apex, the question, the three acts, what is running | slides 4-7 |
| 10-18 | Act 1: wrong context | console, Act 1 |
| 18-30 | Act 2: too much context | console, Act 2 |
| 30-38 | Act 3: invisible context | slide 8 while the alert warms up, then Kibana (6 tabs) |
| 38-41 | Close | slide 9 |
| 41-45 | Q&A, then thank you | slide 10 (Q&A), slide 11 (thank you) |

---
## Opening (0-10 min)
**Bridge (slides 1-2, 1 min).**
> "Mike made the agents safe. Now: what do they cost, and how do you know they're right?"

**The bet (slide 2, 2 min).** Ask the room, take 2-3 guesses, write the closest one down. Keep the console tab out of sight.
> "How many tokens does a naive RAG send to Azure OpenAI to answer ONE question? Closest guess wins. We'll find out in a minute."

**The reveal: naive RAG, live (console, 3 min).** Switch to the console, *Try the demo, Act 2, Naive RAG on the HERO question*, Live. Press run; it takes 8-10 seconds: ask who is closest while it works. If it fails, press `M` (the recorded run shows the same number).
> "The bet. A naive RAG sent 7,591 tokens: three whole contracts, 38,000 characters. Who guessed closest?"
> "It cost about one cent. And it is wrong. Look: none of the five key facts are in the prompt. It lists suppliers at random and never names Veltrano."
Under the hood (`D`): the three documents, none of them the ones we need.
> "More context did not find the hidden risk. It sits in news and registry extracts in other languages. Cheap and confident is the worst combination."
Back to the deck.

**What you just saw (slide 3, 1 min).**
> "So yes, the title is a provocation. RAG isn't dead: grounding the model in your data is the right idea. Naive RAG is broken, and you've just seen it. Chunk, embed, top-k, paste it into the prompt: it works in a demo and breaks in production. Tonight is about fixing that, and the fix isn't a bigger model, it's better retrieval."

**Apex and the question (slides 4-7, 3 min).**
> "Apex Conglomerate is synthetic, realistic, messy. Like your data. 9,264 documents, 15 indices, five languages, two policy versions and one hidden risk."
> "Tonight's question: which of our suppliers could expose ApexPharm to compliance risk, and what do our contracts let us do about it? The answer is scattered across ten documents, four indices, three languages, and one stale policy that says the opposite."
> "Three ways RAG breaks: the wrong context, too much context, and context you can't see. One scoreboard fills in as we go."
Slide 6 is the empty table: "we fill it in at the end". Slide 7: what is running tonight (30 s). Leave slide 7 on screen, then switch to the console (Try the demo, Live).

---
## Act 1: the wrong context (10-18 min)
Message: **no single retrieval mode wins everywhere**. The vector is blind to identifiers, keywords are fooled by common words, and relevant is not the same as valid.
Open *Under the hood* (key `D`) on the first two examples.

**1. Contract 0117 vs 0171 (Q02), 3-4 min. The main example.**
> "Same contract family, one digit apart. I ask for the termination notice of 0171."
Show the three cards. Semantic is wrong: it ranks 0125 first, with scores 0.773, 0.767 and 0.759.
> "Look at those scores. To an embedding, 0117 and 0171 are almost the same string, so the ranking is decided by a hair. The right contract is not even in the top 20. Keywords find it: the whole identifier is one token in a dedicated field. Hybrid finds it too."
Open the dark code block: the third leg of the hybrid query, `terms` on `content.codes`.
> "Identifiers are facts, not similarities."

**2. Q01, right for the wrong reason, 2 min. The twist.**
> "Now the opposite. Keywords fail here, even with the identifier in the question."
Under the hood, BM25: the rare word "changes" scored 6.82 against 5.04 for the exact identifier.
> "BM25 weighs a rare word as much as an identifier. And the vector is first by 0.004: right, but by luck. No single mode wins. That is why we fuse them, and why we keep an exact leg."

**3. Two policy versions (Q03), 1-2 min.**
> "Everyone returns the right policy first. But look at second place: version 1.0, superseded, the 40% threshold. A model that mixes the two tells you there's no action needed."
Point at the orange labels: *older version, superseded*.
> "Relevant is not the same as valid. Search does not know a document expired. Metadata does: the lifecycle status."

**4. Veltran vs Veltrano (Q04), 1 min.**
> "Veltran Logistik is a family business. Veltrano Holding is the group we'll meet in a minute. Names are not meaning: the right document is first, but the neighbours are other companies."
Point at *another company*.

**Q05 (German part code)**: skip, unless asked about multilingual: "A control. German question, near-duplicate part codes. Keywords tie, the vector separates them thanks to one word. Hybrid wins because it has both."

Close of Act 1 (EN):
> "Hit at one: keywords 75, vector 75, hybrid 100. Nobody wins alone."
Number to remember: hit@1 on Q01 to Q04 is 75% / 75% / 100%.

---
## Act 2: too much context (18-30 min)
Message: **bigger prompts do not fix wrong context; they make it expensive**. Then agents: they rediscover the same facts on every question.

**1. Compare: long contracts (Q06), 3 min.**
> "Remember the bet? One question, 7,591 tokens, cheap and wrong. Now a question where the size of the prompt really hurts."
> "Same question, same model, same data. Only the context changes."
Naive 13,649 tokens against 7,815 engineered: minus 43%; cost minus 36%, same correct answer. About 110 against 70 euros per 10,000 questions.
Under the hood: naive pastes three whole contracts, the contract we need is third in the pile; engineered keeps the best fragments of the top documents.
> "And before someone asks: for a single call the latency is about the same, because the length of the answer dominates. The win is tokens and cost."

**2. Wrong context lab, 3 min.**
> "Ask me about any contract. I'll type one."
Type an id of someone in the room's choice (or use `APX-MSA-2022-0388`). Show truth, naive, engineered.
> "The truth is read from the contract itself, clause 15.3. Naive RAG got one contract right out of eight, the one that happens to be among the three documents the vector always returns. It pulls the same near-duplicates whatever you ask, and answers with the number of another contract. Engineered: eight out of eight."
> "A confident answer about the wrong contract is worse than no answer."
Use the control (`0117`) to show the naive "right by luck".

**3. Agents: baseline vs Context Engine, 6 min.**
Click *Run both* (Live; or Practice if the room is slow). Talk while they run.
> "Same model, same tools, same instructions. One agent has a prepared index, the Context Engine."
Under the hood, baseline: one search per supplier, over and over.
> "The baseline searches contracts supplier by supplier: around ten tool calls, a dozen LLM calls on a heavy run, and it never finds Veltrano. The other makes one call: a hybrid query on the index of knowledge indicators, ownership groups, spend share."
5 runs: HERO baseline 1 of 5, Context Engine 5 of 5. Medians: 141k to 25k tokens, 20 to 4 seconds, 14 to 2 LLM calls.
> "It works in most runs, not all. This is a private preview, and the agent calls a lookup tool of ours on top of the AI index. It is a workaround, not the default."
Q10 (spend share): baseline 4 of 5, Context Engine 5 of 5; 170k to 24k tokens. Say it if time allows: "Which share of critical spend sits with one group? 32.5%: an aggregation across news and master data."
If the first run fails: press `R`, or `M` for the recorded run.

Close of Act 2 (EN):
> "Same question, same model, same data. Only the context changed."

---
## Act 3: invisible context (30-38 min)
Message: **you can't fix what you can't see**. Four questions every AI feature must answer: what does it cost, how long does it take, is it right, how do I notice when it goes wrong? We answer by looking at the same system from different vantage points: the app, Azure, the agents, the invoice, and finally an alert.

**Before the first beat (1 min).**
In the console, *Dashboards and the alert*, press **Fire the alert now**. Then show slide 8 (where every number comes from) while the alert warms up. It sends one deliberately fat prompt; the alert becomes active in 1-2 minutes.
> "I just sent one deliberately fat prompt to Azure. Keep it in mind, we'll come back to it."

**Six beats.**
| Beat | Where | Say | Point at |
|---|---|---|---|
| 1. Our code, 2.5 min | Dashboard *Scoreboard* (Observability) | "Everything we ran in the last twenty minutes is here, measured by OpenTelemetry in our own app. Same question, same model: naive sends about 11,000 tokens, the engineered prompt about 7,500 (the mix of questions in the window decides). That is the cost per question, and this is the cost for 10,000 questions." | tokens and cost naive vs engineered; hit@1 bars of Act 1 (BM25 and semantic 75%, hybrid 100%); accuracy with "x of y judged" |
| 2. Azure, from its logs, 1 min | *Azure OpenAI: usage, latency and cost* | "Now not our code: Azure's own logs, one record per model call, through an Event Hub into Elastic. Average latency is around one and a half seconds, but p95 is about three times that. Those are the agent calls, with tens of thousands of tokens each." | calls, p95 vs average, tokens in/out, the spike of the fat call |
| 3. Azure, from metrics, 30 s | *Foundry Overview* | "Same story from Azure Monitor metrics. Different source, a few minutes behind. We reconcile three views of the same call." | requests, tokens, models; just a glance |
| 4. The agents, 1.5 min | *Agents* (ours), then *[Elastic] Agent Builder Overview* | "An agent that rediscovers everything pays for it: the baseline makes about fourteen LLM calls, twenty seconds, 140,000 tokens. The agent with the prepared index: two calls, four seconds, 25,000 tokens." then "And this one comes out of the box with Agent Builder." | run time, LLM calls, tools, tokens |
| 5. The invoice, 45 s | *Azure billing: cost by product* | "At the end of the day, the invoice. Azure billed about 3.9 euros; my estimate from tokens was about 5.9. The estimate is an upper bound: it cannot see the cache, and agents re-send the same context all the time, so Azure bills most of those tokens at a fraction. And look: the plumbing that watches the model costs more than the model." | billed vs estimated (say the live ones: 18 Oct was 3.87 vs 5.91); the monitoring (8.19 over 14-18 Oct) |
| 6. The alert, 45 s | *Alerts* (all statuses), then the rule | "Remember the fat prompt? This rule looks at the last five minutes, every minute: any call over 10,000 prompt tokens. It is active right now. The alert comes before the bill, not after." | the active alert, the rule's ES|QL query, the start time |

Close: "Context is an engineering resource. Choose it, measure it, alert on it."

**Transitions.**
- 1 to 2: "That was our app. What does Azure say?"
- 3 to 4: "Models are one thing. Agents multiply the calls."
- 4 to 5: "All of that costs money. Here it is."
- 5 to 6: "A bill arrives tomorrow. How do I know today?"

**Do not say.**
- A single call is faster: the win is tokens and cost.
- The invoice is real time: it arrives the next day.
- The Context Engine is generally available: it is a private preview.

**If something fails.**
- Empty dashboard: Foundry Overview is 5-10 minutes behind; skip and come back.
- Alert not active: open *Alerts* on all statuses and show the recovered ones (an alert lasts about 5 minutes).
- Slow Kibana: console in Practice and the saved screenshots.

**Setup.**
Six tabs in this order: Scoreboard, Azure usage, Foundry overview, Agents, Billing, Alerts. Dashboards on Last 1 hour (Billing already stores 13-23 Oct), browser zoom 125%, notifications off.
Numbers come from 18 Oct (see `docs/RESULTS.md`); say the live ones.

## Close (38-41 min, slide 9)
Show the filled scoreboard.
> "Three messages. One: right context beats more context. Two: tokens and cost are measurable, on your own data. Three: you can see it, so you can fix it."
> "The repo is yours after the event."
Table: hit@1 75 to 100; Q06 tokens 13,649 to 7,815; latency about the same; HERO agents 1 of 5 to 5 of 5.

## Q&A (41-45 min, slide 10)
Show slide 10 (Q&A, with the Einstein illustration) as soon as you finish the close. The quote on it is attributed to Albert Einstein.
> "Ask anything. Or type a contract id into the lab and try to break it."
- Context Engine: private preview, say "experimental". The agent result uses our lookup tool on top of the AI index.
- Latency: single call about the same; agents get faster because they make fewer calls.
- Cost: the live number is an estimate from tokens times the public price list (0.726 / 4.356 euro per million in / out for gpt-5.4-mini); the invoice arrives the next day and is lower than the estimate when caching kicks in (agents: about a third lower on 18 Oct).
- Data: synthetic; the deployment is Data Zone EU, not "stays in Germany". The repo goes public after the event.
- Which questions can the room try? Any contract id in the lab.

## If something fails
| Symptom | Do |
|---|---|
| 429 or hang | wait 60 s, or `M` for Practice; say "rate limit, this is why we observe" |
| An agent gives a wrong answer | it happens, mostly to the baseline (HERO 1 of 5 right): it is the point; press `R` or `M` |
| Kibana slow | stay in the console, Practice, saved screenshots |
| Nothing works | `python3 demo/stage.py replay all` in a terminal |

## Thank you (slide 11)
> "Thank you. Context is an engineering resource: choose it, measure it, alert on it. The repo goes public after the event."
