# Step 5 — Read the destination's units

Part of [Retrofit](retrofit.md). Units are derived from what the destination already delivers, never interviewed out of the operator. A repository that ships something has already decided its boundaries in its build files and its delivery path, and asking again invites an answer that contradicts the tree.

**A unit is what the repository delivers on its own**: separately built, or separately installed by the repository's own delivery path. Neither half alone is the test. A directory with its own build target that nothing delivers is a build artifact of one unit; a directory the delivery path installs that nothing builds separately is content. Name the evidence for each side per candidate unit, from the destination's own files: build targets and workspace members in its manifests, image or artifact names in its container and packaging files, the services its deployment descriptors install, and the entry points its scripts invoke.

**The name comes from the first source that exists**, in this order: the directory the unit occupies, the built artifact or image name, the package name, the repository name. Kebab-case it, and cite which source it came from. The operator renames anything, and a rename is the confirmed name from that point on.

**The run and ship facts are not on disk and are never inferred silently.** No file states `run` or `ships`: a single `main` package is a CLI, a TUI, or a service. So name the evidence found per unit, propose a pair from it, and have the operator confirm or correct each one. Both the evidence and the confirmation reach the report and the architecture record, so a later reader can tell an observed fact from an accepted one.

**Read what grades the pair before proposing it.** Three payload files decide it, all already in the candidate:

- `scripts/libs/quadlet.sh` refuses `ships: quadlet` unless the unit's `deploy/quadlet/` holds a `.build` unit naming an `ImageTag` that every sibling `.container`'s `Image=` resolves to.
- `scripts/libs/detect.sh` holds one `_capability_package_<language>` per language that can ship an executable.
- `scripts/run` detects languages only after entering `apps/<unit>/`, so a `run` other than `none` needs a manifest at that path rather than at the root.

Where the confirmed pair and the check surface disagree, the disagreement is a finding for the report, not a value to soften.

**A language with no packaging adapter declares `ships.kind: none`, and the gap is reported**: the unit, its language, and the adapter that does not exist. A guessed kind turns `scripts/package` into a command that fails against the unit it was pointed at.

**Domains are drawn only where the destination already draws an internal boundary under one delivery.** A unit that builds and installs as one thing is one unit with no domains, however many directories it has.

**A deployable the destination declares but does not build is not a unit.** A third-party image a compose file pulls, or a service a descriptor installs from a registry, lands under the unit that owns the descriptor naming it, and is reported as a deployable the unit model does not describe. That is a finding rather than a stop.

**The map is the operator's to confirm.** Present every proposed unit with its name and the name's source, the evidence for each half of the delivery test, the proposed run and ship pair with its evidence, any domains and the boundary for each, and every declared-but-not-built deployable. A rejected map with no correction stops the flow and is reported.

**This step moves nothing**: no `apps/<name>/` created, no tree relocated, no `.unit.json` written. Step 6 owns every move, and step 7 writes the record and the declarations against settled paths.

## What the decomposition record will say

Step 7 writes it; its content is decided here, where the unit map is.

- **One record covers the whole decomposition**, not one per unit as [generate's Step 7 — Derive the application boundaries](generate.md#step-7--derive-the-application-boundaries) writes. `docs/adrs/0005-stage-a-retrofit-locally-and-write-the-host-last.md` records why.
- **The choke point is stated as observed rather than chosen**, per unit, and *none of these bind* is recorded as a finding rather than left out, since an absent constraint and an unmeasured one are otherwise indistinguishable.
- **Existing architecture records are normalized to the payload's frontmatter**, carrying the destination's own fields across where they correspond. Leave `generated` empty: the retrofit relocated the decision rather than authoring it. The location is settled by [Architecture records live at the root documentation path](lifecycle.md#architecture-records-live-at-the-root-documentation-path).
- **The manifest records unit names and nothing else**, as [Manifest](lifecycle.md#manifest) directs. The run and ship facts live in the unit declarations and the evidence lives in this record.
