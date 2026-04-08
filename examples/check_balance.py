"""Check RUSD and SBC balances on Radius Testnet."""

from radius_wallet import RadiusWallet

# Load wallet from environment variable
wallet = RadiusWallet.from_env()

# Check your own balances
balances = wallet.get_balances()
print(f"Address: {balances['address']}")
print(f"RUSD:    {balances['rusd']}")
print(f"SBC:     {balances['sbc']}")

# Check someone else's balances
# other = wallet.get_balances("0x1234...")
# print(other)
