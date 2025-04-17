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
- Support for multiple password recovery methods:
  - Dictionary attack
  - Brute force attack
  - John the Ripper integration
  - Hashcat integration (GPU acceleration)
- Checkpoint functionality for resuming interrupted attacks
- Support for multiple rule sets to enhance password recovery

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

# Stop Bitcoin Core daemon
make stop
```

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

## Installation Requirements

- Python 3.8 or 3.9 (recommended)
- Bitcoin Core
- Optional: John the Ripper (for password recovery)
- Optional: Hashcat (for GPU-accelerated password recovery)
- Dependencies listed in requirements.txt

### Installation Steps

1. **Create a Python virtual environment (recommended)**

   ```bash
   # Using standard Python
   python3.9 -m venv btc_env
   source btc_env/bin/activate
   
   # OR using conda
   conda create -n btc_env python=3.9
   conda activate btc_env
   ```

2. **Install dependencies**

   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Troubleshooting Protobuf Installation Issues**

   If you encounter protobuf installation errors like:
   
   ```
   ImportError: cannot import name 'build_py_2to3' from 'distutils.command.build_py'
   ```
   
   This is because the tool requires an older version of protobuf (3.0.0a3) which is not compatible with Python 3.10+. Solutions:
   
   - Use Python 3.9 or 3.8 (recommended)
   - For advanced users: Install dependencies individually with specific versions
     ```bash
     pip install protobuf==3.0.0a3
     pip install two1==3.10.9 --no-deps
     pip install pywallet
     ```

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

### Resuming Hashcat Attacks

The tool now supports checkpointing for Hashcat attacks. If an attack is interrupted:

```bash
# Resume from the last checkpoint
python wallet_cracker.py --bitcoin-core wallet_name --hashcat -D dictionary_directory

# Force restart (ignore checkpoint)
python wallet_cracker.py --bitcoin-core wallet_name --hashcat -D dictionary_directory --no-resume
```

### Command Line Options

```
Arguments:
  wallet_path            Path to wallet file or directory containing wallet files
  
Options:
  -d, --dictionary       Single dictionary file path
  -D, --dictionary-dir   Password dictionary directory (recursive search)
  -b, --brute-force      Perform brute force attack
  -c, --charset          Character set for brute force (default: abcdefghijklmnopqrstuvwxyz0123456789)
  -m, --min-length       Minimum password length (default: 1)
  -M, --max-length       Maximum password length (default: 8)
  -w, --workers          Number of worker processes (default: 4)
  --hashcat              Use hashcat for cracking (GPU acceleration)
  --john                 Use John the Ripper for cracking
  --john-path            John the Ripper installation path
  --rule                 John the Ripper rule file path
  --cpu-only             Use hashcat CPU mode (no GPU)
  --list-wallet-types    List supported wallet types
  --bitcoin-core         Use Bitcoin Core to test passwords directly (wallet name parameter)
  --bitcoin-wordlist     Generate Bitcoin-related password dictionary
  --base-dict            Base dictionary for Bitcoin dictionary generation
  --test-hash            Specify hash file path to crack
  -v, --verbose          Output detailed log information
  -q, --quiet            Output only critical information
  --extract-hash         Only extract hash, do not attempt to crack
  --no-resume            Do not resume previous hashcat session, start fresh
```

## Important Notes

- This tool is intended only for legally recovering your own wallet passwords
- For large password dictionaries, the recovery process may take a considerable amount of time
- GPU acceleration (Hashcat mode) can significantly improve recovery speed

## Security and Legal Disclaimer

This tool is provided for **educational purposes only**. The authors do not endorse or promote unauthorized access to Bitcoin wallets. Only use this tool on wallets that you own or have explicit permission to access. Unauthorized attempts to access others' cryptocurrency wallets may be illegal under various laws.

The user assumes all responsibility for the use of this tool. 