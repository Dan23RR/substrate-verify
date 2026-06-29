"""
test_correlated_failure.py — CICLO 2 (TEST): la primitiva di COMPOSIZIONE di VeriVault e' UNIVERSALE.

TESI (falsificabile): lo STESSO algebra.protocol_verdict che cattura il coupling-oracolo AMM in DeFi (+78e21 misurato,
gate/test/OracleCoupledGate.t.sol) cattura il coupling-da-CORRELAZIONE in un dominio ORTOGONALE (affidabilita di sistema),
SENZA riscrivere il kernel. Il super-additivo qui = guasti correlati da dipendenza condivisa che rompono l'union-bound.

AUTO-CONTROLLO ANTI-POESIA: i MARGINALI per-componente sono TENUTI FISSI (gaussian single-factor copula): la failure-rate
di ogni servizio e' IDENTICA nei due regimi (indipendente vs correlato). Quindi l'esplosione del guasto-di-sistema viene
SOLO dalla correlazione, non da rischi cambiati. Se i marginali driftano -> l'esperimento e' un artefatto -> KILL.

KILL-CONDITION (binaria, asserita):
  (1) marginali fissi: max drift per-componente < 0.004 tra i due regimi (altrimenti artefatto).
  (2) super-additivita reale: S = P_sys(correlato)/P_sys(indip) > 5  (altrimenti la correlazione non rompe nulla).
  (3) il kernel REGGE: protocol_verdict(indip)=IMMUNE (union-bound valido) MA protocol_verdict(correlato)=ABSTAIN
      (declassa, mai falso-IMMUNE) — STESSO algebra.py, invariato.
  (4) witness eseguito: sotto correlazione il sistema VIOLA davvero lo SLA-di-sistema (P_sys_corr > budget) -> giustifica
      il declassamento (come +78e21 giustificava monotone=False nell'AMM).
Riproducibile: `python eval/test_correlated_failure.py`  (numpy gia' presente; NormalDist da stdlib).
"""
import os, sys, math
from statistics import NormalDist
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verivault.schemas import Claim, Status
from verivault.algebra import protocol_verdict
from verivault.reliability import SlaOracle, reliability_bound

# regime: 5 servizi, p=0.05 marginale (entro SLA 0.08), guasto-di-SISTEMA se >=3 falliscono insieme (conjunction rara).
N_COMP, P, K = 5, 0.05, 3
SLA_COMP = 0.08          # budget per-componente: p=0.05 <= 0.08 -> ogni servizio e' "immune" (entro SLA)
RHO = 0.6                # correlazione da dipendenza condivisa (single-factor)
N_MC = 1_000_000


def simulate(rho: float, seed: int):
    """Single-factor gaussian copula: marginali FISSI a P per ogni rho; equicorrelazione rho. Ritorna (P_sys, rates)."""
    rng = np.random.default_rng(seed)
    thr = NormalDist(0, 1).inv_cdf(P)                      # soglia che fissa il marginale a P
    F = rng.standard_normal((N_MC, 1))                     # fattore COMUNE (la dipendenza condivisa)
    eps = rng.standard_normal((N_MC, N_COMP))              # idiosincratico per servizio
    lat = math.sqrt(rho) * F + math.sqrt(1.0 - rho) * eps  # latente standard-normale, corr=rho, marginale invariato
    fails = lat < thr                                      # guasto del servizio i (bool)
    rates = fails.mean(axis=0)                             # failure-rate empirica per servizio (DEVE restare ~P)
    p_sys = float((fails.sum(axis=1) >= K).mean())         # guasto di SISTEMA: >=K servizi insieme
    return p_sys, rates.tolist()


def main():
    print("=" * 92)
    print(f"CICLO 2 — composizione UNIVERSALE: union-bound vs correlazione (n={N_COMP}, p={P}, K>={K}, SLA={SLA_COMP})")
    print("=" * 92)
    p_ind, marg_ind = simulate(0.0, 12345)
    p_cor, marg_cor = simulate(RHO, 12345)
    drift = max(abs(a - b) for a, b in zip(marg_ind, marg_cor))
    S = (p_cor / p_ind) if p_ind > 0 else float("inf")

    print(f"marginali per-servizio (indip):   {[round(x,4) for x in marg_ind]}")
    print(f"marginali per-servizio (corr rho={RHO}): {[round(x,4) for x in marg_cor]}")
    print(f"max drift marginale tra i regimi: {drift:.5f}   (deve essere ~0 -> super-add solo da correlazione)")
    print(f"P(guasto-sistema >= {K}) indip:   {p_ind:.6f}")
    print(f"P(guasto-sistema >= {K}) corr:    {p_cor:.6f}")
    print(f"SUPER-ADDITIVITA  S = corr/indip = {S:.1f}x")

    # --- ORACOLO per-componente (3-vie), STESSA firma del forge_gate ---
    o = SlaOracle()
    v_ok = o.decide(Claim("sla", {"failure_rate_measured": marg_cor[0], "sla_budget": SLA_COMP, "n_samples": N_MC},
                          "sla_montecarlo", "svc0"))
    v_bad = o.decide(Claim("sla", {"failure_rate_measured": 0.20, "sla_budget": SLA_COMP, "n_samples": N_MC,
                                   "witness_trace": "burst@t=42"}, "sla_montecarlo", "svc_bad"))
    v_abs = o.decide(Claim("sla", {"failure_rate_measured": 0.01, "sla_budget": SLA_COMP, "n_samples": 10},
                           "sla_montecarlo", "svc_fewsamples"))
    print(f"\noracolo SlaOracle 3-vie: entro-SLA->{v_ok.status.value}  oltre-SLA->{v_bad.status.value}(witness={bool(v_bad.counterexample)})  pochi-campioni->{v_abs.status.value}")

    # --- monotone DERIVATO dal WITNESS misurato (chiude il crack C2: non hand-set) ---
    from verivault.reliability import binom_ge_k, monotone_from_measured_coupling
    pred_ind = binom_ge_k(N_COMP, sum(marg_ind) / N_COMP, K)   # P_sys SE indipendente (binomiale dai marginali MISURATI)
    pred_cor = binom_ge_k(N_COMP, sum(marg_cor) / N_COMP, K)
    mono_ind = monotone_from_measured_coupling(p_ind, pred_ind)   # DERIVATO: observed vs predizione-indip
    mono_cor = monotone_from_measured_coupling(p_cor, pred_cor)
    print(f"\nmonotone DERIVATO dal witness (non hand-set):")
    print(f"  indip: obs={p_ind:.6f} vs pred-indip={pred_ind:.6f} (ratio {p_ind/pred_ind:.2f}x) -> monotone={mono_ind}")
    print(f"  corr:  obs={p_cor:.6f} vs pred-indip={pred_cor:.6f} (ratio {p_cor/pred_cor:.2f}x) -> monotone={mono_cor}")

    # --- COMPOSIZIONE di sistema con algebra.py INVARIATO, flag monotone DERIVATO ---
    bounds_ind = [reliability_bound(marg_ind[i], SLA_COMP, independent=mono_ind, source=f"svc{i}") for i in range(N_COMP)]
    bounds_cor = [reliability_bound(marg_cor[i], SLA_COMP, independent=mono_cor, source=f"svc{i}") for i in range(N_COMP)]
    v_sys_ind, b_ind, sound_ind = protocol_verdict(bounds_ind)
    v_sys_cor, b_cor, sound_cor = protocol_verdict(bounds_cor)
    print(f"\nprotocol_verdict (servizi INDIP, tutti entro SLA):     {v_sys_ind}  sound={sound_ind}")
    print(f"protocol_verdict (servizi CORRELATI, tutti entro SLA): {v_sys_cor}  sound={sound_cor}  (declassa: union-bound non garantito)")

    # witness: sotto correlazione il sistema VIOLA un SLA-di-sistema generoso (3x il tasso indipendente)
    SYS_BUDGET = 3.0 * p_ind
    witness_unsafe = p_cor > SYS_BUDGET
    print(f"\nSLA-di-sistema (budget=3x indip={SYS_BUDGET:.6f}): P_sys_corr={p_cor:.6f} -> {'VIOLATO' if witness_unsafe else 'ok'} "
          f"(witness che GIUSTIFICA il declassamento)")

    # --- FALSIFICATORI IN-CODICE ---
    assert drift < 0.004, f"marginali NON fissi (drift={drift:.5f}) -> artefatto, non super-additivita da correlazione"
    assert S > 5.0, f"super-additivita assente (S={S:.1f}x <= 5) -> la correlazione non rompe l'union-bound"
    assert mono_ind is True and mono_cor is False, "monotone DERIVATO dal witness deve essere True(indip)/False(corr) — non hand-set (chiude crack C2)"
    assert v_sys_ind == "IMMUNE" and sound_ind, "indip: l'algebra dovrebbe certificare il sistema (union-bound valido)"
    assert v_sys_cor == "ABSTAIN" and not sound_cor, "corr: l'algebra DEVE declassare ad ABSTAIN (mai falso-IMMUNE)"
    assert witness_unsafe, "il sistema correlato dovrebbe violare lo SLA-di-sistema (witness che giustifica il declass)"
    assert v_ok.status == Status.PASS and v_bad.status == Status.REFUTED and v_abs.status == Status.ABSTAIN, "oracolo 3-vie incoerente"

    print("\n" + "=" * 92)
    print("ESITO: TUTTO COERENTE — la PRIMITIVA DI COMPOSIZIONE e' UNIVERSALE.")
    print(f"Lo STESSO algebra.protocol_verdict (invariato) che declassa il coupling-AMM (+78e21) declassa il coupling-da-")
    print(f"correlazione ({S:.0f}x) in un dominio ortogonale. Marginali fissi (drift {drift:.5f}) = niente poesia: solo la")
    print(f"dipendenza condivisa rompe l'union-bound. 2° oracolo (SlaOracle) dispone 3-vie con la stessa firma del forge_gate.")


if __name__ == "__main__":
    main()
