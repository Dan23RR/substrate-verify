"""fetch_solmate.py — vendora il VERO Solmate ERC4626 + deps reali (struttura preservata) per l'exec-gate.
Il gate gira sull'UPSTREAM vero (non una reimplementazione). Solmate=AGPL -> sta in exp/ (EVAL), MAI nel core-prodotto."""
import os, urllib.request

# (path-nel-repo, path-locale) — preserva src/tokens & src/utils cosi gli import relativi (../tokens, ../utils) risolvono
FILES = [
    ("src/tokens/ERC4626.sol", "vendor/solmate/src/tokens/ERC4626.sol"),
    ("src/tokens/ERC20.sol", "vendor/solmate/src/tokens/ERC20.sol"),
    ("src/utils/SafeTransferLib.sol", "vendor/solmate/src/utils/SafeTransferLib.sol"),
    ("src/utils/FixedPointMathLib.sol", "vendor/solmate/src/utils/FixedPointMathLib.sol"),
]
HERE = os.path.dirname(os.path.abspath(__file__))
RAW = "https://raw.githubusercontent.com/transmissions11/solmate/main/{}"
for repo_path, local in FILES:
    dst = os.path.join(HERE, local)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    req = urllib.request.Request(RAW.format(repo_path), headers={"User-Agent": "curl/8"})
    src = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
    open(dst, "w", encoding="utf-8").write(src)
    print(f"  OK {local}  ({len(src)}B)")
print("vendored Solmate upstream reale.")
