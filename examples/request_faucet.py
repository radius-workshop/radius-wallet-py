"""Request testnet SBC from the Radius faucet."""

from radius_wallet import RadiusWallet

wallet = RadiusWallet.from_env()

print(f"Wallet: {wallet.address}")
print(f"Balance before: {wallet.get_sbc_balance()} SBC")

# Request tokens (handles unsigned/signed flow automatically)
result = wallet.request_faucet()
print(f"Faucet response: {result}")

# Wait a moment for the tx to settle, then check balance
import time
time.sleep(3)
print(f"Balance after: {wallet.get_sbc_balance()} SBC")
