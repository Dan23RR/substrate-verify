// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// BRICK 5 — COUPLED-FORGE: esperimento FALSIFICABILE sulla composizione (gap c).
// Misura (non assume) se due componenti, con A individualmente IMMUNE (virtual-shares), COMPONGONO in un exploit.
//
// NOTA DI VERIFICA AVVERSARIALE (load-bearing): una prima versione usava una B SENZA CUSTODIA che prestava contro
// le partecipazioni spot del chiamante senza un debito esigibile. Misurava +990e18 di "super-additivita'". E' un
// ARTEFATTO: quella B e' un FAUCET (regala denaro senza pegno), non un mercato fedele -> FP per costruzione (cfr.
// docs/BRICK5_DESIGN.md kill-condition). La fedelta'-di-B e' LOAD-BEARING. Una B FEDELE prende CUSTODIA del
// collaterale (o liquida). Con custodia, l'attaccante NON puo' fare l'un-pump (le shares sono in B) e la donazione
// PERMANENTE che gonfia A resta nel collaterale che B detiene -> per conservazione, profit(A o B) <= 0.
//
//   MEV(A) da solo (donation-inflation, victim depositante) -> atteso <= 0 (A immune: OZ virtual-shares)
//   MEV(B) baseline (prestito fair, no manip)               -> atteso <= 0 (ltv<1)
//   MEV(A o B) 3a: donazione PERMANENTE + B con custodia      -> atteso <= 0 (conservazione)
//   MEV(A o B) 3b: flash-donazione + B con custodia + repay   -> atteso <= 0 (un-pump impossibile: shares in B)
// FINDING (asserito): weakest-link REGGE per la composizione VAULT-INTERNA quando A e' immune e B custodisce fedele.
// La super-additivita' reale richiede un oracolo ESTERNO flash-recuperabile (AMM-swap), dipendenza STRUTTURALE
// distinta dalla composizione vault-only -> e' cio' che il flag `monotone` di algebra.py deve codificare (BRICK 5b).
import "forge-std/Test.sol";
import {MockToken} from "../src/Targets.sol";
import {OZVault} from "../src/ShapesExt.sol";

interface IVaultLike {
    function deposit(uint256, address) external returns (uint256);
    function redeem(uint256, address, address) external returns (uint256);
    function totalSupply() external view returns (uint256);
    function totalAssets() external view returns (uint256);
    function balanceOf(address) external view returns (uint256);
    function convertToAssets(uint256) external view returns (uint256);
    function approve(address, uint256) external returns (bool);
    function transferFrom(address, address, uint256) external returns (bool);
}

// === B FEDELE: presta `asset` contro A-shares, prezzate allo SPOT (convertToAssets), prendendo CUSTODIA. ===
//     Il prestito e' garantito dal collaterale in custodia; l'attaccante che abbandona perde le shares.
contract CustodyLendingMarket {
    IVaultLike public immutable A; MockToken public immutable asset; uint256 public immutable ltvBps;
    constructor(IVaultLike _A, MockToken _asset, uint256 _ltvBps) { A = _A; asset = _asset; ltvBps = _ltvBps; }
    function borrow(uint256 shares) external returns (uint256 lent) {
        require(A.transferFrom(msg.sender, address(this), shares), "collateral pull (custodia)");
        uint256 value = A.convertToAssets(shares);          // SPOT oracle sul collaterale CUSTODITO
        lent = value * ltvBps / 10000;
        asset.transfer(msg.sender, lent);
    }
}

contract CoupledGate is Test {
    address atk = address(0xA11CE);
    uint256 constant V = 100e18;        // capitale onesto dell'attaccante
    uint256 constant D = 1000e18;       // ammontare di manipolazione (donazione / flash)
    uint256 constant LTV = 9000;        // 90%

    function _freshA() internal returns (IVaultLike a, MockToken t) {
        t = new MockToken();
        a = IVaultLike(address(new OZVault(address(t))));
    }

    // MEV(A) da solo: first-depositor donation-inflation contro un VICTIM depositante. Atteso <= 0 (A immune).
    function _mevA() internal returns (int256) {
        (IVaultLike a, MockToken t) = _freshA();
        address vic = address(0xB0B);
        t.mint(atk, 1 + D); t.mint(vic, V);
        vm.startPrank(atk); t.approve(address(a), type(uint256).max);
        try a.deposit(1, atk) returns (uint256) {} catch { vm.stopPrank(); return int256(0); }
        t.transfer(address(a), D); vm.stopPrank();
        vm.startPrank(vic); t.approve(address(a), type(uint256).max);
        try a.deposit(V, vic) returns (uint256) { vm.stopPrank(); } catch { vm.stopPrank(); return int256(0); }
        vm.startPrank(atk); uint256 got = a.redeem(a.balanceOf(atk), atk, atk); vm.stopPrank();
        return int256(got) - int256(1 + D);
    }

    // MEV(B) baseline: deposito fair in A, prendo a prestito SENZA manipolare il prezzo. Atteso <= 0.
    function _mevB() internal returns (int256) {
        (IVaultLike a, MockToken t) = _freshA();
        CustodyLendingMarket b = new CustodyLendingMarket(a, t, LTV);
        t.mint(address(b), 1_000_000e18); t.mint(atk, V);
        vm.startPrank(atk);
        t.approve(address(a), type(uint256).max);
        uint256 s = a.deposit(V, atk);        // deposito FAIR
        a.approve(address(b), type(uint256).max);
        uint256 lent = b.borrow(s);
        vm.stopPrank();
        return int256(lent) - int256(V);
    }

    // MEV(A o B) 3a: donazione PERMANENTE + B con custodia. Conservazione: <= 0.
    function _mevCoupled3a() internal returns (int256) {
        (IVaultLike a, MockToken t) = _freshA();
        CustodyLendingMarket b = new CustodyLendingMarket(a, t, LTV);
        t.mint(address(b), 1_000_000e18); t.mint(atk, V + D);
        vm.startPrank(atk);
        t.approve(address(a), type(uint256).max);
        uint256 s = a.deposit(V, atk);
        t.transfer(address(a), D);            // DONAZIONE permanente -> gonfia lo spot di A
        a.approve(address(b), type(uint256).max);
        uint256 lent = b.borrow(s);           // B presta al prezzo gonfiato MA prende custodia (collaterale ~V+D)
        vm.stopPrank();
        return int256(lent) - int256(V + D);  // speso V+D, tiene `lent`; abbandona le shares
    }

    // MEV(A o B) 3b: flash-donazione + B con custodia + repay del flash. L'un-pump e' IMPOSSIBILE (shares in B). <= 0.
    function _mevCoupled3b() internal returns (int256) {
        (IVaultLike a, MockToken t) = _freshA();
        CustodyLendingMarket b = new CustodyLendingMarket(a, t, LTV);
        t.mint(address(b), 1_000_000e18); t.mint(atk, V + D);   // V capitale + D flash (da restituire)
        address sink = address(0xF1A5);
        vm.startPrank(atk);
        t.approve(address(a), type(uint256).max);
        uint256 s = a.deposit(V, atk);
        t.transfer(address(a), D);            // flash-donazione -> pump dello spot
        a.approve(address(b), type(uint256).max);
        uint256 lent = b.borrow(s);           // B custodisce le shares -> l'attaccante NON puo' piu' redimere
        // tentativo di un-pump: l'attaccante non ha piu' shares (sono in B) -> donazione persa.
        // L'esito chiave: i proventi (lent) bastano a ripagare il flash D?
        int256 result;
        if (t.balanceOf(atk) >= D) {          // flash ripagabile -> profit = saldo residuo - capitale V (D netto 0)
            t.transfer(sink, D);
            result = int256(t.balanceOf(atk)) - int256(V);
        } else {                              // FLASH NON RIPAGABILE (lent<D): attacco INFEASIBLE -> perdita
            result = int256(t.balanceOf(atk)) - int256(V) - int256(D);   // resta debito D + capitale V perso
        }
        vm.stopPrank();
        return result;
    }

    function testCompositionSuperAdditivity() public {
        int256 mevA = _mevA();
        int256 mevB = _mevB();
        int256 c3a  = _mevCoupled3a();
        int256 c3b  = _mevCoupled3b();
        int256 maxSingle = mevA > mevB ? mevA : mevB;

        emit log_named_int("MEV_A_alone (donation-inflation)", mevA);
        emit log_named_int("MEV_B_alone (fair borrow)", mevB);
        emit log_named_int("MEV_AoB_3a (donation+custody)", c3a);
        emit log_named_int("MEV_AoB_3b (flash+custody)", c3b);
        emit log_named_int("max(MEV_A,MEV_B)", maxSingle);

        // I singoli NON profittano (A immune, B fair):
        assertLe(mevA, int256(0), "MEV(A) deve essere <=0 (OZ virtual-shares immune)");
        assertLe(mevB, int256(0), "MEV(B) fair deve essere <=0 (ltv<1)");

        // FINDING (falsificazione onesta): con B FEDELE (custodia), la composizione vault-interna NON super-additiva.
        assertLe(c3a, maxSingle, "3a (donation+custody) non deve superare il max dei singoli");
        assertLe(c3b, maxSingle, "3b (flash+custody) non deve superare il max dei singoli");

        emit log_string("FINDING: con B FEDELE (custodia), weakest-link REGGE per donation-inflation vault-interna.");
        emit log_string("La super-additivita' richiede un oracolo ESTERNO flash-recuperabile (AMM), non vault-only.");
        emit log_string("=> algebra.py: `monotone` deve derivare da dipendenza-oracolo-esterno (BRICK 5b), non da MEV vault-only.");
    }
}
