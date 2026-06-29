// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// FORME DI VAULT su LIBRERIE UPSTREAM REALI (OZ + Solady), per provare la generalita dell'harness parametrico.
// L'UNICA cosa per-forma e' il vault concreto; l'attacco resta condiviso e fedele (chiama l'ABI reale).
import {ERC4626 as SoladyERC4626} from "solady/tokens/ERC4626.sol";
import {ERC4626 as OZERC4626} from "@openzeppelin/contracts/token/ERC20/extensions/ERC4626.sol";
import {ERC20 as OZERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {IERC20 as OZIERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";

/// @notice SAFE atteso: Solady ERC4626 reale, virtual-shares default ON (offset 0 -> +1).
contract SoladyVault is SoladyERC4626 {
    address internal immutable _ast;
    constructor(address a) { _ast = a; }
    function asset() public view override returns (address) { return _ast; }
    function name() public view override returns (string memory) { return "solady-vault"; }
    function symbol() public view override returns (string memory) { return "SDV"; }
}

/// @notice SAFE atteso: OZ ERC4626 reale, virtual-shares con offset di default 0 (+1).
contract OZVault is OZERC4626 {
    constructor(address a) OZERC20("oz-vault", "OZV") OZERC4626(OZIERC20(a)) {}
}

/// @notice SAFE-forte atteso: OZ ERC4626 reale con _decimalsOffset = 6 (10^6 virtual shares).
contract OZVaultOffset6 is OZERC4626 {
    constructor(address a) OZERC20("oz6", "OZ6") OZERC4626(OZIERC20(a)) {}
    function _decimalsOffset() internal pure override returns (uint8) { return 6; }
}
