# PILOTA REALE — la matematica exchange-rate di Compound/Cream (NESSUN virtual offset).
# Modella l'attacco first-depositor + donazione con la VERA integer-division di Solidity.
# Claim di sicurezza (identico all'exec-gate forge): l'ATTACCANTE non puo' profittare (profit <= 0).
#   attacker: deposita 1 wei (1 share) -> dona D (gonfia totalAssets) -> vittima deposita V -> attacker redime.
# Senza offset, V<D -> la vittima riceve 0 share per troncamento, l'attaccante ruba V. -> REFUTED.
def subject(x):
    donation, victim = x
    S, A = 1, 1                       # attacker ha depositato 1 wei -> 1 share (bootstrap)
    A += donation                     # donazione: totalAssets sale, totalSupply no
    vs = victim * S // A              # share della vittima (integer division REALE)
    S += vs
    A += victim
    att_redeem = 1 * A // S           # l'attaccante redime la sua 1 share
    profit = att_redeem - (1 + donation)   # profitto netto = incasso - costo(deposito+donazione)
    return profit


def prop(x, y):
    return y <= 0                     # IMMUNE iff l'attaccante non profitta


def gen(rng):
    donation = rng.randint(1000, 10**9)
    victim = rng.randint(1, donation)    # vittima < donazione -> regime di troncamento
    return (donation, victim)
