// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

// CONTRATTO SOTTO AUDIT (input della pipeline VeriVault). Costruito sul vero Solmate ERC4626.
import {ERC20} from "solmate/tokens/ERC20.sol";
import {ERC4626} from "solmate/tokens/ERC4626.sol";

contract VaultInternal is ERC4626 {
    uint256 internal _ta;
    constructor(ERC20 a) ERC4626(a, "vault-internal", "VINT") {}
    function totalAssets() public view override returns (uint256) { return _ta; }
    function afterDeposit(uint256 assets, uint256) internal override { _ta += assets; }
    function beforeWithdraw(uint256 assets, uint256) internal override { _ta -= assets; }
}
