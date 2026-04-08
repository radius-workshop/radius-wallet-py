"""Deploy a simple smart contract to Radius Testnet.

This example deploys a minimal Counter contract. To get the bytecode,
compile with Foundry: forge build, then grab the bytecode from
out/Counter.sol/Counter.json.

For this example, we use a pre-compiled Counter bytecode.
"""

from radius_wallet import RadiusWallet

wallet = RadiusWallet.from_env()

# Minimal Counter contract bytecode (Solidity):
#   uint256 public count;
#   function increment() public { count += 1; }
#   function getCount() public view returns (uint256) { return count; }
#
# Compile your own with Foundry:
#   forge create src/Counter.sol:Counter --rpc-url https://rpc.testnet.radiustech.xyz
#
# Or deploy from bytecode here:
COUNTER_BYTECODE = (
    "0x6080604052348015600e575f5ffd5b506101778061001c5f395ff3fe60806040523480"
    "1561000f575f5ffd5b506004361061003f575f3560e01c806306661abd14610043578063"
    "a87d942c14610061578063d09de08a1461007f575b5f5ffd5b61004b610089565b604051"
    "61005891906100c8565b60405180910390f35b61006961008e565b60405161007691906100"
    "c8565b60405180910390f35b610087610096565b005b5f5481565b5f5f54905090565b6001"
    "5f5f8282546100a7919061010e565b92505081905550565b5f819050919050565b6100c281"
    "6100b0565b82525050565b5f6020820190506100db5f8301846100b9565b92915050565b7f"
    "4e487b71000000000000000000000000000000000000000000000000000000005f52601160"
    "045260245ffd5b5f610118826100b0565b9150610123836100b0565b92508282019050808211"
    "1561013b5761013a6100e1565b5b9291505056fea2646970667358221220df9004bd1eca7f"
    "9ccea721371446203e18a46b45aa1bb3de92a870337afe7b7564736f6c63430008210033"
)

print(f"Deploying Counter from {wallet.address}...")
result = wallet.deploy_contract(COUNTER_BYTECODE)

print(f"Contract deployed!")
print(f"  Address: {result['address']}")
print(f"  Tx hash: {result['tx_hash']}")
print(f"  Explorer: {wallet.explorer_url(result['tx_hash'])}")

# Read from the deployed contract
count = wallet.call_contract(
    result["address"],
    "getCount()",
    return_types=["uint256"],
)
print(f"  Initial count: {count}")

# Write to the contract (increment)
tx = wallet.send_contract_tx(result["address"], "increment()")
wallet.wait_for_tx(tx)

count = wallet.call_contract(
    result["address"],
    "getCount()",
    return_types=["uint256"],
)
print(f"  Count after increment: {count}")
