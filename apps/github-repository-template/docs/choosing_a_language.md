# Choosing Programming Languages

To assist in choosing programming languages, the software to be built needs to be broken down into deployable services or durable domain boundaries first, using Event Storming through Domain-Driven Design (DDD). By carving the system into Bounded Contexts—logical boundaries where a specific domain model and set of rules apply—you isolate responsibilities before writing a single line of code.

One example runs through all seven steps below: **Scribe**, a self-hosted meeting recorder. It captures audio in the browser, transcribes it with a local model, summarizes the transcript, and lets people share the result. The interesting part of the example is not the answers — it is the places where the first answer was wrong and what corrected it.

## Mapping Bounded Contexts

### **Step 1: Identify Domain Events**

Let’s start by identifying events i.e. things that can happen in the software. For Scribe:

- Recording Started
- Audio Chunk Received
- Recording Stopped
- Transcript Segment Produced
- Speakers Separated
- Transcript Finalized
- Summary Generated
- Action Item Extracted
- Note Shared
- Transcription Failed

Two of these are worth pausing on, because the pause is the lesson.

“Record Button Clicked” was on the first list and got cut. It is a UI event, not a domain event — the business does not care how the recording started, only that it did.

“Audio Chunk Received” looks like the same kind of mistake, and it survived. The test is not *how low-level does this sound*, it is *does the business have an opinion when this goes wrong*. A meeting that recorded only half of itself is a real failure that someone has to be told about, so chunk arrival is domain-visible. Keep the event, and note that this one decision reappears in Step 5 as a contract and again in Step 6 as a language choice.

### **Step 2: Find the Commands**

Next, we ask: what commands cause these events? Commands are decisions made by users.

- Start Recording → Recording Started
- Stop Recording → Recording Stopped, Transcript Finalized
- Summarize Transcript → Summary Generated, Action Item Extracted
- Share Note → Note Shared
- Correct Transcript → Transcript Segment Produced (a corrected one)

Some events are left over with no command pointing at them: Audio Chunk Received, Speakers Separated, Transcription Failed. That is not a gap in the list. Those are consequences — things the system does to itself once a command has set it in motion. A leftover event usually marks a boundary you have not drawn yet, because something on the other side of it is doing work on its own schedule.

### **Step 3: Discover Aggregates**

Alright, now the first *“DDD-definition”*: Aggregates.

An aggregate is like a cohesive bundle of *related* events and commands. So we look at the stuff we’ve collected so far and identify things that *“belong together”*.

So let’s look at “Audio Chunk Received” and “Recording Started”. The noun “Audio” could be an aggregate. But that doesn’t feel right. You never open, close, or invalidate an Audio on its own — it is always *somebody’s* recording, and it has no lifecycle you can describe without mentioning the thing that produced it. Let’s think more…

Actually, “Recording Session” makes more sense. A Recording Session can:

- Be started and stopped
- Accumulate chunks, in order, with gaps that matter
- Fail partway through
- Belong to exactly one meeting

This is an aggregate — a collection of related objects managed as a single unit with its own lifecycle. “Audio” was never an aggregate; it was a field on this one.

The next call is harder, and it goes the other way. Transcript looks like part of Recording Session — same meeting, same timeline, produced immediately from the audio. The question that splits them is whether either one can change while the other stands still. It can: a transcript gets re-generated against a better model, or corrected by a person, while the recording underneath is byte-identical and untouched. Two independent lifecycles, so two aggregates.

Run the same test on the rest and Scribe ends up with five: Recording Session, Transcript, Summary, Shared Note, and Person. Summary earns its own place for the same reason Transcript did — you can re-summarize an unchanged transcript, and people edit the result.

There is no clear-cut definition of an aggregate — you will find a hundred, none of them crisp. What carries across all of them is the test used twice above: *does this thing have a lifecycle of its own, and can it be correct on its own.*

### **Step 4: Group into Bounded Contexts**

A bounded context is simply a boundary in our big business picture. Everything in that context is somewhat related, in terms of business.

The tempting grouping for Scribe is “everything that turns audio into words” — Transcript and Summary in one context, since both are text processing. Resist it. Grouping is by business meaning, not by technical similarity, and these two do not share a model. The Transcription context thinks in time-aligned segments and voice clusters. The Insight context thinks in decisions, claims, and owners, and has no concept of a timestamp. They also change for entirely different reasons: one changes when the acoustic model changes, the other when the business changes its mind about what a good summary is.

So we group our related aggregates into bounded contexts. In Scribe:

Capture Context:

- Recording Session aggregate

Transcription Context:

- Transcript aggregate

Insight Context:

- Summary aggregate

Sharing Context:

- Shared Note aggregate
- Person aggregate

Notice how the same concept can mean different things in different contexts. A “Speaker” in Transcription is a voice cluster the diarizer labelled “Speaker 2” — it has no name, no email, and no rights. A “Speaker” in Sharing is a Person who can be granted or denied access to a note. It’s the same word but it has a different meaning depending on the bounded context.

That distinction is what stops the boundary from leaking. There is an obvious-looking shortcut where the Transcript aggregate holds real speaker names so the UI can render them without a second lookup — and it drags identity, and eventually access control, into a context whose job is acoustics. Very important: A bounded context is made up of aggregates as you see. It can be just one or it can be multiple aggregates. However, an aggregate should never ever be split across different contexts. It should be in exactly one context, fully contained.

## Choke-point Evaluation

Here is how that architectural decomposition leads directly into the choke-point evaluation:

### Step 5. Define the Seams (The Contracts)

Once the boundaries are drawn, determine how they communicate. The contracts are not all alike, and the differences between them are what constrain Step 6.

**Capture → Transcription.** This is the seam that Step 1 predicted. Audio has to arrive as an ordered, resumable stream, and a dropped chunk is a business failure rather than a retry. That forces per-chunk sequencing, acknowledgement, and back-pressure when transcription falls behind the microphone — so, bidirectional streaming over gRPC or WebSockets, and both sides must hold a long-lived connection open for the length of a meeting.

**Transcription → Insight.** Nothing streams here. Summarization runs once against a finalized transcript, and it has to survive being run twice, so the contract is an idempotent job keyed by transcript version. A queue and plain HTTP carry it. Not every seam needs the machinery the first one needed, and assuming otherwise is how a system ends up streaming things that arrive once an hour.

**Insight → Sharing.** A read-only reference by ID. The weakest possible contract, deliberately.

These contracts become hard constraints for the next step. In particular the first one now says: whatever runs Transcription must hold thousands of concurrent long-lived streams and apply flow control per connection. That sentence decides more than any opinion about languages will.

### Step 6. Evaluate the Choke Points

Every component has more than one constraint. The choke point is the **tightest** one — the one that binds first and would still bind after the others were relieved. So the rubric is a ranking, not a lookup: find every constraint that applies, then decide which one outranks the rest.

1. **A UI constraint** → TypeScript (Web), Swift (iOS), Kotlin (Android).
2. **A deployment/glue constraint** → Bash.
3. **An ecosystem/library constraint** → Python (AI/Data).
4. **A network concurrency constraint** → Go.
5. **A strict hardware/memory constraint** → Rust.

**If none of the five bind, the tightest remaining constraint is time-to-working-code.** → **Python**, or whatever the repository already runs.

That is a tiebreaker, not a sixth line, and the distinction matters. The five above are properties of the problem and they do not expire: the browser still executes the UI a year from now, and the memory limit is the same after the requirements settle. Time-to-working-code is different — it binds hardest while the shape of a thing is still in question and weakens as it stabilizes. A constraint that expires cannot outrank one that does not, because the durable one is still there afterwards, waiting. So velocity never wins a contest. It wins by default, when there is no contest to have.

Where it does win, it decides for a real reason rather than for lack of one — Python answers here for much the same reason it answers line 3: the ecosystem is already there, and there is very little between an idea and a working version of it.

**But separate two things that look identical from here: checked and none bind, versus not yet checked.** Only the first is a finding. The second is a question, and reaching the tiebreaker without having asked it is how every component in a young repository ends up in the same language — not because nothing binds, but because nobody looked. An unmeasured constraint and an absent one are indistinguishable until something measures.

The way to ask is to build the thing in whatever reaches a running version soonest, then measure it against the seam contract from Step 5 rather than against a benchmark. That is what the Transcription spike below was, and it was written in Python. So Python is often the right *first* answer on a new component — not as an answer, but as the cheapest way to put the question. The prototype's job is to find out whether line 4 or line 5 was binding all along, and to be thrown away when it says yes.

That only works while a rewrite stays affordable, which is a property of the contract and not of the code. Transcription could be rebuilt in Rust because its callers were coupled to a stream, not to a process. This is the same discipline as Step 3 and Step 4, arriving one step later: the boundaries are what let an answer be wrong without being expensive.

Applied to Scribe:

**Capture Context, browser recorder.** The choke point is browser execution. → **TypeScript**. No argument, and it is worth naming the easy one so the hard ones are visible as hard.

**Capture Context, session service.** The server side of the same context is a separate deployable with a separate choke point: holding open one long-lived stream per meeting, applying back-pressure per connection, and losing nothing when a client reconnects. That is the network concurrency line of the rubric. → **Go**. Note what just happened — one bounded context produced two deployables in two languages. Contexts are boundaries in the business, not units of deployment and not units of language choice. Collapsing the three ideas is the most common way this method gets misapplied.

**Transcription Context.** The first answer was Python, and it was wrong — but not because the constraint behind it was imaginary. The ecosystem constraint is real here: every model binding worth having is Python-first, and getting off the ground in anything else costs weeks. That is a genuine force, and it lost to a tighter one.

What outranks it is that this context does no experimentation. It runs one pinned model in a hot loop, and it sits directly behind the streaming contract from Step 5 — thousands of open connections, per-connection flow control, GPU memory that must stay resident across them. Note what the spike was for. It was not weighing developer speed against runtime speed; velocity is out of contention the moment line 5 is in play. It was establishing whether line 5 was in play at all. Built in Python and measured against the *contract* rather than the model, the process spent more of its time moving buffers between the runtime and the device than running inference, and back-pressure broke first. That settles it: memory residency binds, and it would still bind after the bindings improved. → **Rust**, with the ecosystem cost paid deliberately rather than pretended away.

**Insight Context.** Line 3 applies — the model libraries are Python-first — but check the lines above it before accepting the easy answer. None bind. There is no UI, the concurrency is a queue draining one job at a time, and the runtime cost is close to irrelevant because the work is dominated by waiting on a model, so the CPU is idle no matter which language is idle. With nothing above it binding, the tiebreaker decides, and it decides emphatically: the prompts, the extraction schema, and the definition of a good summary are all still moving, and every one of those changes is a code change. → **Python**, chosen for how quickly it goes together, with the libraries a convenience rather than the argument.

**Sharing Context.** Store a note, check who may read it, hand back a link. Nothing on the list binds — no UI, no concurrency, no hardware pressure, and no library this depends on. So the tiebreaker takes it, and here it argues mostly through cost: the tightest thing left is how long this takes to build and what it adds to the repository. Use the language already present rather than introducing another toolchain for CRUD. "Nothing above binds" is a finding, not a shrug.

**Deployment and glue.** → **Bash**.

Python appears twice in this list and was rejected once, on the same evidence each time. *AI means Python* is a reputation, not a constraint, and it is right in Insight and wrong in Transcription — the difference is what each context promised at its seam in Step 5. When a language preference and a seam contract disagree, the contract wins, because the contract is the thing one context promised another and the language is only how it is kept.

That is also why the reversal only shows up in one place. Nothing here was decided by asking which language is better at audio or at text; each was decided by asking which constraint binds first, and only Transcription had two answers close enough that the ranking had to be measured rather than reasoned.

### Step 7. Deploying the Architecture

You can maintain these isolated contexts within a single polyglot monorepo. Scribe ends up with a TypeScript recorder, a Go session service, a Rust transcription engine, a Python summarizer, and Bash holding the deployment together — compiled, run, and bundled from the same root workspace.

The polyglot cost is real and worth stating: every language present adds a toolchain that must be installed, checked, and kept working for everyone, on every run of the repository’s checks. That cost is what the tiebreaker charges against a new language, and it is why the tiebreaker exists — a sixth toolchain has to be demanded by one of the five, because nothing else in the rubric argues against adding one. Five languages because five choke points demanded them is architecture; six because one service was written on a Friday is drift.

The contracts are what make this survivable over time. When the transcription engine is later swapped — a new model, a managed GPU API that erases the hardware choke point entirely, a rewrite back into Python because the constraint evaporated — the callers do not change, because they were only ever coupled to the streaming contract.

That gives the maintenance loop its shape. When a choke point changes, re-run Step 6 for the affected context and nothing else. Steps 1 through 4 stay put, because a hosting change is not a change in what the business means by a Transcript. Re-deriving the boundaries every time the infrastructure moves is how durable boundaries get churned into ordinary services.

A choke point changes when the load arrives, too, not only when the infrastructure moves. Anything decided by the tiebreaker is the case to re-check, because it was decided by an absence: nothing above it was binding at the time. That is a fact about the load and the requirements on that day, and both move. When Insight’s summary format settles and the volume is real, the question is not whether velocity still matters — it is whether any of the five have started to bind since.

If none have, the answer stays Python, and stays right. A context that spends its life waiting on a model does not develop a runtime constraint just because it got busy. What changes is that the answer was re-derived rather than inherited.

The re-check is only cheap while the contract holds, and contracts erode quietly. Insight is reachable today because Sharing holds a reference by ID and nothing else. Let one caller reach past that into the summarizer's tables or its process, and the language stops being a property of one context and becomes a property of everything touching it. The tiebreaker's answer was always meant to be provisional; a leaking seam is what makes it permanent without anyone deciding that it should be.
