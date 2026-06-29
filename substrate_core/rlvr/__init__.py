"""substrate_core.rlvr — Substrate-RLVR: addestrare un modello CONTRO l'oracolo sound `regex_equiv`.

NON un nuovo paradigma di superintelligenza. Dopo una review avversariale (judge panel + 3 red-team,
tutti ancorati a codice ESEGUITO, 2026-06-07) la tesi e' stata RIDIMENSIONATA con onesta':

  - Il verificatore-come-reward NON e' novita' (RLVR/DeepSeek-R1/Tulu-3 lo fanno gia').
  - La soundness protegge "e' equivalente?" (~10% del valore), NON "e' un buon rewrite?" (~90%).
  - L'identita' R'=R satura il reward CONFIRMED (riprodotto) -> il reward DEVE pretendere un guadagno
    di semplicita', che NON ha oracolo sound -> tier=EMPIRICAL, dichiarato, MAI proven.
  - compose_and compone VERDETTI, non CAPACITA' (cert-algebra fuori dal fossato di training).

Il fossato onesto, tier-typed:
  (1) [CONFERMATO] oracolo regex completo+sound+decidibile -> reward incorruttibile, mai-rumoroso;
  (2) [ASPIRAZIONALE, ~2 bit/REFUTED, non-testato] witness-conditioned learning (consuma il controesempio);
  (3) [PRODOTTO] tier-head CALIBRATO (proven|empirical|abstain, falso-proven punito = peccato cardinale).

Import senza side-effect: questo __init__ NON importa domini ne' torch a import-time.
Il seam unico verso l'oracolo e' `substrate_core.rlvr.oracle` (che importa esplicitamente
`substrate_core.domains.regex_equiv`, NON auto-registrato nel kernel).
"""
