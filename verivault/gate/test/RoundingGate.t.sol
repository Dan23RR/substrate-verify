// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// SECONDA CLASSE-VULN sullo STESSO kernel: ROUNDING-DIRECTION (deposit/redeem arrotonda a favore dell'utente
// invece che del vault). Stesso harness parametrico: sweep 1-D su un solo scalare (l'importo x), metrica firmata
// round-trip = redeem(deposit(x)) - x, adjudicazione bidirezionale VULN/IMMUNE, soglia di MATERIALITA (anti-leak-benigno).
// Variabile isolata = la DIREZIONE di arrotondamento (up=BUG favor-utente vs down=corretto favor-vault).
import "forge-std/Test.sol";
import {MockToken} from "../src/Targets.sol";

// vault minimale ERC-4626-like: l'UNICA differenza tra le forme e' roundDepositUp (la direzione = il bug)
contract MinimalVault {
    MockToken public asset;
    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    bool public immutable roundDepositUp;

    constructor(MockToken a, bool up) { asset = a; roundDepositUp = up; }
    function totalAssets() public view returns (uint256) { return asset.balanceOf(address(this)); }

    function deposit(uint256 assets, address to) external returns (uint256 shares) {
        uint256 ts = totalSupply; uint256 ta = totalAssets();
        if (ts == 0) shares = assets;
        else if (roundDepositUp) shares = (assets * ts + ta - 1) / ta;   // BUG: arrotonda SU (favor-utente)
        else shares = (assets * ts) / ta;                                // corretto: arrotonda GIU (favor-vault)
        require(shares > 0, "ZERO_SHARES");
        require(asset.transferFrom(msg.sender, address(this), assets));
        totalSupply = ts + shares; balanceOf[to] += shares;
    }
    function redeem(uint256 shares, address to, address owner) external returns (uint256 assets) {
        uint256 ts = totalSupply; uint256 ta = totalAssets();
        assets = (shares * ta) / ts;                                     // redeem arrotonda GIU (standard)
        balanceOf[owner] -= shares; totalSupply = ts - shares;
        require(asset.transfer(to, assets));
    }
}

contract RoundingGate is Test {
    address seeder = address(0x5EED);
    address atk = address(0xA11CE);
    uint256 constant MATERIALITY = 1e12;   // soglia: profit > ~gas-cost (no leak benigni di pochi wei)

    function _seedAndRoundTrip(bool roundUp, uint256 x) internal returns (int256 profit, bool blocked) {
        MockToken t = new MockToken();
        MinimalVault v = new MinimalVault(t, roundUp);
        // seed: 1 wei share + donazione 1e18 -> price-per-share enorme (~1e18), terreno del leak da arrotondamento
        t.mint(seeder, 1);
        vm.startPrank(seeder);
        t.approve(address(v), type(uint256).max);
        v.deposit(1, seeder);
        vm.stopPrank();
        t.mint(address(v), 1e18);            // donazione diretta -> ta enorme, price >> 1
        // attaccante: round-trip di x
        t.mint(atk, x);
        vm.startPrank(atk);
        t.approve(address(v), type(uint256).max);
        uint256 sh;
        try v.deposit(x, atk) returns (uint256 s) { sh = s; } catch { vm.stopPrank(); return (int256(0), true); }
        uint256 got = v.redeem(sh, atk, atk);
        vm.stopPrank();
        profit = int256(got) - int256(x);
    }

    function _sweep(bool roundUp) internal returns (int256 maxP, uint256 bestX) {
        uint256[8] memory xs = [uint256(1), 2, 3, 10, 100, 1000, 1e6, 1e9];
        maxP = type(int256).min;
        for (uint256 i = 0; i < 8; i++) {
            (int256 p, bool b) = _seedAndRoundTrip(roundUp, xs[i]);
            if (!b && p > maxP) { maxP = p; bestX = xs[i]; }
        }
    }

    function testRoundingDirectionGate() public {
        // forma VULNERABILE: deposit arrotonda SU (favor-utente)
        (int256 vulnP, uint256 vulnX) = _sweep(true);
        emit log_named_int("rounding_UP_maxProfit", vulnP);
        emit log_named_uint("rounding_UP_witness_x", vulnX);
        emit log_string(string.concat("RESULT rounding_up ", vulnP > int256(MATERIALITY) ? "VULN" : "IMMUNE",
            " maxProfit=", vm.toString(vulnP), " witness=", vm.toString(vulnX)));
        // forma SAFE: deposit arrotonda GIU (favor-vault) -- stesso codice, sola direzione cambiata
        (int256 safeP,) = _sweep(false);
        emit log_named_int("rounding_DOWN_maxProfit", safeP);
        emit log_string(string.concat("RESULT rounding_down ", safeP > int256(MATERIALITY) ? "VULN" : "IMMUNE",
            " maxProfit=", vm.toString(safeP)));

        // il gate (2a classe): cattura il leak MATERIALE da up-rounding; immune sul down-rounding corretto
        assertGt(vulnP, int256(MATERIALITY), "up-rounding deve essere catturato (leak materiale)");
        assertLe(safeP, int256(MATERIALITY), "down-rounding corretto deve essere immune (nessun leak materiale)");
    }
}
