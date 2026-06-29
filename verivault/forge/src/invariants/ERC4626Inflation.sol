// SPDX-License-Identifier: MIT
// VeriVault — proprietary reimplementation (NO AGPL code from crytic/a16z; invariants are not patentable).
pragma solidity ^0.8.13;

/// @title ERC4626Inflation — gate BIDIREZIONALE per donation/first-depositor share-inflation.
/// @notice Positivo: esegue l'attacco-donazione e misura il PROFITTO attaccante (wei, signed).
///         Negativo: sweepa la donazione su una griglia; se il profitto max <= 0 entro un bound
///         plausibile (k * deposito-vittima) -> CERTIFICATO DI IMMUNITA parametrico.
/// @dev    Modelli minimi per il death-gate controllato. Per contratti REALI: vedi IVault + fork (TODO).
library ERC4626Inflation {
    struct Sweep { uint256 victimDeposit; uint256 maxDonationMultiple; uint8 points; }

    function defaultSweep() internal pure returns (Sweep memory) {
        return Sweep({victimDeposit: 1e18, maxDonationMultiple: 100, points: 9});
    }

    /// griglia di donazioni: 0, e potenze/multipli fino a maxDonationMultiple * victimDeposit
    function grid(Sweep memory s) internal pure returns (uint256[] memory g) {
        g = new uint256[](s.points);
        g[0] = 0;
        uint256 hi = s.maxDonationMultiple * s.victimDeposit;
        for (uint8 i = 1; i < s.points; i++) {
            g[i] = (hi * i) / (s.points - 1);   // lineare 0..hi (semplice e deterministico)
        }
    }
}

/// Vault RAW (Solmate-style, NESSUN virtual share) = il pattern vulnerabile.
contract RawVault {
    uint256 public S; uint256 public A;
    function toShares(uint256 x) public view returns (uint256) { return S == 0 ? x : x * S / A; }
    function toAssets(uint256 s) public view returns (uint256) { return S == 0 ? 0 : s * A / S; }
    function deposit(uint256 x) external returns (uint256 s) { s = toShares(x); S += s; A += x; }
    function redeem(uint256 s) external returns (uint256 x) { x = toAssets(s); S -= s; A -= x; }
    function donate(uint256 x) external { A += x; }   // donazione diretta (manipola totalAssets)
}

/// Vault OZ con virtual offset 10^o (la difesa).
contract OZVault {
    uint256 public S; uint256 public A; uint256 immutable O;
    constructor(uint256 tenPowOffset) { O = tenPowOffset; }
    function toShares(uint256 x) public view returns (uint256) { return x * (S + O) / (A + 1); }
    function toAssets(uint256 s) public view returns (uint256) { return s * (A + 1) / (S + O); }
    function deposit(uint256 x) external returns (uint256 s) { s = toShares(x); S += s; A += x; }
    function redeem(uint256 s) external returns (uint256 x) { x = toAssets(s); S -= s; A -= x; }
    function donate(uint256 x) external { A += x; }
}

/// Interfaccia per VAULT REALI (Stadio gate su mainnet-fork). TODO: wiring fork (vedi docs/ARCHITECTURE.md).
interface IVault {
    function deposit(uint256 assets, address receiver) external returns (uint256 shares);
    function redeem(uint256 shares, address receiver, address owner) external returns (uint256 assets);
    function convertToShares(uint256 assets) external view returns (uint256);
    function totalAssets() external view returns (uint256);
}
