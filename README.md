# radius-wallet-py

A simple Python library for interacting with the [Radius network](https://radiustech.xyz). One file, two dependencies.

Check balances, send tokens, request faucet funds, deploy contracts, and interact with smart contracts — all from Python.

## Quick Start

```bash
pip install eth-account httpx

# Generate a new wallet
python -c "from eth_account import Account; print(Account.create().key.hex())"

# Set your private key
export RADIUS_PRIVATE_KEY=0x...
```

```python
from radius_wallet import RadiusWallet

wallet = RadiusWallet.from_env()
print(wallet.get_balances())
```

## API

### Create / Load Wallet

```python
# From private key
wallet = RadiusWallet("0xYOUR_PRIVATE_KEY")

# Generate new wallet
wallet = RadiusWallet.create()
print(wallet.address)

# From environment variable (default: RADIUS_PRIVATE_KEY)
wallet = RadiusWallet.from_env()

# Use mainnet instead of testnet
from radius_wallet import MAINNET_RPC, MAINNET_CHAIN_ID
wallet = RadiusWallet("0x...", rpc_url=MAINNET_RPC, chain_id=MAINNET_CHAIN_ID)
```

### Check Balances

```python
wallet.get_rusd_balance()           # Your RUSD (native) balance
wallet.get_sbc_balance()            # Your SBC (ERC-20) balance
wallet.get_balances()               # Both, as a dict

wallet.get_sbc_balance("0x1234...")  # Someone else's balance
```

### Send Tokens

```python
# Send SBC (amounts are human-readable, decimals handled automatically)
# Accepts float or string for precision: 1.5 or "1.5"
tx_hash = wallet.send_sbc("0xRecipient", 1.5)

# Send RUSD (native token)
tx_hash = wallet.send_rusd("0xRecipient", 0.001)

# Wait for confirmation
receipt = wallet.wait_for_tx(tx_hash)
assert wallet.tx_succeeded(receipt)
print(wallet.explorer_url(tx_hash))
```

### Transaction Status

```python
receipt = wallet.get_tx_receipt(tx_hash)  # None if pending
receipt = wallet.wait_for_tx(tx_hash)     # Polls until confirmed
wallet.tx_succeeded(receipt)              # True/False
wallet.explorer_url(tx_hash)              # Link to block explorer
```

### Faucet (Testnet)

```python
result = wallet.request_faucet()  # Requests SBC from testnet faucet
```

### Deploy Contracts

```python
result = wallet.deploy_contract(
    bytecode="0x6080...",
    constructor_types=["address", "uint256"],  # optional
    constructor_args=[wallet.address, 1000],   # optional
)
print(result["address"])   # Deployed contract address
print(result["tx_hash"])
```

### Read from Contracts

```python
count = wallet.call_contract(
    "0xContractAddress",
    "getCount()",                # Function signature
    return_types=["uint256"],    # Decode the response
)
```

### Write to Contracts

```python
tx_hash = wallet.send_contract_tx(
    "0xContractAddress",
    "transfer(address,uint256)",
    arg_types=["address", "uint256"],
    args=["0xRecipient", 1000000],
    gas=200_000,  # optional, defaults to 100_000
)
receipt = wallet.wait_for_tx(tx_hash)
```

### Chain Info

```python
info = wallet.get_chain_info()
# {'chain_id': 72344, 'block_number': ..., 'gas_price_gwei': ..., 'note': '...'}
```

## Radius Network Details

| | Testnet | Mainnet |
|--|---------|---------|
| RPC | `https://rpc.testnet.radiustech.xyz` | `https://rpc.radiustech.xyz` |
| Chain ID | 72344 | 723487 |
| Explorer | `https://testnet.radiustech.xyz` | `https://network.radiustech.xyz` |

**Tokens:**
- **RUSD** — Native token, 18 decimals (used for gas)
- **SBC** — ERC-20 stablecoin, 6 decimals, at `0x33ad9e4BD16B69B5BFdED37D8B5D9fF9aba014Fb`

**Things to know:**
- Gas price is fixed (~1 gwei). No EIP-1559, no priority fees, no gas bidding.
- Block numbers are timestamps in milliseconds (not sequential).
- Sub-second finality — no reorgs possible.
- Failed transactions don't charge gas.

## Examples

See the [examples/](examples/) directory:

- `check_balance.py` — Query balances
- `send_sbc.py` — Send an SBC transfer
- `request_faucet.py` — Get testnet tokens
- `deploy_contract.py` — Deploy and interact with a contract

## Install from Git

```bash
pip install git+https://github.com/radius-workshop/radius-wallet-py.git
```

## Production Notes

This library uses a local private key for signing. This is fine for testnet and hackathons, but for production you should use a managed signing service like [Privy](https://privy.io/) to keep keys secure. See the [Nanda Wallet Concierge](https://github.com/radius-workshop/nanda-wallet-concierge) for an example of the Privy integration pattern.
