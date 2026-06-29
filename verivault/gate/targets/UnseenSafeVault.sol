// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// CONTRATTO "MAI VISTO" dallo Stage-3: nessun harness/result_key pre-cablato. Ground-truth (per il TEST, non noto
// all'orchestratore): IMMUNE — totalAssets da accounting INTERNO (_bal aggiornato negli hook) -> donazione inerte.
import {ERC20} from "solmate/tokens/ERC20.sol";
import {ERC4626} from "solmate/tokens/ERC4626.sol";

contract UnseenSafeVault is ERC4626 {
    uint256 internal _bal;
    constructor(ERC20 a) ERC4626(a, "unseen-safe", "USV") {}
    function totalAssets() public view override returns (uint256) { return _bal; }
    function afterDeposit(uint256 assets, uint256) internal override { _bal += assets; }
    function beforeWithdraw(uint256 assets, uint256) internal override { _bal -= assets; }
}
