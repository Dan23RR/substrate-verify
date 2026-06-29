# VeriVault — sound audit certificates for ERC-4626 vaults

> **Point VeriVault at a vault. Get a certificate that *executes* the attack — and proves the answer.**

| | |
|---|---|
| **VULN** | the exact exploit, **executed** on a fork — witness: attacker profit (wei) |
| **IMMUNE** | the **executed proof** the attack cannot profit — witness: max profit ≤ 0 |
| **ABSTAIN** | declared, with a typed reason. **Never a guess.** |

Every verdict ships a **re-runnable proof** and a **signed, portable, tamper-evident certificate** (content-hash + HMAC). Anyone can re-execute the witness and check the hash. No trust required.

---

## The problem we solve (measured, not claimed)
We pointed a swarm of **10 independent LLM smart-contract auditors** at real ERC-4626 vaults, using VeriVault's execution gate as ground truth. The LLM auditors:
- **unanimously (10/10) flagged a genuinely-safe vault as vulnerable** — a false alarm that wastes audit hours and blocks safe deployments;
- **missed a version-specific vulnerability 40% of the time** (OpenZeppelin 4.8, pre-virtual-shares);
- while VeriVault's execution gate was **sound in both directions — 0 false positives, 0 false negatives — with a re-runnable witness** (`+25e18` / `+100e18` on the vulnerable cases; negative max-profit on the safe ones).

**The lesson:** a verdict you can't execute is a verdict you can't trust — *in either direction.* AI auditors (and humans) over-flag safe code and miss version-specific bugs. **VeriVault is the sound second-opinion filter that runs the attack and hands you the proof.**

The class it covers — donation / first-depositor inflation — is the live one: **Mountain Protocol** (wUSDM, −$716k, Feb 2025), **Resupply** ($9.56M, Jun 2025), Sonne / Hundred / Onyx (empty-market).

---

## What you get — try it in 30 seconds
```bash
pip install -e .
verivault demo                                  # 2 real audits: a VULN + an IMMUNE, with signed certs
verivault audit MyVault.sol --sign $SECRET --out cert.json    # ANY IVault ERC-4626 vault — auto-wired, no config
verivault audit --onchain 0x… --rpc $ETH_RPC_URL # audit a DEPLOYED vault (mainnet-fork)
```
Real output (from `verivault demo`, reproducible):
```
  CERTIFICATE — VaultBalanceOf.sol
  VERDICT     : VULN (exploit EXECUTED)
  WITNESS     : max_attacker_profit = 24999999999999999999 wei   (re-runnable via forge)
  content_hash: b68514ab…   signed: yes
```
See real signed certificates in [`docs/demo_certs/`](docs/demo_certs/) — a vulnerable and an immune vault, each with its executed witness.

*Self-contained: the forge execution gate (faithful harnesses + upstream libs) is **bundled in `verivault/gate/`** — `verivault audit` needs only [Foundry](https://getfoundry.sh) (`forge`), no external repo or API.*

---

## The moat — what nobody else sells
LLM proposes → **deterministic forge execution gate disposes** → REFUTED never emits → certificates compose.
1. **The sound NEGATIVE.** Not just "here's an exploit" (every tool does that) but a **certificate of immunity**: sweep the donation against the measured virtual-offset; if no donation up to *k×* the victim deposit profits, emit IMMUNE + the executed proof. **No one else sells proof-of-SAFE.**
2. **A deep ERC-4626 vertical** (totalAssets accounting, virtual-offset, dead-shares, rounding-direction) with typed facts.
3. **Calibrated 3-way output** `{VULN+PoC | IMMUNE+proof | ABSTAIN+reason}` — the honesty is the differentiator.

---

## Honest scope (this is the product, not a disclaimer)
- Covers the **donation / first-depositor inflation** and **rounding-direction** classes. **ABSTAIN — never false-pass — outside.**
- **Source flow:** **any IVault-compatible ERC-4626 vault, fully automatic** (no `--key`) — deterministic faithful-harness generation, no LLM, no API. Verified **FP=0 / FN=0 on 7 vaults including unseen contracts** and 3 constructor styles (Solmate / OpenZeppelin / Solady). Non-standard interfaces → honest ABSTAIN.
- **On-chain flow:** `--onchain <addr>` needs an archive RPC; **abstains, never fakes,** without one.
- The learned *scorer* is a cost-router (NO-GO as an autonomous gate, by design and pre-registered). The **execution gate is the sound adjudicator** — that's the whole point.

---

## Evidence (every number from a runnable script)
- `python verify_all.py` → **ALL GREEN, 24 checks** (16 Python + 8 forge).
- Labeled benchmark: **recall 100% / precision 100%, FP=0 / FN=0** on real vaults (Solmate / OZ v5 offsets / OZ 4.8 / Solady).
- Live: **22 mainnet vaults**, one fork ~40s, **FP=0**.
- Real-incident capture: Compound v2 empty-market (Sonne $20M / Hundred $7.4M / Onyx $2.1M class), full victim deposit stolen, witness executed.

---

## Who it's for
- **Risk curators** (Morpho / Euler vault curation — Gauntlet, Steakhouse, Block Analitica, Re7): continuous, sound re-certification per vault, with a re-runnable proof.
- **Audit shops & solo auditors:** a sound filter over noisy LLM-auditor output + a deliverable **proof-of-safe** certificate.
- **Protocols pre-launch:** an executable immunity certificate to publish.

---

## How to engage
- **Free demo cert** on a vault you care about — send the address or source; you get a signed certificate back.
- **Pilot:** continuous certification on your vault set (per-vault or subscription).
- Contact: `[ADJUST: Daniel Culotta — X / email]`.

*VeriVault is the verification brick of Verifier Labs. Methodology and numbers are script-reproducible; code available for review.*
