"""Send SBC tokens to another address on Radius Testnet."""

from radius_wallet import RadiusWallet

wallet = RadiusWallet.from_env()

# Send 0.1 SBC (SBC uses 6 decimals, the library handles conversion)
recipient = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"  # replace with real address
tx_hash = wallet.send_sbc(recipient, 0.1)

print(f"Tx submitted: {tx_hash}")
print(f"Explorer: {wallet.explorer_url(tx_hash)}")

# Wait for confirmation
receipt = wallet.wait_for_tx(tx_hash)
if wallet.tx_succeeded(receipt):
    print("Transfer confirmed!")
else:
    print("Transfer failed.")
