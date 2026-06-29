// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// (gap a, corpus PIU' INDIPENDENTE): l'exec-gate form-agnostico su vault la cui logica-inflation e' scritta da TERZE
// PARTI (team OZ/solady, su disco nelle lib vendorizzate, NON nel 68-set, NON da me). Include il pattern FEE che il
// tier SMT ABSTIENE esplicitamente -> dimostra form-agnostic > SMT. Label per ESECUZIONE (oggettive). FP=0 sui SAFE.
import "forge-std/Test.sol";
import {MockToken} from "../src/Targets.sol";
import {IVault, IMintableERC20} from "../src/IVault.sol";
import {IERC20, ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {ERC4626} from "@openzeppelin/contracts/token/ERC20/extensions/ERC4626.sol";
import {ERC4626Fees} from "@openzeppelin/contracts/mocks/docs/ERC4626Fees.sol";
import {ERC4626Mock as OZ5Mock} from "@openzeppelin/contracts/mocks/token/ERC4626Mock.sol";
import {ERC4626 as SoladyERC4626} from "solady/tokens/ERC4626.sol";

// FeeVault: la LOGICA fee-on-deposit e' di OZ (ERC4626Fees, terza parte); io aggiungo solo la config concreta (100bps).
contract FeeVault is ERC4626Fees {
    address immutable _tr;
    constructor(IERC20 a, address tr) ERC20("fee", "FEE") ERC4626(a) { _tr = tr; }
    function _entryFeeBasisPoints() internal pure override returns (uint256) { return 100; }   // 1% entry fee
    function _entryFeeRecipient() internal view override returns (address) { return _tr; }
}

// SoladyNoVirtual: la LOGICA ERC4626 e' di solady (terza parte); disattivo solo la difesa virtual-shares via override.
contract SoladyNoVirtual is SoladyERC4626 {
    address immutable _ast;
    constructor(address a) { _ast = a; }
    function asset() public view override returns (address) { return _ast; }
    function name() public view override returns (string memory) { return "snv"; }
    function symbol() public view override returns (string memory) { return "SNV"; }
    function _useVirtualShares() internal pure override returns (bool) { return false; }       // difesa DISATTIVATA -> VULN atteso
}

contract ThirdPartyGate is Test {
    address atk = address(0xA11CE); address vic = address(0xB0B);

    function _oneAttack(IVault v, IMintableERC20 t, uint256 V, uint256 D) internal returns (int256 profit, bool blocked) {
        t.mint(atk, 1 + D); t.mint(vic, V);
        vm.startPrank(atk); t.approve(address(v), type(uint256).max);
        try v.deposit(1, atk) returns (uint256) {} catch { vm.stopPrank(); return (int256(0), true); }
        t.transfer(address(v), D); vm.stopPrank();
        vm.startPrank(vic); t.approve(address(v), type(uint256).max);
        try v.deposit(V, vic) returns (uint256) { vm.stopPrank(); } catch { vm.stopPrank(); return (int256(0), true); }
        vm.startPrank(atk); uint256 got = v.redeem(v.balanceOf(atk), atk, atk); vm.stopPrank();
        return (int256(got) - int256(1 + D), false);
    }

    function _sweep(string memory name, function() internal returns (IVault, IMintableERC20) deploy) internal returns (int256 maxP) {
        uint256 V = 100e18;
        uint256[12] memory Ds = [uint256(1e18),10e18,25e18,40e18,49e18,50e18,51e18,60e18,75e18,90e18,99e18,100e18];
        maxP = type(int256).min; uint256 bestD; uint256 blocked;
        for (uint256 i = 0; i < 12; i++) {
            (IVault v, IMintableERC20 t) = deploy();
            (int256 p, bool b) = _oneAttack(v, t, V, Ds[i]);
            if (b) { blocked++; continue; }
            if (p > maxP) { maxP = p; bestD = Ds[i]; }
        }
        emit log_string(string.concat("RESULT ", name, " maxProfit=", vm.toString(maxP), " witness=", vm.toString(bestD)));
        emit log_named_uint(string.concat(name, "_blocked"), blocked);
    }

    function _dFee() internal returns (IVault, IMintableERC20) {
        MockToken t = new MockToken(); return (IVault(address(new FeeVault(IERC20(address(t)), address(0xFEE)))), IMintableERC20(address(t)));
    }
    function _dOZ5() internal returns (IVault, IMintableERC20) {
        MockToken t = new MockToken(); return (IVault(address(new OZ5Mock(address(t)))), IMintableERC20(address(t)));
    }
    function _dSoladyNV() internal returns (IVault, IMintableERC20) {
        MockToken t = new MockToken(); return (IVault(address(new SoladyNoVirtual(address(t)))), IMintableERC20(address(t)));
    }

    function testThirdPartyShapes() public {
        int256 fee = _sweep("oz_fees_vault(SMT-abstain)", _dFee);          // logica fee OZ; SMT abstiene; gate adjudica
        int256 oz5 = _sweep("oz5_mock", _dOZ5);                            // OZ v5 mock (virtual) -> atteso IMMUNE
        int256 snv = _sweep("solady_no_virtual", _dSoladyNV);              // solady, difesa OFF -> atteso VULN

        int256 SENT = type(int256).min;
        // VULN (difesa disattivata): l'attacco DEVE profittare per esecuzione
        assertGt(snv, int256(0), "solady_no_virtual (difesa OFF) deve essere sfruttabile per esecuzione");
        // FP=0 sui difesi: ne' il fee-vault (SMT-abstain) ne' l'OZ5-mock devono essere flaggati VULN
        assertLe(fee, int256(0), "FP: fee-vault (virtual-shares) NON deve profittare -> form-agnostic gate adjudica IMMUNE dove SMT abstiene");
        assertLe(oz5, int256(0), "FP: OZ v5 mock (virtual) NON deve profittare");
        // sanita: il fee-vault e' stato ESEGUITO (non tutti-bloccati vacui)
        assertGt(fee, SENT, "fee-vault: l'attacco deve essere eseguibile (>=1 trial), non tutti-bloccati");
    }
}
