# The assurance model

The kernel exists to make one thing impossible: claiming more than the evidence justifies. This document explains how.

## Three verdicts

- **REFUTED** is an executed counterexample. A distinguishing string for two regexes, a draining transaction for a vault, a packet that one firewall accepts and another drops. It is sound regardless of who or what produced the claim, because a counterexample is a fact about the world. A refutation is a proof.
- **CONFIRMED** is execution-backed evidence, tagged with the assurance tier it earned. It is **not** a proof. It is only as strong as the oracle that produced it and the coverage that oracle had.
- **ABSTAIN** is a typed reason for not deciding (no spec, no RPC, out of declared bound, and so on). It is never a silent pass.

## The assurance lattice

Every verdict carries a tier, ordered:

```
none  <  empirical  <  bounded  <  proven
```

- **empirical**: executed evidence over sampled inputs (for example fuzzing). Can refute; cannot confirm universally.
- **bounded**: exhaustive over a declared, finite input bound. Sound *inside that bound only*. A bounded-exhaustive CONFIRMED is not a universal claim, and the certificate says so.
- **proven**: a solver-backed universal result (for example UNSAT over the full input space for an equivalence query).

A verdict can never be labelled above the tier its evidence earns. This is enforced in the kernel, not left to discipline. That is why overclaim is impossible to express: there is no code path that stamps `proven` on sampled evidence.

## Certificates

Each verdict serializes to a certificate that:

- is **Ed25519-signed** and **content-hashed**: tamper with it, or sign with the wrong key, and it is rejected (verified independently, including by a standalone browser verifier with no install);
- **reruns offline**: the certificate carries enough to reproduce the verdict;
- **composes weakest-link**: a system certificate is the minimum tier of its parts. Two components each individually immune but jointly exploitable under a shared dependency are caught, and the safe certificate is withheld rather than emitted.

## What a certificate does not yet do

It does not bind to the exact source that produced it. The signature covers the kernel's verdict, not a cryptographic link to a specific source revision. Closing that gap is on the roadmap; until then, treat "which code produced this" as out of scope for the signature.

## The honest boundary

The whole approach works only where the target has a checkable specification: regex semantics, vault invariants, packet acceptance, formalized rules. For outputs that do not come with a spec, the kernel abstains. Lowering the cost of obtaining a usable spec is the open research problem, not a solved feature.
