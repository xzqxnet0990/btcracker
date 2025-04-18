# Bitcoin Core Installation and Wallet Password Recovery Tool

<h4 align="center">
<p>
<a href="https://github.com/xzqxnet0990/btcracker/tree/main/README.md">简体中文</a> |
<a href="https://github.com/xzqxnet0990/btcracker/tree/main/README_EN.md">English</a> 
</p>
</h4>

This project provides a Makefile for installing and managing Bitcoin Core, as well as a powerful wallet password recovery tool `wallet_cracker.py`.

## Features

- Automated installation and configuration of Bitcoin Core
- Wallet creation, unlocking, and locking functionality
- Wallet information and database file viewing functionality
- Support for importing wallet files (individual or batch import)
- Support for multiple password recovery methods:
  - Dictionary attack
  - Brute force attack
  - John the Ripper integration
  - Hashcat integration (GPU acceleration)
- Checkpoint functionality for resuming interrupted attacks

## Usage

### Bitcoin Core Installation and Management

```bash
# Install Bitcoin Core
make install

# Configure Bitcoin Core
make configure

# Start Bitcoin Core daemon
make start

# Check Bitcoin Core status
make status

# Create new wallet
make create-wallet NAME=mywallet

# Unlock wallet (set password)
make unlock NAME=mywallet PASS=mypassword

# Lock wallet
make lock NAME=mywallet

# View wallet information and database files
make examine-wallet-db NAME=mywallet

# Stop Bitcoin Core daemon
make stop
```

### Importing Existing Wallets

You can import existing Bitcoin wallet files into Bitcoin Core and then use the btcracker tool to attempt password recovery:

```bash
# Import a single wallet file
make import-wallet SRC=wallet/wallet1.001.dat NAME=wallet1_001

# Batch import all wallet files in the wallet directory
make import-all-wallets
```

**Wallet Import Notes:**
- The `import-wallet` command requires specifying the source file path (`SRC`) and target wallet name (`NAME`)
- The `import-all-wallets` command automatically imports all .dat files from the wallet directory, naming them as "imported_filename"
- After importing, you can use `make status` to view the list of imported wallets
- If Bitcoin Core is not running, first start it with `make start` before importing wallets
- Imported wallets can be directly cracked using the btcracker tool:
  ```bash
  python btcracker_run.py --bitcoin-core imported_wallet1.001 --hashcat -d wordlist.txt
  ```

### Creating and Encrypting Wallets

Creating and encrypting Bitcoin Core wallets is an important step in securing your funds. Here's a detailed workflow:

```bash
# 1. Create a new wallet
make create-wallet NAME=my_new_wallet

# 2. Encrypt wallet (set password)
make encrypt-wallet NAME=my_new_wallet PASS=my_secure_password

# 3. Change wallet password (if needed)
make change-passphrase NAME=my_new_wallet PASS=old_password NEW_PASS=new_password

# 4. Temporarily unlock wallet (for transactions and other operations)
make unlock NAME=my_new_wallet PASS=my_secure_password

# 5. Lock wallet after operations
make lock NAME=my_new_wallet
```

**Wallet Security Recommendations:**
- Use strong passwords (at least 16 characters, including uppercase/lowercase letters, numbers, and special characters)
- Don't use the same password in multiple places
- Securely back up your password, consider using a password manager
- Change your password periodically to enhance security
- Always lock your wallet after completing operations

**Warning:** If you forget your password, the only recovery method is using this cracking tool, which may require significant computational resources. Keep your passwords and wallet backups safe.

### Creating BDB Format Wallets

Newer versions of Bitcoin Core (v24 and above) create wallets in SQLite format by default, but this project's password recovery tool is primarily designed for traditional BDB format wallets. To create a BDB format wallet, use the dedicated command:

```bash
# Create BDB format wallet
make create-bdb-wallet NAME=bdb_wallet

# If the above command is not supported, first install the BDB-compatible Bitcoin Core version
make install-bdb

# Configure BDB wallet support
make configure-bdb

# Then create wallet
make create-wallet NAME=bdb_wallet
```

**Note:**
- In v24 and above, you may need to install v22.0 for full BDB wallet support
- BDB format wallets are more compatible with the password recovery tool
- Use `make examine-wallet-db NAME=wallet_name` to verify the wallet format is "bdb"

### Wallet Password Recovery

Use the `wallet_cracker.py` tool to recover forgotten wallet passwords:

```bash
# Using the Makefile integrated test target
make test NAME=mywallet

# Directly using wallet_cracker.py
python3 wallet_cracker.py --bitcoin-core "mywallet" --john --john-path ./john --dictionary rockyou.txt

# Using Hashcat acceleration
python3 wallet_cracker.py --bitcoin-core "mywallet" --hashcat --dictionary rockyou.txt
```

### Using the btcracker_run.py Launcher

For simplified operation, the project provides a `btcracker_run.py` launcher script that can be used directly without installing btcracker:

```bash
# Using the launcher script to crack a Bitcoin Core wallet
python btcracker_run.py --bitcoin-core "mywallet" --dictionary rockyou.txt

# Using the launcher with Hashcat acceleration
python btcracker_run.py --bitcoin-core "mywallet" --hashcat --dictionary rockyou.txt

# Using the launcher for brute force attack
python btcracker_run.py --bitcoin-core "mywallet" --brute-force -m 4 -M 8
```

The `btcracker_run.py` launcher supports all the same command-line parameters as wallet_cracker.py. This method requires no installation, just direct execution, making it more suitable for temporary use or testing scenarios.

### Blockchain Synchronization Issues

When setting up Bitcoin Core for the first time, your node needs to download and verify the entire blockchain. During this process, you might encounter the following error messages:

```
(standard_in) 1: syntax error
Progress: synced X/Y blocks (%)
(standard_in) 1: syntax error
/bin/sh: 7: [: Illegal number: 
Synchronization nearly complete (%)
```

**Explanation of these errors:**
- These are just errors in the progress display script and do not affect the actual blockchain synchronization process
- `syntax error` usually occurs due to issues with the `bc` command when calculating percentages in scripts
- `Illegal number` error happens when parsing non-numeric content

**Solutions:**
1. Continue letting the blockchain synchronization complete; these errors won't affect the sync process
2. Use the following command to view the real synchronization status:
   ```bash
   bitcoin-cli getblockchaininfo | grep -E "blocks|headers|verificationprogress"
   ```
3. Complete synchronization can take several days to weeks depending on your network and hardware performance

**Tips for optimizing sync speed:**
- Use a high-speed internet connection
- Ensure you have sufficient disk space (at least 500GB)
- Consider adding more connections in bitcoin.conf:
  ```
  maxconnections=16
  dbcache=4096  # If you have enough RAM
  ```

Note that some wallet functionality may not work properly until blockchain synchronization is complete. Cracking encrypted wallets doesn't require a complete blockchain, but interacting with the wallet may be limited.

### Hashcat Checkpoint Functionality

Hashcat mode supports checkpoint functionality, allowing you to interrupt and resume long-running attacks:

```bash
# Start Hashcat cracking
python3 wallet_cracker.py --bitcoin-core "mywallet" --hashcat --dictionary rockyou.txt

# Press Ctrl+C to interrupt at any time, progress will be automatically saved
# ...

# Resume cracking progress: just run the same command again
python3 wallet_cracker.py --bitcoin-core "mywallet" --hashcat --dictionary rockyou.txt
# The system will automatically detect the previous session and continue from the interruption point

# If you need to restart instead of resuming, you can use the --no-resume parameter
python3 wallet_cracker.py --bitcoin-core "mywallet" --hashcat --dictionary rockyou.txt --no-resume
```

All session information is saved in the `hashcat_sessions` directory, with a unique session file created for each attack. No need to manually manage checkpoints; the program will automatically handle the recovery process.

### Examining Wallet Information and Database Files

The new `examine-wallet-db` command allows you to view detailed wallet information and associated database files:

```bash
# Basic usage
make examine-wallet-db NAME=mywallet

# Specify wallet database path (if you know the exact path)
make examine-wallet-db NAME=mywallet DB_PATH=/path/to/wallet.dat

# Examine imported wallet information
make examine-wallet-db NAME=imported_wallet1.001
```

This command will display:
- Basic wallet information (name, version, format, balance, etc.)
- Wallet format (BDB, descriptor, or SQLite)
- Wallet encryption status (whether encrypted, whether locked)
- Location and information of wallet-related files
- Address information in the wallet

## Installation Requirements

- Python 3.8 or 3.9 (recommended)
- Bitcoin Core
- Optional: John the Ripper (for password recovery)
- Optional: Hashcat (for GPU-accelerated password recovery)

### Optional Components Installation

#### John the Ripper

```bash
# Clone repository
git clone https://github.com/openwall/john.git

# Compile (Unix/Linux/MacOS)
cd john/src
./configure && make
```

#### Hashcat

```bash
# Download from official website: https://hashcat.net/hashcat/
# Or install using package manager
# macOS:
brew install hashcat

# Ubuntu/Debian:
sudo apt-get install hashcat
```

## Password Dictionaries

The tool defaults to using the `rockyou.txt` dictionary file, which is a commonly used password dictionary. You can download it:

```bash
# Download rockyou.txt
curl -L -o rockyou.txt.gz https://github.com/brannondorsey/naive-hashcat/releases/download/data/rockyou.txt.gz
gunzip rockyou.txt.gz
```

## Important Notes

- This tool is intended only for legally recovering your own wallet passwords
- For large password dictionaries, the recovery process may take a considerable amount of time
- GPU acceleration (Hashcat mode) can significantly improve recovery speed
- The checkpoint functionality makes the cracking process more convenient; even if interrupted, you can simply run the same command again to automatically continue without losing progress

## Security and Legal Disclaimer

This tool is provided for **educational purposes only**. The authors do not endorse or promote unauthorized access to Bitcoin wallets. Only use this tool on wallets that you own or have explicit permission to access. Unauthorized attempts to access others' cryptocurrency wallets may be illegal under various laws.

The user assumes all responsibility for the use of this tool. 