// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// MOAT-UPGRADE: il certificato-immunita passa da GRID-12-punti (GeneralGate) a FUZZ-COVERED (property-based).
// Integra forge fuzzing (SOTA, zero deps) nel gate: per ogni vault DIFESO, su (D, V) FUZZATI in un range ampio,
// l'attacco donation/first-depositor NON deve MAI profittare -> assertLe(profit, 0) per ogni run (default 256+).
// FALSIFICABILE: se il fuzzer trova un singolo (D,V) con profit>0 su un vault difeso, la griglia-12 aveva un buco
// e il certificato-immunita-su-grid era debole. Scope onesto: copertura EMPIRICA fuzz (forte), NON prova-su-continuo
// (quella e' il tier SMT/Z3). Disciplina FP=0: la VULN (balanceOf) e provata altrove (GeneralGate, witness eseguito).
import "forge-std/Test.sol";
import {ERC20} from "solmate/tokens/ERC20.sol";
import {IVault, IMintableERC20} from "../src/IVault.sol";
import {MockToken, VaultBalanceOf} from "../src/Targets.sol";
import {SoladyVault, OZVault, OZVaultOffset6} from "../src/ShapesExt.sol";

contract FuzzGate is Test {
    address atk = address(0xA11CE);
    address vic = address(0xB0B);

    // attacco fedele (identico a GeneralGate._oneAttack): chiama l'ABI reale; blocked=true se DoS (no furto).
    function _attack(IVault v, IMintableERC20 t, uint256 V, uint256 D) internal returns (int256 profit, bool blocked) {
        t.mint(atk, 1 + D); t.mint(vic, V);
        vm.startPrank(atk); t.approve(address(v), type(uint256).max);
        try v.deposit(1, atk) returns (uint256) {} catch { vm.stopPrank(); return (int256(0), true); }
        t.transfer(address(v), D); vm.stopPrank();
        vm.startPrank(vic); t.approve(address(v), type(uint256).max);
        try v.deposit(V, vic) returns (uint256) { vm.stopPrank(); } catch { vm.stopPrank(); return (int256(0), true); }
        vm.startPrank(atk); uint256 got = v.redeem(v.balanceOf(atk), atk, atk); vm.stopPrank();
        return (int256(got) - int256(1 + D), false);
    }

    function _bounds(uint96 dRaw, uint96 vRaw) internal pure returns (uint256 D, uint256 V) {
        V = bound(vRaw, uint256(1e6), uint256(1e27));        // vittima da micro a 1e9 token
        D = bound(dRaw, uint256(0), uint256(1e27));          // donazione da 0 a 1e9 token
    }

    // === proprieta' di IMMUNITA fuzzata: su un vault DIFESO, l'attacco non profitta MAI ===
    function testFuzz_OZ0_immune(uint96 dRaw, uint96 vRaw) public {
        (uint256 D, uint256 V) = _bounds(dRaw, vRaw);
        MockToken t = new MockToken();
        (int256 p, bool blocked) = _attack(IVault(address(new OZVault(address(t)))), IMintableERC20(address(t)), V, D);
        if (!blocked) assertLe(p, int256(0), "OZ offset0: donation-inflation deve restare non-profittevole (fuzz)");
    }

    function testFuzz_OZ6_immune(uint96 dRaw, uint96 vRaw) public {
        (uint256 D, uint256 V) = _bounds(dRaw, vRaw);
        MockToken t = new MockToken();
        (int256 p, bool blocked) = _attack(IVault(address(new OZVaultOffset6(address(t)))), IMintableERC20(address(t)), V, D);
        if (!blocked) assertLe(p, int256(0), "OZ offset6 (10^6): donation-inflation deve restare non-profittevole (fuzz)");
    }

    function testFuzz_Solady_immune(uint96 dRaw, uint96 vRaw) public {
        (uint256 D, uint256 V) = _bounds(dRaw, vRaw);
        MockToken t = new MockToken();
        (int256 p, bool blocked) = _attack(IVault(address(new SoladyVault(address(t)))), IMintableERC20(address(t)), V, D);
        if (!blocked) assertLe(p, int256(0), "Solady virtual-shares: donation-inflation deve restare non-profittevole (fuzz)");
    }

    // === CONTROPROVA (sanity): il vault VULNERABILE (balanceOf) E\' fuzz-sfruttabile -> il fuzz NON e\' vacuo ===
    // Non si puo\' assertire un esistenziale in un fuzz per-run; invece verifichiamo il witness noto deterministico:
    // V grande, D=V/2 -> profit>0 (lo stesso witness di GeneralGate). Se questo fallisse, l\'harness fuzz sarebbe rotto.
    function test_balanceOf_exploitable_witness() public {
        uint256 V = 100e18;
        MockToken t = new MockToken();
        (int256 p, bool blocked) = _attack(IVault(address(new VaultBalanceOf(ERC20(address(t))))), IMintableERC20(address(t)), V, V / 2);
        assertTrue(!blocked && p > int256(0), "controprova: balanceOf-vault deve essere sfruttabile col witness D=V/2");
    }
}
