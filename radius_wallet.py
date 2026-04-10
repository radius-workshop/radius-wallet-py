"""
Radius Wallet — a single-file Python library for interacting with the Radius network.

Handles wallet creation, balance queries, token transfers, faucet requests,
and smart contract deployment/interaction. No framework dependency — just
eth-account and httpx.

Usage:
    from radius_wallet import RadiusWallet

    wallet = RadiusWallet("0xYOUR_PRIVATE_KEY")
    print(wallet.get_balances())
    tx = wallet.send_sbc("0xRecipient", 1.0)
    receipt = wallet.wait_for_tx(tx)
"""

import os
import re
import time
import uuid
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Any, Optional, Union

import httpx
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_abi import encode as abi_encode, decode as abi_decode
from eth_utils import keccak

# =============================================================================
# Constants
# =============================================================================

TESTNET_RPC = "https://rpc.testnet.radiustech.xyz"
TESTNET_CHAIN_ID = 72344
TESTNET_EXPLORER = "https://testnet.radiustech.xyz"

MAINNET_RPC = "https://rpc.radiustech.xyz"
MAINNET_CHAIN_ID = 723487
MAINNET_EXPLORER = "https://network.radiustech.xyz"

SBC_ADDRESS = "0x33ad9e4BD16B69B5BFdED37D8B5D9fF9aba014Fb"
SBC_DECIMALS = 6
RUSD_DECIMALS = 18

TESTNET_FAUCET_BASE = "https://testnet.radiustech.xyz/api/v1/faucet"
MAINNET_FAUCET_BASE = "https://network.radiustech.xyz/api/v1/faucet"

# ERC-20 function selectors
_TRANSFER_SELECTOR = "0xa9059cbb"  # transfer(address,uint256)
_BALANCE_OF_SELECTOR = "0x70a08231"  # balanceOf(address)

# Default gas parameters — Radius uses fixed gas pricing (no EIP-1559)
_DEFAULT_GAS_LIMIT = 100_000
_DEPLOY_GAS_LIMIT = 3_000_000


# =============================================================================
# Helpers
# =============================================================================

_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


def _validate_address(address: str) -> str:
    """Validate an Ethereum-style address and return it.

    Raises ValueError if the address is malformed.
    """
    if not isinstance(address, str) or not _ADDRESS_RE.match(address):
        raise ValueError(
            f"Invalid address: {address!r}. "
            "Must be a 0x-prefixed, 40-character hex string."
        )
    return address


def _rpc_call(rpc_url: str, method: str, params: list) -> Any:
    """Make a JSON-RPC call."""
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": method,
        "params": params,
    }
    resp = httpx.post(rpc_url, json=payload, timeout=15.0)
    resp.raise_for_status()
    body = resp.json()
    if "error" in body and body["error"]:
        err = body["error"]
        raise RuntimeError(f"RPC error {err.get('code')}: {err.get('message')}")
    return body.get("result")


def _pad_address(address: str) -> str:
    """Zero-pad an address to 32 bytes (64 hex chars)."""
    return address.lower().replace("0x", "").zfill(64)


def _pad_uint256(value: int) -> str:
    """Zero-pad a uint256 to 32 bytes (64 hex chars).

    Raises ValueError for negative values.
    """
    if value < 0:
        raise ValueError(f"uint256 cannot be negative, got {value}")
    return hex(value).replace("0x", "").zfill(64)


def _to_wei(amount: Union[float, str], decimals: int) -> int:
    """Convert a human-readable amount to base units.

    Uses Decimal internally to avoid floating-point precision issues.
    Raises ValueError for negative amounts.
    """
    try:
        d = Decimal(str(amount))
    except (InvalidOperation, ValueError) as e:
        raise ValueError(f"Invalid amount: {amount!r}") from e
    if d < 0:
        raise ValueError(f"Amount cannot be negative, got {amount}")
    factor = Decimal(10) ** decimals
    scaled = d * factor
    rounded_down = scaled.to_integral_value(rounding=ROUND_DOWN)
    if scaled != rounded_down:
        raise ValueError(
            f"Amount {amount!r} has more than {decimals} decimal places."
        )
    result = int(rounded_down)
    return result


def _from_wei(raw: int, decimals: int) -> float:
    """Convert base units to a human-readable float."""
    return raw / (10 ** decimals)


def _to_hex(raw_tx) -> str:
    """Convert a signed transaction's raw bytes to a 0x-prefixed hex string."""
    h = raw_tx.hex()
    return h if h.startswith("0x") else "0x" + h


# =============================================================================
# RadiusWallet
# =============================================================================

class RadiusWallet:
    """A simple wallet for the Radius network.

    Args:
        private_key: Hex-encoded private key (with or without 0x prefix).
        rpc_url: Radius JSON-RPC endpoint. Defaults to testnet.
        chain_id: Chain ID. Defaults to testnet (72344).
    """

    def __init__(
        self,
        private_key: str,
        rpc_url: str = TESTNET_RPC,
        chain_id: int = TESTNET_CHAIN_ID,
    ):
        if not private_key.startswith("0x"):
            private_key = "0x" + private_key
        self._account = Account.from_key(private_key)
        # Note: no separate copy of the private key string is stored.
        # self._account holds the key; keeping a second copy is unnecessary
        # and increases the surface area for accidental exposure.
        self.rpc_url = rpc_url
        self.chain_id = chain_id

    @classmethod
    def create(
        cls,
        rpc_url: str = TESTNET_RPC,
        chain_id: int = TESTNET_CHAIN_ID,
    ) -> "RadiusWallet":
        """Generate a new random wallet."""
        acct = Account.create()
        return cls(acct.key.hex(), rpc_url=rpc_url, chain_id=chain_id)

    @classmethod
    def from_env(
        cls,
        env_var: str = "RADIUS_PRIVATE_KEY",
        rpc_url: str = TESTNET_RPC,
        chain_id: int = TESTNET_CHAIN_ID,
    ) -> "RadiusWallet":
        """Load wallet from an environment variable."""
        key = os.environ.get(env_var)
        if not key:
            raise ValueError(f"Environment variable {env_var} is not set.")
        return cls(key, rpc_url=rpc_url, chain_id=chain_id)

    @property
    def address(self) -> str:
        """The wallet's public address."""
        return self._account.address

    @property
    def _faucet_base(self) -> str:
        """Faucet API base URL, selected based on chain ID."""
        if self.chain_id == MAINNET_CHAIN_ID:
            return MAINNET_FAUCET_BASE
        return TESTNET_FAUCET_BASE

    # -------------------------------------------------------------------------
    # RPC helpers
    # -------------------------------------------------------------------------

    def _rpc(self, method: str, params: list) -> Any:
        return _rpc_call(self.rpc_url, method, params)

    def _get_nonce(self) -> int:
        raw = self._rpc("eth_getTransactionCount", [self.address, "pending"])
        return int(raw, 16)

    def _get_gas_price(self) -> int:
        raw = self._rpc("eth_gasPrice", [])
        return int(raw, 16)

    # -------------------------------------------------------------------------
    # Balance queries
    # -------------------------------------------------------------------------

    def get_rusd_balance(self, address: Optional[str] = None) -> float:
        """Get RUSD (native) balance in human-readable units."""
        addr = address or self.address
        if address is not None:
            _validate_address(addr)
        raw = self._rpc("eth_getBalance", [addr, "latest"])
        return _from_wei(int(raw, 16), RUSD_DECIMALS)

    def get_sbc_balance(self, address: Optional[str] = None) -> float:
        """Get SBC (ERC-20) balance in human-readable units."""
        addr = address or self.address
        if address is not None:
            _validate_address(addr)
        calldata = _BALANCE_OF_SELECTOR + _pad_address(addr)
        raw = self._rpc("eth_call", [{"to": SBC_ADDRESS, "data": calldata}, "latest"])
        return _from_wei(int(raw, 16), SBC_DECIMALS)

    def get_balances(self, address: Optional[str] = None) -> dict:
        """Get both RUSD and SBC balances."""
        addr = address or self.address
        return {
            "address": addr,
            "rusd": self.get_rusd_balance(addr),
            "sbc": self.get_sbc_balance(addr),
        }

    # -------------------------------------------------------------------------
    # Chain info
    # -------------------------------------------------------------------------

    def get_chain_info(self) -> dict:
        """Get chain ID, block number, and gas price."""
        chain_id = int(self._rpc("eth_chainId", []), 16)
        block = int(self._rpc("eth_blockNumber", []), 16)
        gas_wei = int(self._rpc("eth_gasPrice", []), 16)
        return {
            "chain_id": chain_id,
            "block_number": block,
            "gas_price_gwei": gas_wei / 1e9,
            "note": "On Radius, block_number is a timestamp in milliseconds.",
        }

    # -------------------------------------------------------------------------
    # Transfers
    # -------------------------------------------------------------------------

    def send_rusd(self, to: str, amount: float) -> str:
        """Send RUSD (native token) to an address. Returns tx hash."""
        _validate_address(to)
        value = _to_wei(amount, RUSD_DECIMALS)
        if value <= 0:
            raise ValueError("Amount must be greater than zero.")
        tx = {
            "to": to,
            "value": value,
            "gas": _DEFAULT_GAS_LIMIT,
            "gasPrice": self._get_gas_price(),
            "nonce": self._get_nonce(),
            "chainId": self.chain_id,
        }
        signed = self._account.sign_transaction(tx)
        raw = self._rpc("eth_sendRawTransaction", [_to_hex(signed.raw_transaction)])
        return raw

    def send_sbc(self, to: str, amount: float) -> str:
        """Send SBC (ERC-20) to an address. Amount in human units (e.g. 1.5).
        Returns tx hash."""
        _validate_address(to)
        base_units = _to_wei(amount, SBC_DECIMALS)
        if base_units <= 0:
            raise ValueError("Amount must be greater than zero.")
        calldata = (
            _TRANSFER_SELECTOR + _pad_address(to) + _pad_uint256(base_units)
        )
        tx = {
            "to": SBC_ADDRESS,
            "value": 0,
            "data": calldata,
            "gas": _DEFAULT_GAS_LIMIT,
            "gasPrice": self._get_gas_price(),
            "nonce": self._get_nonce(),
            "chainId": self.chain_id,
        }
        signed = self._account.sign_transaction(tx)
        raw = self._rpc("eth_sendRawTransaction", [_to_hex(signed.raw_transaction)])
        return raw

    # -------------------------------------------------------------------------
    # Transaction status
    # -------------------------------------------------------------------------

    def get_tx_receipt(self, tx_hash: str) -> Optional[dict]:
        """Get a transaction receipt. Returns None if still pending."""
        return self._rpc("eth_getTransactionReceipt", [tx_hash])

    def wait_for_tx(self, tx_hash: str, timeout: float = 30.0) -> dict:
        """Wait for a transaction to be confirmed. Returns the receipt."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            receipt = self.get_tx_receipt(tx_hash)
            if receipt is not None:
                return receipt
            time.sleep(0.5)
        raise TimeoutError(f"Transaction {tx_hash} not confirmed within {timeout}s.")

    def tx_succeeded(self, receipt: dict) -> bool:
        """Check if a transaction receipt indicates success."""
        status = receipt.get("status", "0x0")
        return int(status, 16) == 1

    def explorer_url(self, tx_hash: str) -> str:
        """Get the block explorer URL for a transaction."""
        base = TESTNET_EXPLORER if self.chain_id == TESTNET_CHAIN_ID else MAINNET_EXPLORER
        return f"{base}/tx/{tx_hash}"

    # -------------------------------------------------------------------------
    # Faucet (testnet only)
    # -------------------------------------------------------------------------

    def request_faucet(self, token: str = "SBC") -> dict:
        """Request testnet tokens from the Radius faucet.

        Tries an unsigned request first. If the faucet requires a signature,
        automatically signs a challenge and retries.

        Returns dict with tx_hash and status info.
        """
        # Try unsigned drip first
        resp = httpx.post(
            f"{self._faucet_base}/drip",
            json={"address": self.address, "token": token},
            timeout=15.0,
        )
        data = resp.json()

        if resp.is_success:
            return data

        error = data.get("error", "")

        # Handle signature requirement
        if error == "signature_required" or resp.status_code == 401:
            return self._faucet_signed(token)

        # Handle rate limiting
        if error == "rate_limited":
            retry_ms = data.get("retry_after_ms") or (data.get("retry_after_seconds", 0) * 1000)
            raise RuntimeError(f"Faucet rate-limited. Retry after {int(retry_ms / 1000)}s.")

        raise RuntimeError(f"Faucet error: {data}")

    def _faucet_signed(self, token: str) -> dict:
        """Faucet drip with signed challenge."""
        # Get challenge
        resp = httpx.get(
            f"{self._faucet_base}/challenge/{self.address}",
            params={"token": token},
            timeout=15.0,
        )
        resp.raise_for_status()
        challenge_data = resp.json()
        message = challenge_data.get("message") or challenge_data.get("challenge")

        # Sign the challenge (EIP-191)
        msg = encode_defunct(text=message)
        signed = self._account.sign_message(msg)
        signature = signed.signature.hex()
        if not signature.startswith("0x"):
            signature = "0x" + signature

        # Submit signed drip
        resp = httpx.post(
            f"{self._faucet_base}/drip",
            json={"address": self.address, "token": token, "signature": signature},
            timeout=15.0,
        )
        data = resp.json()
        if not resp.is_success:
            raise RuntimeError(f"Signed faucet drip failed: {data}")
        return data

    # -------------------------------------------------------------------------
    # Smart contract deployment
    # -------------------------------------------------------------------------

    def deploy_contract(
        self,
        bytecode: str,
        constructor_types: Optional[list[str]] = None,
        constructor_args: Optional[list] = None,
    ) -> dict:
        """Deploy a smart contract.

        Args:
            bytecode: Hex-encoded contract bytecode (with or without 0x prefix).
            constructor_types: Solidity types for constructor args (e.g. ["address", "uint256"]).
            constructor_args: Values for constructor args.

        Returns:
            dict with 'tx_hash', 'address', and 'receipt'.
        """
        if not bytecode.startswith("0x"):
            bytecode = "0x" + bytecode

        # Append ABI-encoded constructor arguments if present
        data = bytecode
        if constructor_types and constructor_args:
            encoded = abi_encode(constructor_types, constructor_args).hex()
            data = bytecode + encoded

        tx = {
            "data": data,
            "value": 0,
            "gas": _DEPLOY_GAS_LIMIT,
            "gasPrice": self._get_gas_price(),
            "nonce": self._get_nonce(),
            "chainId": self.chain_id,
        }
        signed = self._account.sign_transaction(tx)
        tx_hash = self._rpc("eth_sendRawTransaction", [_to_hex(signed.raw_transaction)])
        receipt = self.wait_for_tx(tx_hash)

        contract_address = receipt.get("contractAddress")
        if not contract_address:
            raise RuntimeError(f"Deployment failed — no contract address in receipt. Tx: {tx_hash}")

        return {
            "tx_hash": tx_hash,
            "address": contract_address,
            "receipt": receipt,
        }

    # -------------------------------------------------------------------------
    # Smart contract interaction
    # -------------------------------------------------------------------------

    def call_contract(
        self,
        address: str,
        function_sig: str,
        arg_types: Optional[list[str]] = None,
        args: Optional[list] = None,
        return_types: Optional[list[str]] = None,
    ) -> Any:
        """Read from a smart contract (no transaction, no gas).

        Args:
            address: Contract address.
            function_sig: Function signature, e.g. "balanceOf(address)".
            arg_types: ABI types for args, e.g. ["address"].
            args: Argument values.
            return_types: Expected return types, e.g. ["uint256"]. If provided,
                          decodes the result.

        Returns:
            Raw hex result, or decoded tuple if return_types provided.
        """
        _validate_address(address)
        selector = self._function_selector(function_sig)
        calldata = selector
        if arg_types and args:
            calldata += abi_encode(arg_types, args).hex()

        raw = self._rpc("eth_call", [{"to": address, "data": "0x" + calldata}, "latest"])

        if return_types:
            decoded = abi_decode(return_types, bytes.fromhex(raw.replace("0x", "")))
            return decoded[0] if len(return_types) == 1 else decoded
        return raw

    def send_contract_tx(
        self,
        address: str,
        function_sig: str,
        arg_types: Optional[list[str]] = None,
        args: Optional[list] = None,
        value: int = 0,
        gas: int = _DEFAULT_GAS_LIMIT,
    ) -> str:
        """Send a transaction to a smart contract. Returns tx hash.

        Args:
            address: Contract address.
            function_sig: Function signature, e.g. "transfer(address,uint256)".
            arg_types: ABI types for args.
            args: Argument values.
            value: Native token value to send (in wei), defaults to 0.
            gas: Gas limit for the transaction. Defaults to 100_000.
                 Increase for complex contract calls.
        """
        _validate_address(address)
        selector = self._function_selector(function_sig)
        calldata = "0x" + selector
        if arg_types and args:
            calldata += abi_encode(arg_types, args).hex()

        tx = {
            "to": address,
            "value": value,
            "data": calldata,
            "gas": gas,
            "gasPrice": self._get_gas_price(),
            "nonce": self._get_nonce(),
            "chainId": self.chain_id,
        }
        signed = self._account.sign_transaction(tx)
        return self._rpc("eth_sendRawTransaction", [_to_hex(signed.raw_transaction)])

    @staticmethod
    def _function_selector(sig: str) -> str:
        """Compute the 4-byte function selector from a signature string.
        e.g. "transfer(address,uint256)" -> "a9059cbb"
        """
        return keccak(text=sig).hex()[:8]
