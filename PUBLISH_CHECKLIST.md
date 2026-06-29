# PUBLISH CHECKLIST — read before going public

> This folder is a **staging skeleton**, not the code. It holds the public-facing wrapper (README, LICENSE, .gitignore, CI, docs, citation) plus this gate. You drop the real kernel in, scrub it, and publish. Do this carefully: once it is public and indexed, a leaked secret or an overclaim is hard to take back.

## 0. Name it
Pick the public repo name (placeholder used here: `substrate-verify`; alternatives: `veridict`, `certkernel`, `exec-verify`). Update the title line in `README.md` and the `repository-code` URL in `CITATION.cff`.

## 1. Drop in the code (placement)
Copy from your local working dirs into this skeleton:

| From | To | What |
|---|---|---|
| `substrate_core/` (kernel, adjudicators, smt, signing, lattice) | `src/` | the trusted kernel |
| `verivault/` | `verivault/` | the ERC-4626 exec-gate vertical |
| labelled corpora (regex GitHub set, vault bench, netacl ACLs) | `benchmarks/` | reproducible inputs |
| signed example certs (`.scar`, `docs/demo_certs/*.json`) | `examples/` | rerunnable certificates |
| the browser verifier (`verifier/`, `audit_regression/conformance_check.js`) | `verifier/` | no-install certificate checker |
| `verify_all.py`, `audit_regression/` | repo root | the reproducible suite |
| `grants/outreach/public_writeup_FINAL.md` | `docs/WRITEUP.md` | the public write-up |

Keep a `pyproject.toml` so `pip install -e .` works.

## 2. Remove the 4 cosmetic overclaims (from the audits) BEFORE publishing
These are the only things the two adversarial audits flagged. Fix them in the code/docs you copy in, not just here:
- [ ] **"128 all green"** anywhere in code/README. On a clean clone the real number is ~118 pass / 3 skip / 1 fail. Either fix the skip-vs-fail orchestration so the suite is genuinely green, or state "~118 deterministic checks + honest skips". This README already states it honestly; make the code match.
- [ ] **`issuer_authenticated: True`** — the real offline value is `False` (signature valid, issuer not authenticated without a pre-trusted root). Downgrade the label.
- [ ] **The ghost filename `g1_exploit.json`** — does not exist; the real artifacts are `normaai_g1.scar` + `normaai_g1_transcript.json`. Remove the dead reference.
- [ ] **`'proven'` stamped on fuzz/bounded results** — relabel bounded-exhaustive as `bounded`, sampled as `empirical`. Never `proven` for non-universal evidence.

Also: do **not** add a `cvc5 false_proven=0` claim (only Z3 is on disk), do **not** claim a source-to-certificate binding (absent), do **not** present the RLVR/witness thesis as settled (still open).

## 3. SECRET SCAN (the one that can really hurt you)
- [ ] No Ed25519 **seed / private signing key** committed. Publish only **public** keys and signed certificates. The `.gitignore` here excludes `*.seed`, `*signing_key*`, `*.pem`, `*.key` — verify your real filenames are covered.
- [ ] No `.env`, no API keys, no RPC URLs with embedded tokens, no Resend/Gemini/Groq/Alchemy keys anywhere in the tree.
- [ ] **Start a FRESH git history.** Do `git init` in the published copy. Do NOT import an existing `.git` that may carry a removed `.env` or key in history. (A removed secret still lives in old commits, and a public repo exposes them.)
- [ ] Run a scanner before the first push, e.g. `gitleaks detect` or `trufflehog filesystem .`.

## 4. Sanity-run on a clean clone
- [ ] In a fresh checkout: `pip install -e . && python verify_all.py`. Confirm the output matches what the README claims (~118 green + honest skips). If it does not, fix the README or the code so they agree. Do not publish a README that overstates the suite.
- [ ] Open `verifier/` in a browser, drop in one example certificate, confirm it validates, then tamper one byte and confirm it goes red.

## 5. Polish the front door
- [ ] `LICENSE` year and name correct (2026, Daniel Culotta).
- [ ] `README.md` title = chosen repo name; results table numbers match `docs/WRITEUP.md` exactly.
- [ ] `CITATION.cff` DOIs correct: RoPE `10.5281/zenodo.19899195`, Behavioral Trust Clustering `10.5281/zenodo.20028123`.

## 6. Publish
- [ ] `git init`, `git add .`, commit, create the public repo, push.
- [ ] On your GitHub profile, **pin** this repo (and re-pin snc-core + AION-Nexus; drop the empty sos-paradigm pin).
- [ ] Update the profile README line "a verification layer ... open-source release soon" to link the now-public repo.

## 7. Then, and only then, ship the write-up
- [ ] Post `docs/WRITEUP.md` to LessWrong / AI Alignment Forum, and mirror as an arXiv note (cs.LO primary). Add the references listed at the end of the write-up.
- [ ] You now have a real, runnable thing to point to. Send the **short summary + repo link** to Coefficient Giving when they come back (~6 Jul), and use the same link in the ARIA and Blue-Team threads.

---
**Order matters:** secret scan and overclaim removal (steps 2-3) come *before* the first public push. Everything after is reversible; a leaked key in public git history is not.
