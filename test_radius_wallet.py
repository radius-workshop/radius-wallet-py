"""Tests for radius_wallet.py — mocked RPC, no network calls."""

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from radius_wallet import (
    MAINNET_CHAIN_ID,
    MAINNET_FAUCET_BASE,
    MAINNET_RPC,
    RUSD_DECIMALS,
    SBC_ADDRESS,
    SBC_DECIMALS,
    TESTNET_CHAIN_ID,
    TESTNET_EXPLORER,
    TESTNET_FAUCET_BASE,
    TESTNET_RPC,
    MAINNET_EXPLORER,
    RadiusWallet,
    _from_wei,
    _pad_address,
    _pad_uint256,
    _to_hex,
    _to_wei,
    _validate_address,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# A well-known test private key (DO NOT use on mainnet).
TEST_PRIVATE_KEY = "0x" + "ab" * 32
# Deterministic address for this key (computed by eth-account)
TEST_ADDRESS = RadiusWallet(TEST_PRIVATE_KEY).address

RECIPIENT = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"


@pytest.fixture
def wallet():
    """A wallet instance that never hits the network."""
    return RadiusWallet(TEST_PRIVATE_KEY)


@pytest.fixture
def mainnet_wallet():
    """A wallet configured for mainnet."""
    return RadiusWallet(TEST_PRIVATE_KEY, rpc_url=MAINNET_RPC, chain_id=MAINNET_CHAIN_ID)


# ---------------------------------------------------------------------------
# Wallet creation and address derivation
# ---------------------------------------------------------------------------

class TestWalletCreation:
    def test_create_from_hex_with_prefix(self):
        w = RadiusWallet("0x" + "ab" * 32)
        assert w.address == TEST_ADDRESS

    def test_create_from_hex_without_prefix(self):
        w = RadiusWallet("ab" * 32)
        assert w.address == TEST_ADDRESS

    def test_create_random(self):
        w = RadiusWallet.create()
        assert w.address.startswith("0x")
        assert len(w.address) == 42

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("RADIUS_PRIVATE_KEY", TEST_PRIVATE_KEY)
        w = RadiusWallet.from_env()
        assert w.address == TEST_ADDRESS

    def test_from_env_missing(self, monkeypatch):
        monkeypatch.delenv("RADIUS_PRIVATE_KEY", raising=False)
        with pytest.raises(ValueError, match="not set"):
            RadiusWallet.from_env()

    def test_from_env_custom_var(self, monkeypatch):
        monkeypatch.setenv("MY_KEY", TEST_PRIVATE_KEY)
        w = RadiusWallet.from_env(env_var="MY_KEY")
        assert w.address == TEST_ADDRESS

    def test_no_redundant_private_key_attribute(self, wallet):
        """The wallet should NOT store a separate _private_key string."""
        assert not hasattr(wallet, "_private_key")

    def test_defaults_to_testnet(self, wallet):
        assert wallet.rpc_url == TESTNET_RPC
        assert wallet.chain_id == TESTNET_CHAIN_ID


# ---------------------------------------------------------------------------
# Address validation
# ---------------------------------------------------------------------------

class TestAddressValidation:
    def test_valid_address(self):
        assert _validate_address("0x70997970C51812dc3A010C7d01b50e0d17dc79C8")

    def test_valid_address_all_lower(self):
        assert _validate_address("0x" + "aa" * 20)

    def test_missing_prefix(self):
        with pytest.raises(ValueError, match="Invalid address"):
            _validate_address("70997970C51812dc3A010C7d01b50e0d17dc79C8")

    def test_too_short(self):
        with pytest.raises(ValueError, match="Invalid address"):
            _validate_address("0xabcd")

    def test_too_long(self):
        with pytest.raises(ValueError, match="Invalid address"):
            _validate_address("0x" + "aa" * 21)

    def test_non_hex_chars(self):
        with pytest.raises(ValueError, match="Invalid address"):
            _validate_address("0x" + "gg" * 20)

    def test_empty_string(self):
        with pytest.raises(ValueError, match="Invalid address"):
            _validate_address("")

    def test_none(self):
        with pytest.raises(ValueError, match="Invalid address"):
            _validate_address(None)


# ---------------------------------------------------------------------------
# _to_wei / _from_wei
# ---------------------------------------------------------------------------

class TestToWei:
    def test_one_token_18_decimals(self):
        assert _to_wei(1.0, 18) == 10**18

    def test_one_token_6_decimals(self):
        assert _to_wei(1.0, 6) == 10**6

    def test_fractional(self):
        assert _to_wei(1.5, 6) == 1_500_000

    def test_smallest_unit_6_decimals(self):
        assert _to_wei(0.000001, 6) == 1

    def test_zero(self):
        assert _to_wei(0, 18) == 0

    def test_string_input(self):
        assert _to_wei("1.5", 6) == 1_500_000

    def test_string_avoids_float_precision(self):
        """String '0.3' should give exact result, unlike float 0.1+0.2."""
        assert _to_wei("0.3", 18) == 300_000_000_000_000_000

    def test_decimal_input(self):
        assert _to_wei(Decimal("1.5"), 6) == 1_500_000

    def test_negative_raises(self):
        with pytest.raises(ValueError, match="negative"):
            _to_wei(-1.0, 6)

    def test_negative_string_raises(self):
        with pytest.raises(ValueError, match="negative"):
            _to_wei("-1.0", 6)

    def test_invalid_string_raises(self):
        with pytest.raises(ValueError, match="Invalid amount"):
            _to_wei("not_a_number", 6)

    def test_large_amount(self):
        assert _to_wei(1_000_000, 6) == 1_000_000_000_000

    def test_too_many_decimals_raises(self):
        with pytest.raises(ValueError, match="more than 6 decimal places"):
            _to_wei("0.0000009", 6)


class TestFromWei:
    def test_one_token_18_decimals(self):
        assert _from_wei(10**18, 18) == 1.0

    def test_one_token_6_decimals(self):
        assert _from_wei(10**6, 6) == 1.0

    def test_zero(self):
        assert _from_wei(0, 18) == 0.0

    def test_fractional(self):
        assert _from_wei(500_000, 6) == 0.5


# ---------------------------------------------------------------------------
# _pad_address / _pad_uint256
# ---------------------------------------------------------------------------

class TestPadAddress:
    def test_standard_address(self):
        result = _pad_address("0x70997970C51812dc3A010C7d01b50e0d17dc79C8")
        assert len(result) == 64
        assert result == "00000000000000000000000070997970c51812dc3a010c7d01b50e0d17dc79c8"

    def test_lowercase(self):
        result = _pad_address("0xABCDEF1234567890ABCDEF1234567890ABCDEF12")
        assert "abcdef" in result
        assert "ABCDEF" not in result


class TestPadUint256:
    def test_zero(self):
        result = _pad_uint256(0)
        assert result == "0" * 64

    def test_one(self):
        result = _pad_uint256(1)
        assert len(result) == 64
        assert result.endswith("1")
        assert result == "0" * 63 + "1"

    def test_large_value(self):
        result = _pad_uint256(10**18)
        assert len(result) == 64

    def test_negative_raises(self):
        with pytest.raises(ValueError, match="negative"):
            _pad_uint256(-1)

    def test_max_uint256(self):
        max_val = 2**256 - 1
        result = _pad_uint256(max_val)
        assert result == "f" * 64


# ---------------------------------------------------------------------------
# _function_selector
# ---------------------------------------------------------------------------

class TestFunctionSelector:
    def test_transfer(self):
        assert RadiusWallet._function_selector("transfer(address,uint256)") == "a9059cbb"

    def test_balance_of(self):
        assert RadiusWallet._function_selector("balanceOf(address)") == "70a08231"

    def test_approve(self):
        assert RadiusWallet._function_selector("approve(address,uint256)") == "095ea7b3"

    def test_no_0x_prefix(self):
        result = RadiusWallet._function_selector("transfer(address,uint256)")
        assert not result.startswith("0x")

    def test_length_is_8(self):
        result = RadiusWallet._function_selector("transfer(address,uint256)")
        assert len(result) == 8


# ---------------------------------------------------------------------------
# _to_hex
# ---------------------------------------------------------------------------

class TestToHex:
    def test_bytes_without_prefix(self):
        assert _to_hex(b"\xab\xcd") == "0xabcd"

    def test_hexbytes_without_prefix(self):
        """HexBytes.hex() returns no 0x prefix in modern versions."""

        class FakeHexBytes:
            def hex(self):
                return "abcd1234"

        assert _to_hex(FakeHexBytes()) == "0xabcd1234"

    def test_already_prefixed(self):
        """Edge case: if hex() ever returns 0x prefix, don't double-prefix."""

        class FakeHexBytes:
            def hex(self):
                return "0xabcd1234"

        assert _to_hex(FakeHexBytes()) == "0xabcd1234"


# ---------------------------------------------------------------------------
# Balance queries (mocked RPC)
# ---------------------------------------------------------------------------

class TestBalanceQueries:
    def test_get_rusd_balance(self, wallet):
        with patch.object(wallet, "_rpc", return_value="0xde0b6b3a7640000"):  # 1e18
            balance = wallet.get_rusd_balance()
            assert balance == 1.0

    def test_get_rusd_balance_other_address(self, wallet):
        with patch.object(wallet, "_rpc", return_value="0xde0b6b3a7640000") as mock_rpc:
            wallet.get_rusd_balance(RECIPIENT)
            mock_rpc.assert_called_once_with("eth_getBalance", [RECIPIENT, "latest"])

    def test_get_sbc_balance(self, wallet):
        raw_hex = "0x" + "0" * 52 + "0f4240"  # 1_000_000 = 1.0 SBC
        with patch.object(wallet, "_rpc", return_value=raw_hex):
            balance = wallet.get_sbc_balance()
            assert balance == 1.0

    def test_get_sbc_balance_calldata(self, wallet):
        """Verify eth_call is constructed correctly for balanceOf."""
        with patch.object(wallet, "_rpc", return_value="0x" + "00" * 32) as mock_rpc:
            wallet.get_sbc_balance()
            call_args = mock_rpc.call_args
            assert call_args[0][0] == "eth_call"
            data = call_args[0][1][0]["data"]
            assert data.startswith("0x70a08231")  # balanceOf selector
            assert call_args[0][1][0]["to"] == SBC_ADDRESS

    def test_get_balances(self, wallet):
        with patch.object(wallet, "get_rusd_balance", return_value=1.0), \
             patch.object(wallet, "get_sbc_balance", return_value=2.0):
            result = wallet.get_balances()
            assert result["rusd"] == 1.0
            assert result["sbc"] == 2.0
            assert result["address"] == wallet.address

    def test_invalid_address_raises(self, wallet):
        with pytest.raises(ValueError, match="Invalid address"):
            wallet.get_rusd_balance("bad_address")

    def test_invalid_address_sbc_raises(self, wallet):
        with pytest.raises(ValueError, match="Invalid address"):
            wallet.get_sbc_balance("bad_address")


# ---------------------------------------------------------------------------
# Transaction dict construction
# ---------------------------------------------------------------------------

class TestTransactionConstruction:
    def test_send_rusd_tx_dict(self, wallet):
        """Verify send_rusd builds a correct legacy transaction."""
        with patch.object(wallet, "_get_gas_price", return_value=1_000_000_000), \
             patch.object(wallet, "_get_nonce", return_value=5), \
             patch.object(wallet, "_rpc", return_value="0xfake_hash"):
            # Patch sign_transaction to capture the tx dict
            original_sign = wallet._account.sign_transaction
            captured_tx = {}

            def capture_sign(tx):
                captured_tx.update(tx)
                return original_sign(tx)

            with patch.object(wallet._account, "sign_transaction", side_effect=capture_sign):
                wallet.send_rusd(RECIPIENT, 1.0)

            assert captured_tx["to"] == RECIPIENT
            assert captured_tx["value"] == 10**18
            assert captured_tx["gas"] == 100_000
            assert captured_tx["gasPrice"] == 1_000_000_000
            assert captured_tx["nonce"] == 5
            assert captured_tx["chainId"] == TESTNET_CHAIN_ID
            # Legacy tx: no maxFeePerGas, no maxPriorityFeePerGas
            assert "maxFeePerGas" not in captured_tx
            assert "maxPriorityFeePerGas" not in captured_tx

    def test_send_sbc_calldata(self, wallet):
        """Verify send_sbc builds correct ERC-20 transfer calldata."""
        with patch.object(wallet, "_get_gas_price", return_value=1_000_000_000), \
             patch.object(wallet, "_get_nonce", return_value=0), \
             patch.object(wallet, "_rpc", return_value="0xfake_hash"):
            captured_tx = {}
            original_sign = wallet._account.sign_transaction

            def capture_sign(tx):
                captured_tx.update(tx)
                return original_sign(tx)

            with patch.object(wallet._account, "sign_transaction", side_effect=capture_sign):
                wallet.send_sbc(RECIPIENT, 1.5)

            data = captured_tx["data"]
            # Starts with transfer selector
            assert data.startswith("0xa9059cbb")
            # Contains recipient address, padded to 32 bytes
            assert _pad_address(RECIPIENT) in data.lower()
            # Contains amount (1.5 * 10^6 = 1_500_000 = 0x16e360)
            assert _pad_uint256(1_500_000) in data
            # Sends to SBC contract, not recipient
            assert captured_tx["to"] == SBC_ADDRESS
            assert captured_tx["value"] == 0

    def test_send_rusd_validates_address(self, wallet):
        with pytest.raises(ValueError, match="Invalid address"):
            wallet.send_rusd("not_an_address", 1.0)

    def test_send_sbc_validates_address(self, wallet):
        with pytest.raises(ValueError, match="Invalid address"):
            wallet.send_sbc("not_an_address", 1.0)

    def test_send_rusd_rejects_negative(self, wallet):
        with pytest.raises(ValueError, match="negative"):
            wallet.send_rusd(RECIPIENT, -1.0)

    def test_send_sbc_rejects_negative(self, wallet):
        with pytest.raises(ValueError, match="negative"):
            wallet.send_sbc(RECIPIENT, -1.0)

    def test_send_rusd_rejects_zero(self, wallet):
        with pytest.raises(ValueError, match="greater than zero"):
            wallet.send_rusd(RECIPIENT, 0)

    def test_send_sbc_rejects_zero(self, wallet):
        with pytest.raises(ValueError, match="greater than zero"):
            wallet.send_sbc(RECIPIENT, 0)

    def test_send_sbc_rejects_precision_overflow(self, wallet):
        with pytest.raises(ValueError, match="more than 6 decimal places"):
            wallet.send_sbc(RECIPIENT, "0.0000009")


# ---------------------------------------------------------------------------
# Chain info
# ---------------------------------------------------------------------------

class TestChainInfo:
    def test_get_chain_info(self, wallet):
        def mock_rpc(method, params):
            return {
                "eth_chainId": hex(TESTNET_CHAIN_ID),
                "eth_blockNumber": hex(1000),
                "eth_gasPrice": hex(1_000_000_000),
            }[method]

        with patch.object(wallet, "_rpc", side_effect=mock_rpc):
            info = wallet.get_chain_info()
            assert info["chain_id"] == TESTNET_CHAIN_ID
            assert info["block_number"] == 1000
            assert info["gas_price_gwei"] == 1.0


# ---------------------------------------------------------------------------
# Transaction status
# ---------------------------------------------------------------------------

class TestTransactionStatus:
    def test_get_tx_receipt_found(self, wallet):
        receipt = {"status": "0x1", "transactionHash": "0xabc"}
        with patch.object(wallet, "_rpc", return_value=receipt):
            assert wallet.get_tx_receipt("0xabc") == receipt

    def test_get_tx_receipt_pending(self, wallet):
        with patch.object(wallet, "_rpc", return_value=None):
            assert wallet.get_tx_receipt("0xabc") is None

    def test_wait_for_tx_immediate(self, wallet):
        receipt = {"status": "0x1"}
        with patch.object(wallet, "get_tx_receipt", return_value=receipt):
            assert wallet.wait_for_tx("0xabc") == receipt

    def test_wait_for_tx_timeout(self, wallet):
        with patch.object(wallet, "get_tx_receipt", return_value=None):
            with pytest.raises(TimeoutError, match="not confirmed"):
                wallet.wait_for_tx("0xabc", timeout=0.1)

    def test_tx_succeeded_true(self, wallet):
        assert wallet.tx_succeeded({"status": "0x1"}) is True

    def test_tx_succeeded_false(self, wallet):
        assert wallet.tx_succeeded({"status": "0x0"}) is False

    def test_tx_succeeded_missing_status(self, wallet):
        """Missing status defaults to 0x0 (failure)."""
        assert wallet.tx_succeeded({}) is False

    def test_explorer_url_testnet(self, wallet):
        url = wallet.explorer_url("0xabc123")
        assert url == f"{TESTNET_EXPLORER}/tx/0xabc123"

    def test_explorer_url_mainnet(self, mainnet_wallet):
        url = mainnet_wallet.explorer_url("0xabc123")
        assert url == f"{MAINNET_EXPLORER}/tx/0xabc123"


# ---------------------------------------------------------------------------
# Faucet (mocked HTTP)
# ---------------------------------------------------------------------------

class TestFaucet:
    def test_unsigned_drip_success(self, wallet):
        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.json.return_value = {"tx_hash": "0xabc"}

        with patch("radius_wallet.httpx.post", return_value=mock_resp) as mock_post:
            result = wallet.request_faucet()
            assert result == {"tx_hash": "0xabc"}
            mock_post.assert_called_once()
            call_url = mock_post.call_args[0][0]
            assert call_url == f"{TESTNET_FAUCET_BASE}/drip"

    def test_faucet_uses_mainnet_url(self, mainnet_wallet):
        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.json.return_value = {"tx_hash": "0xabc"}

        with patch("radius_wallet.httpx.post", return_value=mock_resp) as mock_post:
            mainnet_wallet.request_faucet()
            call_url = mock_post.call_args[0][0]
            assert call_url == f"{MAINNET_FAUCET_BASE}/drip"

    def test_signed_flow(self, wallet):
        """When unsigned drip returns 401, should do signed challenge flow."""
        # First call: unsigned drip fails with 401
        fail_resp = MagicMock()
        fail_resp.is_success = False
        fail_resp.status_code = 401
        fail_resp.json.return_value = {"error": "signature_required"}

        # Challenge response
        challenge_resp = MagicMock()
        challenge_resp.raise_for_status = MagicMock()
        challenge_resp.json.return_value = {"challenge": "Sign this message: abc123"}

        # Signed drip success
        success_resp = MagicMock()
        success_resp.is_success = True
        success_resp.json.return_value = {"tx_hash": "0xdef"}

        with patch("radius_wallet.httpx.post", side_effect=[fail_resp, success_resp]) as mock_post, \
             patch("radius_wallet.httpx.get", return_value=challenge_resp) as mock_get:
            result = wallet.request_faucet()
            assert result == {"tx_hash": "0xdef"}
            # Should have called GET for challenge
            assert mock_get.call_count == 1
            challenge_url = mock_get.call_args[0][0]
            assert "/challenge/" in challenge_url
            # Second POST should include signature
            signed_post = mock_post.call_args_list[1]
            body = signed_post[1]["json"]
            assert "signature" in body
            assert body["signature"].startswith("0x")

    def test_rate_limited(self, wallet):
        fail_resp = MagicMock()
        fail_resp.is_success = False
        fail_resp.status_code = 429
        fail_resp.json.return_value = {"error": "rate_limited", "retry_after_seconds": 60}

        with patch("radius_wallet.httpx.post", return_value=fail_resp):
            with pytest.raises(RuntimeError, match="rate-limited"):
                wallet.request_faucet()

    def test_unknown_error(self, wallet):
        fail_resp = MagicMock()
        fail_resp.is_success = False
        fail_resp.status_code = 500
        fail_resp.json.return_value = {"error": "internal_error"}

        with patch("radius_wallet.httpx.post", return_value=fail_resp):
            with pytest.raises(RuntimeError, match="Faucet error"):
                wallet.request_faucet()

    def test_faucet_base_testnet(self, wallet):
        assert wallet._faucet_base == TESTNET_FAUCET_BASE

    def test_faucet_base_mainnet(self, mainnet_wallet):
        assert mainnet_wallet._faucet_base == MAINNET_FAUCET_BASE


# ---------------------------------------------------------------------------
# Contract deployment (mocked)
# ---------------------------------------------------------------------------

class TestDeployContract:
    def test_deploy_basic(self, wallet):
        fake_receipt = {"contractAddress": "0x" + "cc" * 20, "status": "0x1"}
        with patch.object(wallet, "_get_gas_price", return_value=1_000_000_000), \
             patch.object(wallet, "_get_nonce", return_value=0), \
             patch.object(wallet, "_rpc", return_value="0xfake_hash"), \
             patch.object(wallet, "wait_for_tx", return_value=fake_receipt):
            result = wallet.deploy_contract("0x6080604052")
            assert result["address"] == "0x" + "cc" * 20
            assert result["tx_hash"] == "0xfake_hash"

    def test_deploy_no_contract_address(self, wallet):
        fake_receipt = {"status": "0x0"}
        with patch.object(wallet, "_get_gas_price", return_value=1_000_000_000), \
             patch.object(wallet, "_get_nonce", return_value=0), \
             patch.object(wallet, "_rpc", return_value="0xfake_hash"), \
             patch.object(wallet, "wait_for_tx", return_value=fake_receipt):
            with pytest.raises(RuntimeError, match="Deployment failed"):
                wallet.deploy_contract("0x6080604052")

    def test_deploy_adds_0x_prefix(self, wallet):
        """Bytecode without 0x prefix should be handled."""
        fake_receipt = {"contractAddress": "0x" + "cc" * 20, "status": "0x1"}
        captured_tx = {}

        with patch.object(wallet, "_get_gas_price", return_value=1_000_000_000), \
             patch.object(wallet, "_get_nonce", return_value=0), \
             patch.object(wallet, "_rpc", return_value="0xfake_hash"), \
             patch.object(wallet, "wait_for_tx", return_value=fake_receipt):
            original_sign = wallet._account.sign_transaction

            def capture_sign(tx):
                captured_tx.update(tx)
                return original_sign(tx)

            with patch.object(wallet._account, "sign_transaction", side_effect=capture_sign):
                wallet.deploy_contract("6080604052")

            assert captured_tx["data"].startswith("0x")


# ---------------------------------------------------------------------------
# Contract interaction (mocked)
# ---------------------------------------------------------------------------

class TestContractInteraction:
    def test_call_contract_raw(self, wallet):
        with patch.object(wallet, "_rpc", return_value="0x" + "00" * 32) as mock_rpc:
            result = wallet.call_contract(
                RECIPIENT, "getCount()",
            )
            assert result == "0x" + "00" * 32
            call_args = mock_rpc.call_args[0]
            assert call_args[0] == "eth_call"
            data = call_args[1][0]["data"]
            expected_selector = RadiusWallet._function_selector("getCount()")
            assert data == "0x" + expected_selector

    def test_call_contract_decoded(self, wallet):
        # 42 as uint256
        hex_42 = "0x" + "00" * 31 + "2a"
        with patch.object(wallet, "_rpc", return_value=hex_42):
            result = wallet.call_contract(
                RECIPIENT, "getCount()", return_types=["uint256"],
            )
            assert result == 42

    def test_call_contract_validates_address(self, wallet):
        with pytest.raises(ValueError, match="Invalid address"):
            wallet.call_contract("bad", "getCount()")

    def test_send_contract_tx(self, wallet):
        with patch.object(wallet, "_get_gas_price", return_value=1_000_000_000), \
             patch.object(wallet, "_get_nonce", return_value=0), \
             patch.object(wallet, "_rpc", return_value="0xfake_hash"):
            result = wallet.send_contract_tx(RECIPIENT, "increment()")
            assert result == "0xfake_hash"

    def test_send_contract_tx_validates_address(self, wallet):
        with pytest.raises(ValueError, match="Invalid address"):
            wallet.send_contract_tx("bad", "increment()")

    def test_send_contract_tx_custom_gas(self, wallet):
        """Verify the gas parameter is passed through."""
        captured_tx = {}
        with patch.object(wallet, "_get_gas_price", return_value=1_000_000_000), \
             patch.object(wallet, "_get_nonce", return_value=0), \
             patch.object(wallet, "_rpc", return_value="0xfake_hash"):
            original_sign = wallet._account.sign_transaction

            def capture_sign(tx):
                captured_tx.update(tx)
                return original_sign(tx)

            with patch.object(wallet._account, "sign_transaction", side_effect=capture_sign):
                wallet.send_contract_tx(RECIPIENT, "increment()", gas=500_000)

            assert captured_tx["gas"] == 500_000

    def test_send_contract_tx_with_args(self, wallet):
        """Verify calldata includes selector + ABI-encoded args."""
        captured_tx = {}
        with patch.object(wallet, "_get_gas_price", return_value=1_000_000_000), \
             patch.object(wallet, "_get_nonce", return_value=0), \
             patch.object(wallet, "_rpc", return_value="0xfake_hash"):
            original_sign = wallet._account.sign_transaction

            def capture_sign(tx):
                captured_tx.update(tx)
                return original_sign(tx)

            with patch.object(wallet._account, "sign_transaction", side_effect=capture_sign):
                wallet.send_contract_tx(
                    RECIPIENT,
                    "transfer(address,uint256)",
                    arg_types=["address", "uint256"],
                    args=[RECIPIENT, 1_000_000],
                )

            data = captured_tx["data"]
            assert data.startswith("0xa9059cbb")
            # 4 bytes selector + 32 bytes address + 32 bytes uint256 = 4+32+32 = 68 bytes = 136 hex + "0x"
            assert len(data) == 2 + 8 + 128  # 0x + 8 selector + 128 args


# ---------------------------------------------------------------------------
# RPC call formatting
# ---------------------------------------------------------------------------

class TestRpcCall:
    def test_rpc_error_raises(self, wallet):
        error_body = {"jsonrpc": "2.0", "id": "1", "error": {"code": -32000, "message": "nonce too low"}}
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = error_body

        with patch("radius_wallet.httpx.post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="nonce too low"):
                wallet._rpc("eth_getBalance", [wallet.address, "latest"])

    def test_rpc_http_error_raises(self, wallet):
        import httpx as _httpx
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = _httpx.HTTPStatusError(
            "503", request=MagicMock(), response=MagicMock()
        )

        with patch("radius_wallet.httpx.post", return_value=mock_resp):
            with pytest.raises(_httpx.HTTPStatusError):
                wallet._rpc("eth_getBalance", [wallet.address, "latest"])
