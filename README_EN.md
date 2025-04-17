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