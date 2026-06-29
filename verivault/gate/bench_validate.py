"""bench_validate.py — valida on-chain una lista di candidati ERC-4626 mainnet (selettori asset()/totalSupply())
e genera test/_VaultList.sol con SOLO i vault reali confermati. Cast largo -> validato -> benchmark pulito."""
import json, urllib.request

RPC = "https://ethereum.publicnode.com"
CANDIDATES = [
    ("sdai",        "0x83F20F44975D03b1b09e64809B757c47f942BEeA"),
    ("susds",       "0xa3931d71877C0E7a3148CB7Eb4463524FEc27fbD"),
    ("susde",       "0x9D39A5DE30e57443BfF2A8307A4256c8797A3497"),
    ("sfrax",       "0xA663B02CF0a4b149d2aD41910CB81e23e1c41c32"),
    ("scrvusd",     "0x0655977FEb2f289A4aB78af67BAB0d17aAb84367"),
    ("sdola",       "0xb45ad160634c528Cc3D2926d9807104FA3157305"),
    ("sfrxeth",     "0xac3E018457B222d93114458476f3E3416Abbe38F"),
    ("apxeth",      "0x9Ba021B0a9b958B5E75cE9f6dff97C7eE52cb3E6"),
    ("wusdm",       "0x57F5E098CaD7A3D1Eed53991D4d66C45C9AF7812"),
    ("steakusdc",   "0xBEEF01735c132Ada46AA9aA4c54623cAA92A64CB"),
    ("gauntusdc",   "0x8eB67A509616cd6A7c1B3c8C21D48FF57df3d458"),
    ("re7weth",     "0x78Fc2c2eD1A4cDb5402365934aE5648aDAd094d0"),
    ("flagshipeth", "0x38989BBA00BDF8181F4082995b3DEAe96163aC5D"),
    ("yvusdc",      "0xBe53A109B494E5c9f97b9Cd39Fe969BE68BF6204"),
    ("yvweth",      "0xc56413869c6CDf96496f2b1eF801fEDBdFA7dDB0"),
    ("yvdai",       "0x028eC7330ff87667b6dfb0D94b954c820195336c"),
    ("dusdcv3",     "0xda00000035fef4082F78dEF6A8903bee419FbF8E"),
    ("dwethv3",     "0xda0002859B2d05F66a753d8241fCDE8623f26F4f"),
    ("meveth",      "0x24Ae2dA0f361AA4BE46b48EB19C91e02c5e4f27E"),
    ("woeth",       "0xDcEe70654261AF21C44c093C300eD3Bb97b78192"),
    ("steakusdt",   "0xbEef047a543E45807105E51A8BBEFCc5950fcfBa"),
    ("usdc_re7",    "0x60d715515d4411f7F43e4206dc5d4a3677f0eC78"),
]
ASSET_SEL = "0x38d52e0f"      # asset()
TS_SEL = "0x18160ddd"         # totalSupply()


def eth_call(to, data):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_call",
                       "params": [{"to": to, "data": data}, "latest"]}).encode()
    req = urllib.request.Request(RPC, data=body, headers={"Content-Type": "application/json", "User-Agent": "curl/8"})
    r = json.loads(urllib.request.urlopen(req, timeout=15).read())
    return r.get("result")


valid = []
for name, addr in CANDIDATES:
    try:
        a = eth_call(addr, ASSET_SEL)
        ts = eth_call(addr, TS_SEL)
        if a and len(a) >= 66 and int(a, 16) != 0 and ts and len(ts) >= 66:
            asset = "0x" + a[-40:]
            valid.append((name, addr, asset))
            print(f"  OK   {name:14} {addr}  asset={asset}")
        else:
            print(f"  --   {name:14} {addr}  (non-4626 / no asset)")
    except Exception as e:
        print(f"  ERR  {name:14} {addr}  {str(e)[:40]}")

# genera la lista Solidity
lines = ["// SPDX-License-Identifier: MIT", "pragma solidity ^0.8.20;",
         "// GENERATO da bench_validate.py — vault ERC-4626 mainnet validati on-chain.", "library VaultList {",
         "    function get() internal pure returns (string[] memory n, address[] memory a) {",
         f"        n = new string[]({len(valid)}); a = new address[]({len(valid)});"]
for i, (name, addr, _asset) in enumerate(valid):
    lines.append(f'        n[{i}] = "{name}"; a[{i}] = {addr};')
lines += ["    }", "}", ""]
open("test/_VaultList.sol", "w", encoding="utf-8").write("\n".join(lines))
print(f"\nVALIDATI {len(valid)}/{len(CANDIDATES)} -> test/_VaultList.sol")
