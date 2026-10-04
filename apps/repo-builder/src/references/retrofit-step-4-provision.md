# Step 4 — Provision the environment and the hooks

Part of [Retrofit](retrofit.md). Provision the candidate's environment from the destination's tracked lockfiles and manifests, using its own toolchain. An environment that cannot be rebuilt from tracked files is a finding against the destination; never copy one from the operator's clone, since checks passing on an unreproducible environment measure nothing.

Then install the hooks by [Working hooks in a candidate](lifecycle.md#working-hooks-in-a-candidate): it names retrofit's scope, the hooks directory's location, what an already-hooked clone owes before the key is pinned, and the verification. Read its scope list for retrofit, the only flow borrowing a hooks directory it does not own. Where the candidate carries no `.pre-commit-config.yaml`, skip the install and report hooks not-applicable.
