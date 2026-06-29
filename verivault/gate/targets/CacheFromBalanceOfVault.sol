// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// TRAPPOLA FP=0 (review): totalAssets() ritorna un accumulatore _ta (sembra "internal immune"), MA _ta e'
// SINCRONIZZATO da un balance ESTERNO in sync() -> manipolabile via donazione+sync. L'estrattore NON deve
// classificarlo 'internal_accounting' (falso-SAFE): deve ASTENERSI ('unknown' -> analyzable=False).
import {ERC20} from "solmate/tokens/ERC20.sol";
import {ERC4626} from "solmate/tokens/ERC4626.sol";

contract CacheFromBalanceOfVault is ERC4626 {
    uint256 internal _ta;
    constructor(ERC20 a) ERC4626(a, "cache-bal", "CCH") {}
    function totalAssets() public view override returns (uint256) { return _ta; }
    function sync() external { _ta = asset.balanceOf(address(this)); }   // sync da balance ESTERNO -> manipolabile
}
