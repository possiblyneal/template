# Wayfinding

Generation has to know how many applications the repository holds, what each is called, and what each is written in. Those are not preferences to collect. They follow from the decomposition in [`choosing_a_language.md`](choosing_a_language.md), and wayfinding derives them with the user.

It is short by default — two questions asked once — and hands the decomposition to `/wayfinder` only where the short form fails to settle something. That handoff ends the generate and turns a build into a planning effort, which is a real cost to put in front of someone who asked for a repository, and most repositories do not need it.

Run it at [Generate](generate.md) step 7 — after the candidate is materialized, the destination repository exists, and step 6 has configured where that repository tracks its issues, and before the candidate is personalized. Step 8 is the first thing that reads the result, so that is the last position where the question can still be asked and the position at which a stop has banked the most; `docs/adrs/0003-order-the-repository-ahead-of-wayfinding.md` has the reasoning. Skip wayfinding only when the invocation already names every deployable and its language, and say so in the final report — a supplied name and a derived one are identical on disk, and only the derived one has an ADR behind it.

## The short form

Do not open a full Event Storming workshop to create a directory. Ask the two questions that decide `apps/`, in one structured prompt, with your own reading of the request as the options:

1. **What ships separately?** Offer the candidate decompositions the request supports — one service; a client and a server; an API and a worker — and name what each would be called. This answers how many `apps/<name>/` directories exist and what each is.
2. **What binds first, for each of those?** Offer the five constraints from the reference — browser or device execution, deployment glue, an ecosystem only one language has, many long-lived connections with per-connection flow control, a hard memory or hardware limit — plus *none of these bind*. This answers the language.

Propose, and let the user dispose. That is the reason for putting your reading into the options rather than asking open questions: a proposal the user can see and reject has been tested, and an assumption you made silently has not. But the options are a shortcut, not the answer — *Other* is the load-bearing choice here, and a split nobody picked off the list is the ordinary outcome for anything the request did not already spell out.

Two answers close the session for most repositories. Take the names from the decomposition, confirm them as kebab-case, and go.

## When to hand off

The short form is a path through [`choosing_a_language.md`](choosing_a_language.md), not a replacement for it. It works when the user can already say what ships. When it does not, the remaining work is the full method — Steps 1 through 6, one step per exchange, applying each test as the reference gives it — and that is `/wayfinder`'s job rather than this skill's. Stop the generate and hand off when any of these holds:

- the user rejects every offered split and describes one the request does not obviously support, which means the boundary is the open question rather than the naming;
- more than one constraint is selected for a single deployable and which one is tightest is not settled by what that deployable promised at its seam;
- two proposed deployables turn out to need the same concept under different meanings — the reference's Speaker case, where the boundary is what is actually in dispute;
- the repository is being designed rather than described: the user can say what the software should do but not what ships.

The value of that session is concentrated in the places where the first answer was wrong — a UI event mistaken for a domain event, a noun that turned out to be a field on an aggregate rather than an aggregate, two aggregates that looked like one until asked whether either could change alone. Only the user can produce those corrections, which is why the method is worth a separate effort rather than a longer prompt.

## Handing off to `/wayfinder`

`/wayfinder` charts the open decisions as a map of tickets and then works them one at a time, with the user answering each. Invoke it with the Skill tool to chart, supplying:

- **Destination** — for every deployable a kebab-case name, its choke point, and the language that constraint selects. That is `/wayfinder`'s destination in its own sense: what reaching the end of the map looks like, and the edge past which further decomposition is out of scope for this generate rather than fog still ahead of it.
- **Notes** — [`choosing_a_language.md`](choosing_a_language.md) as the method every ticket session runs on, one step per exchange; the short-form answers already given; and which of them came apart, since that is where the map starts.
- **Nothing about where the map lives.** `/wayfinder` reads `docs/agents/issue-tracker.md` and charts against whatever that file records. The payload ships it at that path, and [Generate](generate.md) step 6 confirms it and creates the labels it names against a repository step 4 already created. Do not name an effort directory and do not override the choice. Why the repository comes first is in `docs/adrs/0003-order-the-repository-ahead-of-wayfinding.md`.

Charting is where the generate ends. `/wayfinder` resolves nothing while charting and never works more than one ticket per session. Do not work a ticket, and do not answer any of the six steps yourself; `docs/adrs/0003-order-the-repository-ahead-of-wayfinding.md` records why.

So report `stopped` with the pull request not created, leave the materialized candidate and the created repository in place, and hand back two things: the map, and the resume. The user works the map with `/wayfinder` across as many sessions as it takes, then re-invokes `/repo-builder` against the same candidate once the map has no open tickets, and not before. The destination handed to `/wayfinder` is the decomposition itself, so an open ticket is a piece of it still undecided. It re-enters at [Generate](generate.md) step 8 and reads the decomposition out of that section.

## What wayfinding must produce

For every deployable, whether the short form settled it or a map did: a kebab-case name, the constraint identified as its choke point, and the language that constraint selects.

A map additionally produces the context each deployable belongs to, and for every seam the two contexts and the contract between them. The short form does not, and must not invent them — a context named without the aggregates under it is a label, and a seam contract asserted without asking is the preference-justified-after-the-fact this section exists to prevent.

The number of deployables is the number of `apps/<name>/` directories to create. It is not the number of contexts. The reference names collapsing context, deployable, and language choice as the most common way the method gets misapplied, and this is the step where that collapse would happen.

## Recording the outcome

Write one ADR per deployable under `docs/adrs/`, copied from `0000-template.md` and numbered from `0001`. Set `scope` to `apps/<name>` and the `lang:<language>` tag, state the choke point in **Context** — with the seam contract behind it when a map established one — and record in **Alternatives Considered** the constraints that were checked and did not bind.

Set `status: accepted`, not the template's `status: proposed`. Generation acted on this decision: the directory exists and the language is chosen. Shipping it as a proposal describes a deliberation that already concluded, and leaves every generated repository with a decision log nobody appears to have agreed to.

That last part is the reason for writing any of this down. A constraint checked and found not to bind and a constraint nobody looked at are indistinguishable a year later, and the ADR is the only thing that can tell them apart. The short form's *none of these bind* is exactly such a finding, and it reaches the ADR as one.

Say in **Context** how the choke point was established: chosen from the short form's list, reasoned from the seam contract, or measured against it. The reference's one reversal turned on that difference, and the weaker the footing the sooner the decision is worth revisiting.
