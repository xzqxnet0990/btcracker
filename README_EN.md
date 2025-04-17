# Bitcoin Wallet Cracker

<h4 align="center">
<p>
<a href="https://github.com/xzqxnet0990/btcracker/tree/main/README.md">简体中文</a> |
<a href="https://github.com/xzqxnet0990/btcracker/tree/main/README_EN.md">English</a> 
</p>
</h4>

A tool for recovering lost Bitcoin wallet passwords through various methods. **For educational purposes only.**

## Features

- Supports multiple wallet types including Bitcoin Core wallets
- Dictionary attack with multiple wordlists
- Brute force attack with customizable character sets
- GPU acceleration via Hashcat
- CPU-only mode for systems without dedicated GPU
- Checkpoint functionality for resuming interrupted attacks
- Support for multiple rule sets to enhance password recovery

## Installation

### Requirements

- Python 3.8 or 3.9 (recommended)
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

## Usage

### Basic Usage

```bash
# Dictionary attack on a wallet file
python wallet_cracker.py wallet.dat -D dictionary_directory

# Bitcoin Core mode
python wallet_cracker.py --bitcoin-core wallet_name -D dictionary_directory

# Using Hashcat acceleration
python wallet_cracker.py --bitcoin-core wallet_name --hashcat -D dictionary_directory

# Brute force attack
python wallet_cracker.py wallet.dat -b -m 4 -M 8

# List supported wallet types
python wallet_cracker.py --list-wallet-types
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

## Simplified Usage with Makefile

A Makefile is included for easier use:

```bash
make test NAME=wallet_name
```

## Security and Legal Disclaimer

This tool is provided for **educational purposes only**. The authors do not endorse or promote unauthorized access to Bitcoin wallets. Only use this tool on wallets that you own or have explicit permission to access. Unauthorized attempts to access others' cryptocurrency wallets may be illegal under various laws.

The user assumes all responsibility for the use of this tool. 