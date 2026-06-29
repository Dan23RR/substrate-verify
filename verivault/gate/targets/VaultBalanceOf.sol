// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

// CONTRATTO SOTTO AUDIT (input della pipeline VeriVault). Costruito sul vero Solmate ERC4626.
import {ERC20} from "solmate/tokens/ERC20.sol";
import {ERC4626} from "solmate/tokens/ERC4626.sol";

contract VaultBalanceOf is ERC4626 {
    constructor(ERC20 a) ERC4626(a, "vault-balanceof", "VBAL") {}
    function totalAssets() public view override returns (uint256) {
        return asset.balanceOf(address(this));
    }
}
