// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// CONTRATTO SOTTO AUDIT. Vault sul vero OpenZeppelin ERC4626 con _decimalsOffset = 6 (10^6 virtual shares).
import {ERC4626 as OZERC4626} from "@openzeppelin/contracts/token/ERC20/extensions/ERC4626.sol";
import {ERC20 as OZERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {IERC20 as OZIERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";

contract OZVaultOffset6 is OZERC4626 {
    constructor(address a) OZERC20("oz6", "OZ6") OZERC4626(OZIERC20(a)) {}
    function _decimalsOffset() internal pure override returns (uint8) { return 6; }  // difesa virtual-shares forte
}
