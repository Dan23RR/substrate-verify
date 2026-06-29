// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// Interfaccia minimale ERC-4626-like: l'harness parametrico chiama SOLO queste funzioni REALI del vault
// (nessuna reimplementazione della logica -> nessuna infedelta). Qualunque vault che la soddisfa e' attaccabile.
interface IVault {
    function asset() external view returns (address);
    function deposit(uint256 assets, address receiver) external returns (uint256 shares);
    function redeem(uint256 shares, address receiver, address owner) external returns (uint256 assets);
    function totalSupply() external view returns (uint256);
    function totalAssets() external view returns (uint256);
    function balanceOf(address owner) external view returns (uint256);
}

interface IMintableERC20 {
    function mint(address to, uint256 amount) external;
    function approve(address spender, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address owner) external view returns (uint256);
}
