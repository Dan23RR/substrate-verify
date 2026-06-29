// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// Forme ETICHETTATE aggiuntive per la matrice di confusione del detector.
// - OZ48Vault: OpenZeppelin ERC4626 v4.8.0 REALE = pre-virtual-shares -> NOTORIAMENTE VULNERABILE (storico).
// - OZVaultOffset3: OZ ERC4626 v5 con offset 3 (10^3 virtual) -> SAFE.
import {ERC4626 as OZ48ERC4626} from "@oz48/token/ERC20/extensions/ERC4626.sol";
import {ERC20 as OZ48ERC20} from "@oz48/token/ERC20/ERC20.sol";
import {IERC20 as OZ48IERC20} from "@oz48/token/ERC20/IERC20.sol";
import {ERC4626 as OZ5ERC4626} from "@openzeppelin/contracts/token/ERC20/extensions/ERC4626.sol";
import {ERC20 as OZ5ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {IERC20 as OZ5IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";

/// @notice VULNERABILE (storico): OZ ERC4626 v4.8.0, nessuna virtual-share (la mitigazione arrivo in v4.9).
contract OZ48Vault is OZ48ERC4626 {
    constructor(address a) OZ48ERC20("oz48", "O48") OZ48ERC4626(OZ48IERC20(a)) {}
}

/// @notice SAFE: OZ ERC4626 v5 con _decimalsOffset = 3 (10^3 virtual shares).
contract OZVaultOffset3 is OZ5ERC4626 {
    constructor(address a) OZ5ERC20("oz3", "OZ3") OZ5ERC4626(OZ5IERC20(a)) {}
    function _decimalsOffset() internal pure override returns (uint8) { return 3; }
}
