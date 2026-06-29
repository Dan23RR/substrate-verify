"""test_certificate.py — il certificato PORTABILE e CONTESTABILE (BRICK 8, prima pietra).
Falsifica le proprieta' che il README dichiarava (era L0-prose): round-trip deterministico, integrita' via hash,
detezione-tampering, firma HMAC opzionale. Ogni asserzione = un falsificatore in-codice. Riproducibile:
`python eval/test_certificate.py`  (nessun forge/z3/RPC; solo stdlib + verivault)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verivault.schemas import Claim, Verdict, Certificate, Status
from verivault import certificate as C


def _sample() -> Certificate:
    claim = Claim(kind="erc4626.immunity", payload={"offset": 6, "victim_deposit": 100 * 10**18},
                  oracle="forge_gate", target="OZVaultOffset6.sol", deps=[])
    verdict = Verdict(Status.PASS, confidence=1.0,
                      proof={"immunity_certificate": True, "max_attacker_profit_wei": -499999997524752464,
                             "scope_covers": "donation/first-depositor", "scope_excludes": ["cross-contract"]},
                      reason="nessuna donazione profittevole entro il bound -> immune",
                      script="gate/test/GeneralGate.t.sol")
    return Certificate(claim, verdict, composed_from=[])


def main():
    ok = True
    cert = _sample()

    # (1) ROUND-TRIP deterministico: from_dict(to_dict(c)) ha lo stesso canonical_json
    cj1 = C.canonical_json(cert)
    cert2 = C.from_dict(C.to_dict(cert))
    cj2 = C.canonical_json(cert2)
    print(f"(1) round-trip canonical_json identico: {cj1 == cj2}")
    ok &= (cj1 == cj2)

    # (2) determinismo: due serializzazioni della stessa cert -> stesso hash
    h1, h2 = C.content_hash(cert), C.content_hash(_sample())
    print(f"(2) content_hash deterministico: {h1 == h2}  ({h1[:16]}...)")
    ok &= (h1 == h2)

    # (3) CONTESTABILITA' / integrita': alterare il verdetto cambia l'hash (tampering rilevabile)
    tampered = _sample(); tampered.verdict.status = Status.REFUTED      # qualcuno falsifica un PASS in REFUTED
    h_t = C.content_hash(tampered)
    print(f"(3) tampering (PASS->REFUTED) cambia l'hash: {h_t != h1}")
    ok &= (h_t != h1)

    # (4) FIRMA HMAC opzionale: verify(sign(c,k),k) True; tampering -> firma non valida
    k = b"test-key-not-secret"
    sig = C.sign(cert, k)
    valid = C.verify(cert, sig, k)
    tampered_invalid = not C.verify(tampered, sig, k)
    print(f"(4) firma HMAC: verify-ok={valid}  tampered-rejected={tampered_invalid}")
    ok &= valid and tampered_invalid

    # (5) busta portabile: senza chiave l'hash resta (contestabile via re-esecuzione di verdict.script)
    env = C.envelope(cert)          # nessuna env-var di firma -> hmac None ma hash presente
    has_hash = bool(env.get("content_hash")) and env["certificate"]["verdict"]["script"] == "gate/test/GeneralGate.t.sol"
    print(f"(5) busta export: hash presente + script citato (ri-eseguibile): {has_hash}")
    ok &= has_hash

    print("\nESITO:", "TUTTO COERENTE" if ok else "INCOERENZA")
    assert ok, "proprieta' del certificato portabile/contestabile non rispettate"
    print("=> 'certificato firmato portabile' NON e' piu' L0-prose: round-trip + hash + tamper-detect + HMAC, eseguiti.")


if __name__ == "__main__":
    main()
