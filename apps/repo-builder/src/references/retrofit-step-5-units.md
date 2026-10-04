# Step 5 — Read the destination's units

Part of [Retrofit](retrofit.md). Derive units from what the destination already delivers; never interview the operator for them, since an answer can contradict the tree.

**A unit is what the repository delivers on its own**: separately built, or separately installed by its own delivery path. Neither half alone qualifies: a built directory nothing delivers is a build artifact of one unit; an installed directory nothing builds separately is content. Per candidate unit, name the evidence for each half from the destination's files: manifest build targets and workspace members, image or artifact names in container and packaging files, services its deployment descriptors install, entry points its scripts invoke.

**The name comes from the first source that exists**: the unit's directory, the built artifact or image name, the package name, the repository name. Kebab-case it and cite the source. The operator may rename anything; a rename is the confirmed name from then on.

**The run and ship facts are not on disk and are never inferred silently** (one `main` package can be a CLI, a TUI, or a service). Name the evidence per unit, propose a pair, and have the operator confirm or correct each. Both the evidence and the confirmation go into the report and the architecture record, so observed and accepted facts stay distinguishable.

**Read what grades the pair before proposing it.** Three payload files in the candidate decide it:

- `scripts/libs/quadlet.sh` refuses `ships: quadlet` unless the unit's `deploy/quadlet/` holds a `.build` unit naming an `ImageTag` that every sibling `.container`'s `Image=` resolves to.
- `scripts/libs/detect.sh` holds one `_capability_package_<language>` per language that can ship an executable.
- `scripts/run` detects languages only after entering `apps/<unit>/`, so a `run` other than `none` needs a manifest at that path, not at the root.

Where the confirmed pair and the check surface disagree, report the disagreement as a finding; do not soften the value.

**A language with no packaging adapter declares `ships.kind: none`, and the gap is reported**: the unit, its language, and the missing adapter. A guessed kind makes `scripts/package` fail against the unit.

**Domains are drawn only where the destination already draws an internal boundary under one delivery.** A unit that builds and installs as one thing has no domains, however many directories it has.

**A deployable the destination declares but does not build is not a unit.** A pulled third-party image or a registry-installed service goes under the unit owning the descriptor that names it, and is reported as a deployable the unit model does not describe. It is a finding, not a stop.

**The map is the operator's to confirm.** Present every proposed unit with: its name and the name's source, the evidence for each half of the delivery test, the proposed run and ship pair with its evidence, any domains with each boundary, and every declared-but-not-built deployable. A rejected map with no correction stops the flow and is reported.

**This step moves nothing**: no `apps/<name>/` created, no tree relocated, no `.unit.json` written. Step 6 owns every move; [step 7 writes the record and the declarations](retrofit-step-7-bar.md#the-records-and-the-collisions) against settled paths.

## What the decomposition record will say

Step 7 writes it; its content is decided here.

- **One record covers the whole decomposition**, not one per unit as [generate's Step 7 — Derive the application boundaries](generate.md#step-7--derive-the-application-boundaries) writes. `docs/adrs/0005-stage-a-retrofit-locally-and-write-the-host-last.md` records why.
- **The choke point is stated as observed, not chosen**, per unit. Record *none of these bind* as a finding rather than omitting it, so an absent constraint is distinguishable from an unmeasured one.
- **Existing architecture records are normalized to the payload's frontmatter**, carrying corresponding destination fields across. Leave `generated` empty: the retrofit relocated the decision, not authored it. Fill every field the payload ADR template has and the destination's ADR lacks, not only `status` and `tags`, only from evidence in the ADR itself; with none, use the template's default for it (`status: proposed`, `tags: []`) and report the field as defaulted. Location: [Architecture records live at the root documentation path](lifecycle.md#architecture-records-live-at-the-root-documentation-path).
- **The manifest records unit names and nothing else**, per [Manifest](lifecycle.md#manifest). Run and ship facts live in the unit declarations; the evidence lives in this record.
