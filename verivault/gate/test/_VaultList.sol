// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
// GENERATO da bench_validate.py — vault ERC-4626 mainnet validati on-chain.
library VaultList {
    function get() internal pure returns (string[] memory n, address[] memory a) {
        n = new string[](22); a = new address[](22);
        n[0] = "sdai"; a[0] = 0x83F20F44975D03b1b09e64809B757c47f942BEeA;
        n[1] = "susds"; a[1] = 0xa3931d71877C0E7a3148CB7Eb4463524FEc27fbD;
        n[2] = "susde"; a[2] = 0x9D39A5DE30e57443BfF2A8307A4256c8797A3497;
        n[3] = "sfrax"; a[3] = 0xA663B02CF0a4b149d2aD41910CB81e23e1c41c32;
        n[4] = "scrvusd"; a[4] = 0x0655977FEb2f289A4aB78af67BAB0d17aAb84367;
        n[5] = "sdola"; a[5] = 0xb45ad160634c528Cc3D2926d9807104FA3157305;
        n[6] = "sfrxeth"; a[6] = 0xac3E018457B222d93114458476f3E3416Abbe38F;
        n[7] = "apxeth"; a[7] = 0x9Ba021B0a9b958B5E75cE9f6dff97C7eE52cb3E6;
        n[8] = "wusdm"; a[8] = 0x57F5E098CaD7A3D1Eed53991D4d66C45C9AF7812;
        n[9] = "steakusdc"; a[9] = 0xBEEF01735c132Ada46AA9aA4c54623cAA92A64CB;
        n[10] = "gauntusdc"; a[10] = 0x8eB67A509616cd6A7c1B3c8C21D48FF57df3d458;
        n[11] = "re7weth"; a[11] = 0x78Fc2c2eD1A4cDb5402365934aE5648aDAd094d0;
        n[12] = "flagshipeth"; a[12] = 0x38989BBA00BDF8181F4082995b3DEAe96163aC5D;
        n[13] = "yvusdc"; a[13] = 0xBe53A109B494E5c9f97b9Cd39Fe969BE68BF6204;
        n[14] = "yvweth"; a[14] = 0xc56413869c6CDf96496f2b1eF801fEDBdFA7dDB0;
        n[15] = "yvdai"; a[15] = 0x028eC7330ff87667b6dfb0D94b954c820195336c;
        n[16] = "dusdcv3"; a[16] = 0xda00000035fef4082F78dEF6A8903bee419FbF8E;
        n[17] = "dwethv3"; a[17] = 0xda0002859B2d05F66a753d8241fCDE8623f26F4f;
        n[18] = "meveth"; a[18] = 0x24Ae2dA0f361AA4BE46b48EB19C91e02c5e4f27E;
        n[19] = "woeth"; a[19] = 0xDcEe70654261AF21C44c093C300eD3Bb97b78192;
        n[20] = "steakusdt"; a[20] = 0xbEef047a543E45807105E51A8BBEFCc5950fcfBa;
        n[21] = "usdc_re7"; a[21] = 0x60d715515d4411f7F43e4206dc5d4a3677f0eC78;
    }
}
