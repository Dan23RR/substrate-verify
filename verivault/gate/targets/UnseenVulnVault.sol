// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// CONTRATTO "MAI VISTO" dallo Stage-3: nessun harness/result_key pre-cablato per questo. Ground-truth (per il TEST,
// non noto all'orchestratore): VULN — totalAssets legge balanceOf raw, nessuna virtual-share -> donation-inflation.
import {ERC20} from "solmate/tokens/ERC20.sol";
import {ERC4626} from "solmate/tokens/ERC4626.sol";

contract UnseenVulnVault is ERC4626 {
    constructor(ERC20 a) ERC4626(a, "unseen-vuln", "UVV") {}
    function totalAssets() public view override returns (uint256) {
        return asset.balanceOf(address(this));
    }
}
