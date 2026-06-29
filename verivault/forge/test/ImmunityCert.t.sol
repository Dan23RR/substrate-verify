// SPDX-License-Identifier: MIT
pragma solidity ^0.8.13;
import "forge-std/Test.sol";
import {ERC4626Inflation, RawVault, OZVault} from "../src/invariants/ERC4626Inflation.sol";

/// Gate BIDIREZIONALE validato (questa sessione): emette VULN+PoC (positivo) o CERTIFICATO-IMMUNITA (negativo).
/// `forge test --match-path test/ImmunityCert.t.sol -vv`  ->  JSON-able output per l'oracolo Python.
contract ImmunityCert is Test {
    using ERC4626Inflation for ERC4626Inflation.Sweep;
    uint256 constant V = 1e18;

    function _grid() internal pure returns (uint256[9] memory g) {
        g = [uint256(0), 5e17, 1e18, 2e18, 3e18, 5e18, 1e19, 5e19, 1e20];
    }
    function attackRaw(uint256 D) internal returns (int256) {
        RawVault v = new RawVault(); uint256 sa = v.deposit(1); v.donate(D); v.deposit(V);
        return int256(v.redeem(sa)) - 1 - int256(D);
    }
    function attackOZ(uint256 O, uint256 D) internal returns (int256) {
        OZVault v = new OZVault(O); uint256 sa = v.deposit(1); v.donate(D); v.deposit(V);
        return int256(v.redeem(sa)) - 1 - int256(D);
    }
    function maxRaw() internal returns (int256 m) { m = type(int256).min; uint256[9] memory g = _grid(); for (uint i; i < 9; i++) { int256 p = attackRaw(g[i]); if (p > m) m = p; } }
    function maxOZ(uint256 O) internal returns (int256 m) { m = type(int256).min; uint256[9] memory g = _grid(); for (uint i; i < 9; i++) { int256 p = attackOZ(O, g[i]); if (p > m) m = p; } }

    function test_immunity_certificate() public {
        int256 raw = maxRaw();
        console2.log(string.concat("RESULT raw maxProfit=", vm.toString(raw)));
        uint8[5] memory offs = [0, 1, 2, 4, 6];
        for (uint i; i < offs.length; i++) {
            int256 m = maxOZ(10 ** offs[i]);
            console2.log(string.concat("RESULT oz offset=", vm.toString(offs[i]), " maxProfit=", vm.toString(m)));
        }
        assertGt(raw, 0, "RAW deve essere EXPLOITABLE (gate positivo)");
        assertLe(maxOZ(1), 0, "OZ offset>=0 deve essere IMMUNE (gate negativo / certificato)");
    }
}
