"""reorder.py — il flatten c15.sol (Compound 0.8.10 port, codice reale Sonne/Hundred/Onyx) ha le sezioni in
ordine sbagliato (CErc20 prima della base CToken) + SPDX/pragma/import duplicati. Riordina per dipendenza."""
import re

text = open("CompoundReal.sol", encoding="utf-8").read()
parts = re.split(r"(// FILE: contracts/\w+\.sol)", text)
sections = {}
for i in range(1, len(parts), 2):
    name = re.search(r"contracts/(\w+)\.sol", parts[i]).group(1)
    cleaned = []
    for ln in parts[i + 1].split("\n"):
        s = ln.strip()
        if s.startswith("// SPDX-License-Identifier:"):
            continue
        if s.startswith("pragma solidity"):
            continue
        if s.startswith('import "./') or s.startswith("import './"):
            continue
        cleaned.append(ln)
    sections[name] = "\n".join(cleaned)

order = ["ExponentialNoError", "EIP20Interface", "EIP20NonStandardInterface", "InterestRateModel",
         "ComptrollerInterface", "ErrorReporter", "CTokenInterfaces", "CToken", "CErc20", "CErc20Immutable"]
out = ["// SPDX-License-Identifier: BSD-3-Clause", "pragma solidity ^0.8.10;", ""]
for name in order:
    out.append("// ======== " + name + " ========")
    out.append(sections[name])
open("CompoundReal.sol", "w", encoding="utf-8").write("\n".join(out))
print("riordinato in dipendenza:", " -> ".join(order))
print("sezioni trovate:", sorted(sections.keys()))
