// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// CONTRATTO SOTTO AUDIT. Vault sul vero Solady ERC4626 (che di default ha _useVirtualShares=true, offset 0 -> +1).
import {ERC4626 as SoladyERC4626} from "solady/tokens/ERC4626.sol";

contract SoladyVault is SoladyERC4626 {
    address internal immutable _ast;
    constructor(address a) { _ast = a; }
    function asset() public view override returns (address) { return _ast; }
    function name() public view override returns (string memory) { return "solady-vault"; }
    function symbol() public view override returns (string memory) { return "SDV"; }
    // NON overrida _useVirtualShares (default true) ne _decimalsOffset (default 0): virtual-shares attive.
}
