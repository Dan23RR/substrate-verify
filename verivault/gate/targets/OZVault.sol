// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// CONTRATTO SOTTO AUDIT. Vault sul vero OpenZeppelin ERC4626 (virtual-shares con _decimalsOffset di default 0 -> +1).
import {ERC4626 as OZERC4626} from "@openzeppelin/contracts/token/ERC20/extensions/ERC4626.sol";
import {ERC20 as OZERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {IERC20 as OZIERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";

contract OZVault is OZERC4626 {
    constructor(address a) OZERC20("oz-vault", "OZV") OZERC4626(OZIERC20(a)) {}
    // _decimalsOffset() non overridato (default 0): mitigazione virtual-shares OZ standard (+1).
}
