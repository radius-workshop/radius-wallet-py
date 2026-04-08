"""
Smoke test: validates radius_wallet.py against the real Radius testnet.
Run manually: python examples/smoke_test.py

This is a pre-release sanity check, NOT a CI test. It hits the live
Radius testnet RPC — no funds needed, no transactions sent.
"""

import os
import sys

# Allow running from repo root: python examples/smoke_test.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radius_wallet import (
    RadiusWallet,
    TESTNET_CHAIN_ID,
    TESTNET_EXPLORER,
    TESTNET_RPC,
)

passed = 0
failed = 0


def check(label: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        msg = f"  FAIL  {label}"
        if detail:
            msg += f"  ({detail})"
        print(msg)


def main():
    global passed, failed

    print("=" * 60)
    print("Radius Wallet — Smoke Test")
    print(f"RPC: {TESTNET_RPC}")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Create a random wallet
    # ------------------------------------------------------------------
    print("\n--- Wallet Creation ---")
    wallet = RadiusWallet.create()
    print(f"  Address: {wallet.address}")
    check("Wallet has valid address", wallet.address.startswith("0x") and len(wallet.address) == 42)
    check("Chain ID matches testnet", wallet.chain_id == TESTNET_CHAIN_ID,
          f"expected {TESTNET_CHAIN_ID}, got {wallet.chain_id}")

    # ------------------------------------------------------------------
    # 2. Balance queries (new wallet should have 0 across the board)
    # ------------------------------------------------------------------
    print("\n--- Balance Queries ---")
    try:
        rusd = wallet.get_rusd_balance()
        print(f"  RUSD balance: {rusd}")
        check("RUSD balance is 0 for new wallet", rusd == 0.0)
    except Exception as e:
        failed += 1
        print(f"  FAIL  RUSD balance query failed: {e}")

    try:
        sbc = wallet.get_sbc_balance()
        print(f"  SBC balance:  {sbc}")
        check("SBC balance is 0 for new wallet", sbc == 0.0)
    except Exception as e:
        failed += 1
        print(f"  FAIL  SBC balance query failed: {e}")

    try:
        balances = wallet.get_balances()
        check("get_balances returns address", balances["address"] == wallet.address)
        check("get_balances includes rusd key", "rusd" in balances)
        check("get_balances includes sbc key", "sbc" in balances)
    except Exception as e:
        failed += 1
        print(f"  FAIL  get_balances failed: {e}")

    # ------------------------------------------------------------------
    # 3. Chain info
    # ------------------------------------------------------------------
    print("\n--- Chain Info ---")
    try:
        info = wallet.get_chain_info()
        print(f"  chain_id:    {info['chain_id']}")
        print(f"  block:       {info['block_number']}")
        print(f"  gas (gwei):  {info['gas_price_gwei']}")

        check("chain_id == 72344", info["chain_id"] == TESTNET_CHAIN_ID,
              f"got {info['chain_id']}")
        check("block_number > 0", info["block_number"] > 0)
        check("gas_price_gwei >= 0", info["gas_price_gwei"] >= 0)
    except Exception as e:
        failed += 1
        print(f"  FAIL  get_chain_info failed: {e}")

    # ------------------------------------------------------------------
    # 4. Explorer URL format
    # ------------------------------------------------------------------
    print("\n--- Explorer URL ---")
    dummy_hash = "0x" + "ab" * 32
    url = wallet.explorer_url(dummy_hash)
    print(f"  URL: {url}")
    check("Explorer URL starts with testnet base", url.startswith(TESTNET_EXPLORER))
    check("Explorer URL contains /tx/", "/tx/" in url)
    check("Explorer URL ends with tx hash", url.endswith(dummy_hash))

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    total = passed + failed
    print("\n" + "=" * 60)
    print(f"Results: {passed}/{total} passed, {failed} failed")
    print("=" * 60)

    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\nFATAL: smoke test could not complete — {e}")
        print("(Is the Radius testnet reachable?)")
        sys.exit(2)
