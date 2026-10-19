# Speech script, start to finish (45 min, English)
"RAG is Broken: How Elastic & Azure Fix Context, Latency, and Token Bills" · AI Dev Night with Microsoft and Elastic · Köln, 22 Oct 2026, 19:30.

How to use it: read it aloud once, then keep it nearby. Lines in plain text are what you say. *Italics in brackets* are what you do. `[SLIDE n]` and `[CONSOLE]` mark where you are, in the order of the deck (`DevNight_Opening_v5.pptx`, 11 slides).
The cheat sheet with all the numbers, the "if something fails" table and the console keys is `docs/TALK_SCRIPT.md`. The running order with timers is `python3 demo/stage.py show`.
Numbers are from 14 and 18 Oct. If the live number differs, say the live one.

| Min | Part | | Min | Part |
|---|---|---|---|---|
| 0-3 | Slides 1-2: bridge, the bet | | 18-30 | Act 2 (console) |
| 3-6 | Console: the reveal | | 30-38 | Act 3 (slide 8, Kibana) |
| 6-7 | Slide 3 | | 38-41 | Slide 9: close |
| 7-10 | Slides 4-7 | | 41-45 | Slides 10-11: Q&A, thanks |
| 10-18 | Act 1 (console) | | | |

---
## 0:00 [SLIDE 1] Walk on (30 s)
*Walk on while the slide is up. No introduction about Elastic.*
Good evening, Köln.

## 0:30 [SLIDE 2] The bridge and the bet (2.5 min)
Mike just showed you how to make agents safe. Which is the right first problem. Now comes the second one: what do they cost, and how do you know they are right?
Let's make it concrete, with a bet. A very simple question, and I want a number from you.
How many tokens does a naive RAG send to Azure OpenAI to answer one question? One question. Not a hundred, not a day: one.
*Take two or three guesses from the room. Write the closest one down. Do not show the console.*
Closest guess wins. We'll find out in a minute.

## 3:00 [CONSOLE] The reveal (3 min)
*Switch to the console: Try the demo, Act 2, Naive RAG on the HERO question. Live. Press run.*
This is a naive RAG, the one in most tutorials: take the question, find the three closest documents, paste them whole into the prompt, ask the model.
*While it runs (8-10 seconds):* Who is closest? Keep your numbers, it's coming.
*The result appears.* **7,591 tokens.** Three whole contracts, about thirty-eight thousand characters. And it cost about one cent.
So the bill is not the problem. Look at the answer. It is confident, it is long, and it is wrong. *Point at the five key facts, none in the prompt.* None of the five facts we need is in this prompt. It lists suppliers more or less at random, and it never mentions a group called Veltrano. We'll meet them in a minute.
*Optional, key D:* These are the three documents it picked. None of them is one we needed.
The hidden risk sits in news and in registry extracts, in other languages. More context did not find it. Cheap and confident is the worst combination.
*Back to the deck.*

## 6:00 [SLIDE 3] What you just saw (1 min)
So yes, the title is a provocation. RAG isn't dead: grounding the model in your data is the right idea. Naive RAG is broken, and you've just seen it. Chunk, embed, top-k, paste it into the prompt: it works in a demo and it breaks in production, and nobody can see why. Tonight is about fixing that. And the fix isn't a bigger model. It's better retrieval.

## 7:00 [SLIDE 4] Apex (45 s)
Our test bench is Apex Conglomerate. It is synthetic, realistic, and messy. Like your data.
Nine thousand documents, fifteen indices, five languages. Third-party risk, operations, customers and payments, pharma and security. Tonight's crime scene.

## 7:45 [SLIDE 5] The question (1 min)
And here is the question we will chase all evening: *read it.* Which of our suppliers could expose ApexPharm to compliance risk, and what do our contracts let us do about it?
The answer is not in one place. A press release in German, news in Italian, a registry extract in Hungarian, three contracts, the supplier master data, and two versions of the same policy, one of them stale. Ten-plus documents, four indices, three languages, and one stale policy that says the opposite.

## 8:45 [SLIDE 6] Three ways RAG breaks (45 s)
RAG breaks in three ways, and they are our three acts.
Act one: the wrong context. The vector can't tell one contract number from its neighbour, and a stale policy ranks second.
Act two: too much context. Whole contracts to answer a one-clause question, and agents that rediscover everything on every run.
Act three: invisible context. You don't know what it costs, how long it takes, or whether the answer is right.
This table is empty on purpose. At the end of the evening, we fill it in, with numbers we measured tonight.

## 9:30 [SLIDE 7] What is running tonight (30 s)
Quickly, what is running on this stage. Everything is live, in Azure in the EU, on Microsoft Foundry with Azure OpenAI, running GPT-5.4 mini. Two Elastic Serverless projects: one for data, hybrid search and the Context Engine; one for observability. And this console, instrumented with OpenTelemetry, so every token is visible.
*Leave slide 7 on screen, then switch to the console, Try the demo, Act 1. Live.*

---
## 10:00 [CONSOLE] Act 1: the wrong context (8 min)
Open Under the hood (key `D`) on the first two examples.

### Contract 0117 versus 0171 (4 min, the main example)
Two contracts, one digit apart. I ask for the termination notice of 0171.
*Run Q02. Show the three cards.*
Three ways to search. Keywords: right. Hybrid: right. Semantic, vectors: wrong. It returns another contract, with confidence.
*Under the hood.* Look at these scores: 0.773, 0.767, 0.759. To an embedding, these two identifiers are almost the same string, so the ranking is decided by a hair. And the contract we asked for isn't even in the top twenty.
Keywords find it, because the whole identifier is one token in a dedicated field. And hybrid finds it too: this third leg of the query is an exact match on the identifier.
Identifiers are facts, not similarities.

### The opposite case (2 min, Q01)
You may be thinking: so keywords are the answer. Let me show you the opposite.
*Run Q01.* Same kind of question, an identifier in it, and now it is BM25, the keywords, that gets it wrong.
*Under the hood.* The rare word "changes" scored 6.82. The exact identifier, 5.04. BM25 weighs a rare word as much as an identifier. And the vector is first by 0.004: right, but by luck.
No single mode wins. That's why we fuse them, and why we keep an exact leg.

### Two policy versions (1 min, Q03)
*Run Q03.* Everyone returns the right policy first. But look at second place: version 1.0, the one with the forty percent threshold. *Point at the label "older version, superseded".* A model that mixes the two tells you there's no action needed.
Relevant is not the same as valid. Search doesn't know a document has expired. Metadata does: the lifecycle status.

### Veltran versus Veltrano (1 min, Q04)
*Run Q04.* Last one, quickly. Veltran Logistik is a family business. Veltrano Holding is the group we'll meet in a minute, and the names are almost identical. The right document is first, but its neighbours are other companies. Names are not meaning.
*Close of Act 1:* Hit at one, on these four questions: keywords seventy-five percent, vectors seventy-five, hybrid one hundred. Nobody wins alone.
*(Skip Q05, the German control, unless someone asks about other languages.)*

---
## 18:00 [CONSOLE] Act 2: too much context (12 min)

### The cost of context (3 min, Q06)
Remember the bet? One question, 7,591 tokens, cheap and wrong. Now a question where the size of the prompt really hurts.
*Run Compare Q06: change-of-control obligations in the Rheinchem agreement.*
Same question, same model, same data. Only the context changes.
Naive: thirteen thousand six hundred tokens. Engineered: seven thousand eight hundred. Minus forty-three percent in tokens, minus thirty-six percent in cost, and both answers are correct. For ten thousand questions, that is about a hundred and ten euros against seventy.
*Under the hood.* The naive prompt pastes three whole contracts, and the one we need is third in the pile. The engineered one keeps only the best fragments of the top documents.
And before somebody asks: for a single call, the latency is about the same. The length of the answer dominates. The win is tokens and cost.

### The wrong context lab (3 min)
Now the part where you can break it. Give me a contract number.
*Type the id someone shouts, or use APX-MSA-2022-0388. Ask.*
The truth is read from the contract itself, clause 15.3, so we can check every answer.
Naive RAG: wrong. Engineered: right. I ran this on eight contracts. Naive RAG got one right, and that one is the control, the contract that happens to be among the three documents the vector always returns. It pulls the same near-duplicates whatever you ask, and then it answers, with confidence, with the number of another contract. Engineered: eight out of eight.
A confident answer about the wrong contract is worse than no answer.

### Agents (6 min)
Last piece of this act: agents. Same model, same tools, same instructions. The difference is one thing: one of them has a prepared index, the Context Engine.
*Open Agents: baseline against Context Engine. Click Run both. Talk while they run (10-40 seconds).*
While they work: the question is the one we started with, the compliance risk. The baseline has to discover everything by itself. The other one asks the index first.
*When the results appear. Under the hood.* Look at what the baseline did: it searches the contracts supplier by supplier, around ten tool calls, over and over, and it never finds Veltrano. The other one makes one call: a hybrid query on a set of precomputed knowledge indicators, with the ownership groups and the spend share.
I ran this five times. The baseline found all the facts once. The Context Engine agent, five times out of five. Medians: a hundred and forty thousand tokens down to twenty-five thousand, twenty seconds down to four, fourteen LLM calls down to two.
So, honestly: it works in most runs, not in all. This is a private preview, and the agent uses a lookup tool of ours on top of the AI index. It's a workaround, not the default. But the direction is clear.
*If the first run fails: press R, or M for the recorded run. "That happens: it is the point of tonight."*
*Optional, if time allows:* Another question: which share of critical spend sits with a single group? Thirty-two point five percent. The baseline got it four times in five, after about eighteen calls and a hundred and seventy thousand tokens. The Context Engine: five in five, two calls, twenty-four thousand tokens.
Same question, same model, same data. Only the context changed.

---
## 30:00 [CONSOLE → SLIDE 8] The alert, then the map (1 min)
Act three. Before anything else, one thing.
*In the console, Dashboards and the alert, press Fire the alert now.*
I just sent one deliberately fat prompt to Azure. Keep it in mind, we'll come back to it.
*Switch to slide 8 while the alert warms up.*
While that happens, one slide to answer a question you will get: where does each number on the scoreboard come from? Five sources, five paths, two Kibanas. The console sends OpenTelemetry traces: tokens, latency, cost, accuracy per call. Agent Builder traces its own runs. Azure gives us metrics, one log record per model call through an Event Hub, and the billed cost the next day. Every number has an address.

## 31:00 [KIBANA] Six beats (7 min)
*Six tabs, in this order.*

**1. Our code (2.5 min), Scoreboard.** Everything we ran in the last twenty minutes is here, measured by OpenTelemetry in our own app. Same question, same model: the naive prompt about eleven thousand tokens, the engineered about seven and a half. That's the cost per question, and this is the cost for ten thousand questions. And the hit-at-one bars from Act one. *Point at accuracy: "x of y judged".*

**2. Azure, from its logs (1 min), Azure OpenAI usage and cost.** Now not our code: Azure's own logs, one record per model call, through an Event Hub into Elastic. Average latency around a second and a half, but the 95th percentile is about three times that. Those are the agent calls, with tens of thousands of tokens each.

**3. Azure, from metrics (30 s), Foundry overview.** The same story from Azure Monitor metrics. A different source, a few minutes behind. We reconcile three views of the same call.

**4. The agents (1.5 min), Agents, then [Elastic] Agent Builder Overview.** An agent that rediscovers everything pays for it: the baseline about fourteen LLM calls, twenty seconds, a hundred and forty thousand tokens. The one with the prepared index: two calls, four seconds, twenty-five thousand tokens. And this other dashboard comes out of the box with Agent Builder.

**5. The invoice (45 s), Azure billing.** At the end of the day, the invoice. Azure billed about 3.9 euros; my estimate from tokens was about 5.9. The estimate is an upper bound: it can't see the cache, and agents re-send the same context all the time, so Azure bills most of those tokens at a fraction. Say the live numbers. And look: the plumbing that watches the model costs more than the model. Observability is not free, and I'd rather tell you.

**6. The alert (45 s), Alerts, all statuses.** Remember the fat prompt? This rule looks at the last five minutes, every minute: any call above ten thousand prompt tokens. It is active right now. *Open the rule: the ES|QL.* The alert comes before the bill, not after.
*If it isn't active yet: show the recovered ones, "an alert lasts about five minutes".*

Context is an engineering resource. Choose it, measure it, alert on it.

---
## 38:00 [SLIDE 9] The close (3 min)
*Back to the deck: the table we left empty is now full.*
Three messages.
One: right context beats more context. Hit-at-one from seventy-five to a hundred percent. A prompt forty-three percent smaller, with the same answer.
Two: tokens and cost are measurable, on your own data. About the same latency for a single call, and I won't tell you otherwise. And for agents, from zero out of five to three out of five on the question that matters.
Three: you can see it, so you can fix it. Traces, logs, invoice, and an alert before the bill.
The repo is yours after the event. It even contains the answers.

## 41:00 [SLIDE 10] Questions (4 min)
Questions. And if you want to try to break it, give me a contract number.
*Answers to the usual questions:*
- The Context Engine is a private preview. Say "experimental". The agent result uses our lookup tool on top of the AI index.
- Latency: for a single call, about the same, the answer length dominates. Agents get faster because they make fewer calls.
- Cost: the live number is an estimate from tokens times the public price list. The invoice arrives the next day and is lower than the estimate when caching kicks in: for agents about a third lower.
- Data: synthetic. The deployment is the EU Data Zone, not "stays in Germany". The repo goes public after the event.

## 45:00 [SLIDE 11] Thank you
Thank you. Context is an engineering resource: choose it, measure it, alert on it. The repo goes public after the event.
