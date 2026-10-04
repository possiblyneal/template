# Step 4 — Provision the environment and the hooks

Part of [Retrofit](retrofit.md). Provision the candidate's environment from its tracked manifests — the lockfiles and manifests the destination commits, resolved by the destination's own toolchain. An environment that cannot be rebuilt from tracked files is a finding against the destination, never something to copy across from the operator's clone: a check surface that passes only against an environment nobody can reproduce measures nothing.

Then install the hooks by [Working hooks in a candidate](lifecycle.md#working-hooks-in-a-candidate), which names retrofit's scope, where the hooks directory sits, what an already-hooked clone owes before the key is pinned, and how the result is verified. Retrofit's candidate is the only one borrowing a hooks directory it does not own, so read that section's scope list rather than assuming another flow's.
