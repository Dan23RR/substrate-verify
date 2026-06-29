// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// CONTRATTI SOTTO AUDIT (target reali costruiti sul VERO Solmate ERC4626 upstream).
// Sono i sorgenti che la pipeline VeriVault estrae (Stadio 1) ed esegue (Stadio 4) end-to-end.
import {ERC20} from "solmate/tokens/ERC20.sol";
import {ERC4626} from "solmate/tokens/ERC4626.sol";

contract MockToken is ERC20 {
    constructor() ERC20("Mock", "MCK", 18) {}
    function mint(address to, uint256 amt) external { _mint(to, amt); }
}

/// @notice Vault VULNERABILE: totalAssets legge balanceOf (manipolabile via donazione).
contract VaultBalanceOf is ERC4626 {
    constructor(ERC20 a) ERC4626(a, "vault-balanceof", "VBAL") {}
    function totalAssets() public view override returns (uint256) {
        return asset.balanceOf(address(this));
    }
}

/// @notice Vault SICURO: totalAssets da accounting INTERNO (una donazione diretta e' inerte).
contract VaultInternal is ERC4626 {
    uint256 internal _ta;
    constructor(ERC20 a) ERC4626(a, "vault-internal", "VINT") {}
    function totalAssets() public view override returns (uint256) { return _ta; }
    function afterDeposit(uint256 assets, uint256) internal override { _ta += assets; }
    function beforeWithdraw(uint256 assets, uint256) internal override { _ta -= assets; }
}
