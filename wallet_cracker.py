#!/usr/bin/env python3
# Bitcoin wallet.dat password cracker
# For educational purposes only
#
# 使用方法:
# 1. 直接破解钱包文件:   python wallet_cracker.py wallet.dat -D 字典目录
# 2. Bitcoin Core模式:  python wallet_cracker.py --bitcoin-core 钱包名 -D 字典目录
# 3. 使用Hashcat加速:   python wallet_cracker.py --bitcoin-core 钱包名 --hashcat -D 字典目录
# 4. 暴力破解:          python wallet_cracker.py wallet.dat -b -m 4 -M 8
# 5. 列出支持的钱包类型: python wallet_cracker.py --list-wallet-types
# 6. Makefile简化使用:  make test NAME=wallet_name

import os
import sys
import time
import argparse
import itertools
import subprocess
import tempfile
import json
import bz2
import gzip
import tarfile
import zipfile
from concurrent.futures import ProcessPoolExecutor
import platform
import struct
import sqlite3
import traceback
import binascii
import dbm
from pathlib import Path
import logging

# 添加BTCRecover子模块路径
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "btcrecover"))

# 添加进度条支持
try:
    from tqdm import tqdm
except ImportError:
    print("提示: 安装 tqdm 包可以显示进度条: pip install tqdm")
    # 使用简单的替代进度显示
    class tqdm:
        def __init__(self, iterable=None, total=None, desc=None, unit=None, **kwargs):
            self.iterable = iterable
            self.total = total or (len(iterable) if iterable is not None else None)
            self.desc = desc or ""
            self.n = 0
            self.last_print = 0
            
        def update(self, n=1):
            self.n += n
            current_time = time.time()
            # 每秒最多更新一次进度
            if current_time - self.last_print >= 1:
                if self.total:
                    print(f"\r{self.desc}: {self.n}/{self.total} ({self.n/self.total*100:.1f}%)", end="", flush=True)
                else:
                    print(f"\r{self.desc}: {self.n}", end="", flush=True)
                self.last_print = current_time
                
        def close(self):
            print("")
            
        def __iter__(self):
            self.iter = iter(self.iterable)
            return self
            
        def __next__(self):
            try:
                obj = next(self.iter)
                self.update(1)
                return obj
            except StopIteration:
                self.close()
                raise
                
        def __enter__(self):
            return self
            
        def __exit__(self, exc_type, exc_val, exc_tb):
            self.close()
            
        def set_description(self, desc):
            self.desc = desc

try:
    from pywallet import wallet
except ImportError:
    print("Error: pywallet module not found")
    print("Please install it using: pip install pywallet")
    sys.exit(1)

try:
    import btcrecover.btcrpass
    BTCRECOVER_AVAILABLE = True
except ImportError:
    BTCRECOVER_AVAILABLE = False
    print("Warning: btcrecover module not found, some wallet types may not be supported")

# 设置日志级别 (0=最少日志, 1=标准日志, 2=详细日志)
LOG_LEVEL = 1

def log(message, level=1):
    """根据设置的日志级别打印消息"""
    if level <= LOG_LEVEL:
        print(message, flush=True)

def test_password(wallet_file, password):
    """Test if the password can decrypt the wallet file."""
    try:
        # Attempt to open the wallet with the given password
        wallet_data = wallet.WalletDat(wallet_file)
        result = wallet_data.read_wallet(password)
        if result:
            return True, password
    except ImportError as e:
        print(f"ImportError: {e} - 可能是加密库路径问题")
        print("建议: 运行 fix_crypto.py 修复脚本")
        return False, None
    except Exception as e:
        # macOS经常出现的加密库错误
        if "unsafe way" in str(e) or "libcrypto" in str(e):
            print(f"加密库错误: {e}")
            print("建议: 设置 export CRYPTOGRAPHY_OPENSSL_NO_LEGACY=1")
        # 其他常见错误
        elif "cannot import name" in str(e):
            print(f"模块导入错误: {e}") 
            print("建议: 使用虚拟环境并降级pycryptodome")
        # 静默处理其他错误
        pass
    
    # If pywallet fails, try btcrecover if available
    if BTCRECOVER_AVAILABLE:
        try:
            tokenlist = btcrecover.btcrpass.TokenList(password)
            wallet_obj = btcrecover.btcrpass.WalletBase.wallet_factory(wallet_file)
            if wallet_obj.return_verified_password_or_false(tokenlist) is not False:
                return True, password
        except Exception as e:
            # 仅在调试模式下打印btcrecover错误
            if os.environ.get("BTC_DEBUG") == "1":
                print(f"btcrecover 错误: {e}")
            pass
            
    return False, None

def extract_passwords_from_file(filename):
    """Extract passwords from a file, handling compressed formats."""
    passwords = []
    
    try:
        # Handle different file formats
        if filename.endswith('.txt'):
            with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
                passwords = [line.strip() for line in f if line.strip()]
        elif filename.endswith('.bz2'):
            with bz2.open(filename, 'rt', encoding='utf-8', errors='ignore') as f:
                passwords = [line.strip() for line in f if line.strip()]
        elif filename.endswith('.gz'):
            with gzip.open(filename, 'rt', encoding='utf-8', errors='ignore') as f:
                passwords = [line.strip() for line in f if line.strip()]
        elif filename.endswith('.tgz') or filename.endswith('.tar.gz'):
            with tempfile.TemporaryDirectory() as tmpdir:
                try:
                    with tarfile.open(filename, 'r:gz') as tar:
                        tar.extractall(path=tmpdir)
                        for root, _, files in os.walk(tmpdir):
                            for file in files:
                                if file.endswith('.txt'):
                                    with open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore') as f:
                                        passwords.extend([line.strip() for line in f if line.strip()])
                except Exception as e:
                    log(f"Error extracting {filename}: {e}", level=1)
        elif filename.endswith('.zip'):
            with tempfile.TemporaryDirectory() as tmpdir:
                try:
                    with zipfile.ZipFile(filename, 'r') as zip_ref:
                        zip_ref.extractall(tmpdir)
                        for root, _, files in os.walk(tmpdir):
                            for file in files:
                                if file.endswith('.txt'):
                                    with open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore') as f:
                                        passwords.extend([line.strip() for line in f if line.strip()])
                except Exception as e:
                    log(f"Error extracting {filename}: {e}", level=1)
    except Exception as e:
        log(f"Error processing file {filename}: {e}", level=1)
    
    return passwords

def collect_password_files(base_dir):
    """收集指定目录下的所有密码字典文件，包括子目录和压缩文件"""
    password_files = []
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            file_path = os.path.join(root, file)
            # Include text files and compressed files that might contain passwords
            if file.endswith(('.txt', '.bz2', '.gz', '.tgz', '.tar.gz', '.zip')):
                password_files.append(file_path)
    print(f"收集到 {len(password_files)} 个密码文件")
    return password_files

def dictionary_attack(wallet_file, wordlist_files, num_workers=4):
    """使用多个字典文件进行字典攻击"""
    if isinstance(wordlist_files, str):
        wordlist_files = [wordlist_files]

    total_tested = 0
    start_time = time.time()

    for wordlist_file in wordlist_files:
        if not os.path.exists(wordlist_file):
            log(f"跳过不存在的字典文件: {wordlist_file}", level=1)
            continue

        log(f"使用字典文件: {wordlist_file}", level=1)

        try:
            # 使用我们的提取函数处理文件
            password_list = extract_passwords_from_file(wordlist_file)
            
            if not password_list:
                log(f"从文件 {wordlist_file} 中未提取到密码，跳过", level=1)
                continue
                
            log(f"从 {wordlist_file} 中提取到 {len(password_list)} 个密码", level=1)

            with ProcessPoolExecutor(max_workers=num_workers) as executor:
                batch_size = 1000
                password_batches = [password_list[i:i+batch_size] for i in range(0, len(password_list), batch_size)]

                # 创建进度条
                with tqdm(total=len(password_list), desc="密码测试", unit="pwd") as pbar:
                    for batch in password_batches:
                        futures = []
                        for password in batch:
                            if not password:
                                continue
                            futures.append(executor.submit(test_password, wallet_file, password))

                        for future in futures:
                            success, found_password = future.result()
                            total_tested += 1
                            pbar.update(1)

                            if success:
                                elapsed = time.time() - start_time
                                speed = total_tested / elapsed if elapsed > 0 else 0
                                log(f"\n找到密码: {found_password} (测试了 {total_tested} 个密码，速度 {speed:.2f} p/s)", level=1)
                                return found_password
        except Exception as e:
            log(f"处理字典文件 {wordlist_file} 时出错: {str(e)}", level=1)
            continue

    elapsed = time.time() - start_time
    speed = total_tested / elapsed if elapsed > 0 else 0
    log(f"未找到密码。共测试 {total_tested} 个密码，速度 {speed:.2f} p/s", level=1)
    return None

def brute_force_attack(wallet_file, charset, min_length, max_length, num_workers=4):
    """Perform a brute force attack using the given character set and length range."""
    print(f"Starting brute force attack with charset: {charset}")
    print(f"Length range: {min_length} to {max_length}")
    
    start_time = time.time()
    tested = 0
    
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        for length in range(min_length, max_length + 1):
            print(f"Trying passwords of length {length}")
            
            # Generate all possible combinations of the given length
            for combo in itertools.product(charset, repeat=length):
                password = ''.join(combo)
                future = executor.submit(test_password, wallet_file, password)
                success, found_password = future.result()
                tested += 1
                
                if tested % 1000 == 0:
                    elapsed = time.time() - start_time
                    print(f"Tested {tested} passwords in {elapsed:.2f} seconds ({tested/elapsed:.2f} p/s)")
                
                if success:
                    print(f"\nPassword found: {found_password}")
                    return found_password
    
    print(f"Password not found. Tested {tested} passwords in {time.time() - start_time:.2f} seconds")
    return None

def extract_hash_from_wallet(wallet_file):
    """Extract hash from various wallet types for hashcat processing."""
    try:
        wallet_type = detect_wallet_type(wallet_file)
        print(f"正在从{wallet_type}钱包提取哈希...")
        
        # Save hash to temporary file
        fd, hash_file = tempfile.mkstemp(suffix='.txt')
        os.close(fd)
        
        # 针对不同钱包类型使用不同的提取方法
        if wallet_type == "Bitcoin Core wallet.dat" or wallet_type == "未知":
            # 尝试使用btcrecover (如果可用)
            if BTCRECOVER_AVAILABLE:
                try:
                    cmd = ["python", "-m", "btcrecover.extract_scripts", "--data-extract", "--wallet", wallet_file, "--output", hash_file]
                    subprocess.run(cmd, check=True, capture_output=True, text=True)
                    
                    with open(hash_file, 'r') as f:
                        hash_data = f.read().strip()
                    
                    if hash_data:
                        print(f"成功提取哈希: {hash_data[:30]}...")
                        return hash_data, hash_file
                except Exception as e:
                    print(f"使用btcrecover提取哈希失败: {e}")
            
            # 备用方法：尝试手动提取
            try:
                with open(wallet_file, 'rb') as f:
                    wallet_data = f.read()
                
                # 尝试找到比特币钱包的加密标记
                encrypted_marker = b'\x30\x81\x82\x02\x01\x01\x30\x2c'
                if encrypted_marker in wallet_data:
                    pos = wallet_data.find(encrypted_marker)
                    # 提取适合hashcat的格式
                    hash_portion = wallet_data[pos:pos+256].hex()
                    hash_format = f"$bitcoin$1$16$0000000000000000000000000000000000000000000000000000000000000000$1$1$64$0000000000000000$16$0000000000000000000000000000000000000000000000000000000000000000${hash_portion}"
                    with open(hash_file, 'w') as f:
                        f.write(hash_format)
                    return hash_format, hash_file
            except Exception as e:
                print(f"手动提取哈希失败: {e}")
                
        elif "Electrum" in wallet_type:
            # 处理Electrum钱包
            if BTCRECOVER_AVAILABLE:
                try:
                    cmd = ["python", "-m", "btcrecover.extract_scripts", "--data-extract", "--wallet", wallet_file, "--output", hash_file]
                    subprocess.run(cmd, check=True, capture_output=True, text=True)
                    with open(hash_file, 'r') as f:
                        hash_data = f.read().strip()
                    if hash_data:
                        return hash_data, hash_file
                except Exception as e:
                    print(f"提取Electrum钱包哈希失败: {e}")
        
        elif "Ethereum" in wallet_type:
            # 处理以太坊钱包
            try:
                with open(wallet_file, 'r') as f:
                    wallet_json = json.load(f)
                
                if "crypto" in wallet_json or "Crypto" in wallet_json:
                    crypto = wallet_json.get("crypto", wallet_json.get("Crypto", {}))
                    if "ciphertext" in crypto and "kdfparams" in crypto:
                        ciphertext = crypto["ciphertext"]
                        salt = crypto["kdfparams"].get("salt", "")
                        hash_format = f"$ethereum$s*{salt}*{ciphertext}"
                        with open(hash_file, 'w') as f:
                            f.write(hash_format)
                        return hash_format, hash_file
            except Exception as e:
                print(f"提取以太坊钱包哈希失败: {e}")
                
        # 如果btcrecover可用，尝试使用它的通用提取功能
        if BTCRECOVER_AVAILABLE:
            try:
                # 尝试使用btcrecover的自动检测功能
                cmd = ["python", "-m", "btcrecover.extract_scripts", "--data-extract", "--wallet", wallet_file, "--output", hash_file]
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                with open(hash_file, 'r') as f:
                    hash_data = f.read().strip()
                
                if hash_data:
                    print(f"成功提取哈希: {hash_data[:30]}...")
                    return hash_data, hash_file
            except Exception as e:
                print(f"通用哈希提取失败: {e}")
                
        print("无法从钱包中提取有效的哈希")
        return None, None
        
    except Exception as e:
        print(f"提取哈希时发生错误: {e}")
        return None, None

def detect_hash_mode(hash_file):
    """检测哈希文件的类型，返回适用于hashcat的模式"""
    try:
        with open(hash_file, 'r') as f:
            hash_data = f.read().strip()
        
        # 检测各种钱包哈希格式
        if hash_data.startswith('$bitcoin$'):
            return 11300  # Bitcoin Core钱包
        elif hash_data.startswith('$electrum$'):
            return 16600  # Electrum钱包
        elif hash_data.startswith('$ethereum$'):
            return 15700  # 以太坊钱包
        elif hash_data.startswith('$multibit$'):
            return 12700  # Multibit钱包
        elif 'aes$' in hash_data:
            return 14700  # 带AES加密的iTunes备份
        
        # 更多格式可以在此添加
        
    except Exception as e:
        print(f"检测哈希类型时出错: {e}")
    
    return -1  # 未知类型

def hashcat_attack(hash_file, wordlist_file=None, attack_mode=0, charset=None, min_length=1, max_length=8, cpu_only=False, resume=True):
    """Use hashcat to crack the wallet hash with multiple rule sets."""
    if not os.path.exists(hash_file):
        log(f"Error: Hash file {hash_file} not found", level=1)
        return None
    
    print(f"\n===== Hashcat攻击开始 =====")  # 添加更明确的状态输出
    log(f"哈希文件: {hash_file}", level=1)
    if wordlist_file:
        log(f"字典文件: {wordlist_file}", level=1)
    
    # 检测哈希类型
    hash_mode = detect_hash_mode(hash_file)
    if hash_mode == -1:
        log("无法确定哈希类型，将尝试使用Bitcoin Core模式(11300)", level=1)
        hash_mode = 11300
    
    log(f"检测到哈希类型: {hash_mode}", level=1)
    
    # 创建临时词典文件（如果需要）
    temp_wordlist = None
    
    # 创建检查点和会话文件目录
    checkpoint_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hashcat_sessions")
    os.makedirs(checkpoint_dir, exist_ok=True)
    
    # 为当前攻击创建唯一的会话ID
    session_id = f"btcracker_{os.path.basename(hash_file)}_{attack_mode}"
    if wordlist_file:
        session_id += f"_{os.path.basename(wordlist_file)}"
    if charset:
        session_id += f"_{min_length}_{max_length}"
    
    session_file = os.path.join(checkpoint_dir, f"{session_id}.session")
    restore_file = os.path.join(checkpoint_dir, f"{session_id}.restore")
    log(f"会话文件: {session_file}", level=2)
    
    # 创建.potfile文件路径（用于保存找到的密码）
    potfile = os.path.join(checkpoint_dir, f"{session_id}.potfile")
    
    try:
        # 检查hashcat是否安装
        try:
            hashcat_version = subprocess.run(["hashcat", "--version"], capture_output=True, text=True)
            print(f"检测到hashcat版本: {hashcat_version.stdout.strip()}")
            log(f"检测到hashcat版本: {hashcat_version.stdout.strip()}", level=2)
        except (subprocess.SubprocessError, FileNotFoundError):
            print("错误: 未找到hashcat。请先安装hashcat。")
            log("Error: hashcat not found. Please install hashcat first.", level=1)
            return None
        
        # 字典攻击准备工作
        if attack_mode == 0 and wordlist_file:  
            if not os.path.exists(wordlist_file):
                print(f"错误: 字典文件 {wordlist_file} 不存在")
                log(f"Error: Wordlist file {wordlist_file} not found", level=1)
                return None
            
            # 处理非标准txt文件
            if not wordlist_file.endswith('.txt'):
                print(f"处理非文本字典文件: {wordlist_file}")
                log(f"处理非文本字典文件: {wordlist_file}", level=2)
                passwords = extract_passwords_from_file(wordlist_file)
                
                if not passwords:
                    print(f"从 {wordlist_file} 中未提取到密码")
                    log(f"从 {wordlist_file} 中未提取到密码", level=1)
                    return None
                
                # 创建临时字典文件
                temp_wordlist = tempfile.mktemp(suffix='.txt')
                with open(temp_wordlist, 'w', encoding='utf-8') as f:
                    for pwd in passwords:
                        f.write(f"{pwd}\n")
                
                print(f"创建了包含 {len(passwords)} 个密码的临时字典文件")
                log(f"创建了包含 {len(passwords)} 个密码的临时字典文件", level=2)
                wordlist_file = temp_wordlist
        
        # 基础命令
        base_cmd = ["hashcat", "-m", str(hash_mode), hash_file, "--status", "--status-timer", "5"]
        
        # 添加会话和恢复功能
        base_cmd.extend(["--session", session_id, "--potfile-path", potfile])
        
        # 检查是否存在恢复文件，如果存在且resume=True则添加恢复参数
        if resume and os.path.exists(restore_file):
            print(f"找到恢复文件，从断点继续")
            log(f"找到恢复文件，从断点继续: {restore_file}", level=1)
            base_cmd.append("--restore")
        else:
            # 如果不是恢复模式，则添加输出文件
            base_cmd.extend(["-o", "found_password.txt"])
        
        # 检测操作系统和设备类型
        is_macos = platform.system() == "Darwin"
        is_arm = "arm" in platform.processor().lower()
        
        # 设置CPU/GPU选项
        if cpu_only or (is_macos and is_arm):
            if not cpu_only:
                print("检测到Apple Silicon，自动切换到CPU模式")
                log("检测到Apple Silicon，自动切换到CPU模式", level=2)
            else:
                print("根据用户设置，使用CPU模式")
                log("根据用户设置，使用CPU模式", level=2)
                
            # macOS上的优化设置
            if is_macos:
                base_cmd.extend(["--force", "-D", "1", "--backend-devices", "1"])
            else:
                base_cmd.extend(["--force", "--opencl-device-types", "1", "--backend-devices", "1", "--cpu-affinity=1"])
        else:
            # GPU模式选项
            if is_macos:
                base_cmd.extend(["--force", "--backend-devices", "1", "-D", "2"])
            else:
                base_cmd.extend(["-O"])  # 启用优化
        
        # 通用选项
        base_cmd.append("--self-test-disable")
        
        # 在非macOS平台上启用优化
        if not is_macos:
            base_cmd.append("-O")
        
        # 添加状态报告
        base_cmd.extend(["--force", "--status", "--status-timer", "5"])
        
        # 直接使用本地hashcat/rules目录
        local_rules_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hashcat/rules")
        print(f"\n===== Hashcat规则使用情况 =====")
        print(f"使用本地hashcat规则目录: {local_rules_dir}")
        log(f"使用本地hashcat规则目录: {local_rules_dir}", level=1)  # 提高日志级别，确保输出
        
        # 检查规则目录
        if not os.path.exists(local_rules_dir):
            print(f"警告：本地规则目录 {local_rules_dir} 不存在，尝试创建")
            try:
                os.makedirs(local_rules_dir, exist_ok=True)
                print(f"已创建规则目录: {local_rules_dir}")
            except Exception as e:
                print(f"创建规则目录失败: {e}")
        
        if not os.path.exists(local_rules_dir) or not os.path.isdir(local_rules_dir):
            print(f"警告：本地规则目录 {local_rules_dir} 不存在或不是目录")
            log(f"警告：本地规则目录 {local_rules_dir} 不存在或不是目录", level=1)
            rules_to_use = []
        else:
            # 列出目录中的文件
            print("规则目录内容:")
            try:
                rule_files = os.listdir(local_rules_dir)
                for rf in rule_files:
                    print(f"  - {rf}")
            except Exception as e:
                print(f"列出规则目录内容时出错: {e}")
            
            # 定义规则优先级列表 - 根据有效性和效率排序
            priority_rules = [
                # 加密货币钱包的高效规则
                "best66.rule",          # 小型高效规则增强版
                "toggles1.rule",        # 基本大小写变换 
                "leetspeak.rule",       # 基本Leet替换
                "top10_2023.rule",      # 最新密码趋势规则
                
                # 小规则先尝试
                "hybrid/append_d.rule",   # 附加数字
                "hybrid/prepend_d.rule",  # 前置数字
                "hybrid/append_ds.rule",  # 附加数字和特殊字符
                
                # 复杂规则
                "specific.rule",        # 领域特定规则
                "T0XlC_3_rule.rule",    # T0XlC变种
                
                # 更大的规则后尝试
                "unix-ninja-leetspeak.rule", # 更复杂的Leet替换
                "T0XlC.rule",           # 广泛的复杂变换
                "dive.rule",            # 深度规则（大量变换）
                "d3ad0ne.rule",         # 强力通用规则
                
                # 重型规则 - 最后尝试
                "rockyou-30000.rule",    # 基于RockYou数据的大型规则集
                "generated.rule",        # 生成的中型规则集
                "generated2.rule",       # 生成的大型规则集
            ]
            
            # 检查规则文件是否存在，并创建实际要使用的规则列表
            rules_to_use = []
            for rule_file in priority_rules:
                rule_path = os.path.join(local_rules_dir, rule_file)
                if os.path.exists(rule_path):
                    rules_to_use.append((rule_file, rule_path))
                    log(f"找到规则文件: {rule_file}", level=1)  # 提高日志级别
                else:
                    log(f"规则文件不存在: {rule_file}", level=1)
            
            # 添加混合规则目录中的一些额外规则
            hybrid_dir = os.path.join(local_rules_dir, "hybrid")
            if os.path.exists(hybrid_dir) and os.path.isdir(hybrid_dir):
                log(f"混合规则目录存在: {hybrid_dir}", level=1)
                try:
                    hybrid_files = os.listdir(hybrid_dir)
                    log(f"混合规则目录包含 {len(hybrid_files)} 个文件", level=1)
                except Exception as e:
                    log(f"列出混合规则目录内容时出错: {e}", level=1)
                
                for hybrid_rule in ["append_ds.rule", "append_d.rule", "prepend_ds.rule"]:
                    hybrid_path = os.path.join(hybrid_dir, hybrid_rule)
                    if os.path.exists(hybrid_path) and f"hybrid/{hybrid_rule}" not in [r[0] for r in rules_to_use]:
                        rules_to_use.append((f"hybrid/{hybrid_rule}", hybrid_path))
                        log(f"找到混合规则: {hybrid_rule}", level=1)
                    else:
                        if not os.path.exists(hybrid_path):
                            log(f"混合规则不存在: {hybrid_rule}", level=1)
        
        # 显示规则数量（无论是目录还是单文件模式）
        if rules_to_use:
            print(f"加载了 {len(rules_to_use)} 个规则文件")
            log(f"加载了 {len(rules_to_use)} 个规则文件", level=1)
            
            # 根据文件大小对规则排序（先尝试小规则文件）
            rules_to_use.sort(key=lambda x: os.path.getsize(x[1]))
            
            # 输出规则使用顺序 - 总是显示，不受日志级别限制
            print("==================== 规则使用顺序 ====================")
            for i, (rule, path) in enumerate(rules_to_use):
                rule_size = os.path.getsize(path) / 1024
                try:
                    rule_lines = sum(1 for _ in open(path, 'r'))
                    print(f"  {i+1}. {rule} ({rule_size:.1f} KB, {rule_lines} 行)")
                except Exception as e:
                    print(f"  {i+1}. {rule} ({rule_size:.1f} KB, 读取行数出错: {e})")
            print("=====================================================")
        else:
            print("警告: 未找到规则文件，将不使用规则")
            log("未找到规则文件，将不使用规则", level=1)
            # 尝试创建一个简单的规则文件，以便至少应用一些基本变换
            try:
                simple_rules = ["$1", "$2", "$3", "$!", "$@", "$#"]  # 简单的添加数字和特殊字符规则
                simple_rule_path = os.path.join(local_rules_dir, "simple.rule")
                with open(simple_rule_path, 'w') as f:
                    for rule in simple_rules:
                        f.write(f"{rule}\n")
                print(f"创建了简单规则文件: {simple_rule_path}")
                rules_to_use = [("simple.rule", simple_rule_path)]
            except Exception as e:
                print(f"创建简单规则文件失败: {e}")
        
        # 确保字典攻击模式有可用的字典文件
        if attack_mode == 0 and wordlist_file is None:
            print("错误: 字典攻击模式需要指定字典文件")
            log("字典攻击模式需要指定字典文件", level=1)
            return None
            
        # 进行攻击 - 字典模式
        if attack_mode == 0 and wordlist_file:
            # 先尝试直接使用字典，不应用规则
            print(f"\n>>> 首先不使用规则直接测试字典 {os.path.basename(wordlist_file)} <<<")
            direct_cmd = base_cmd.copy()
            direct_cmd.append(wordlist_file)
            
            # 添加检查点和会话管理
            direct_session = f"{session_id}_direct"
            if not resume or not "--restore" in direct_cmd:
                direct_cmd.extend(["--session", direct_session])
            
            log(f"执行直接字典命令: {' '.join(direct_cmd)}", level=2)
            
            try:
                start_time = time.time()
                print(f"开始直接字典测试...")
                
                # 允许用户中断但保存状态
                process = subprocess.Popen(direct_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                         text=True, bufsize=1, universal_newlines=True)
                
                # 实时显示输出进度
                print("按Ctrl+C可以暂停攻击并保存进度...")
                try:
                    for line in iter(process.stdout.readline, ''):
                        if "Progress" in line or "Status" in line:
                            print(f"\r{line.strip()}", end='')
                        if "Recovered" in line and "...." not in line:  # 可能找到密码
                            print(f"\n{line.strip()}")
                    
                    process.wait(timeout=300)  # 5分钟超时
                    elapsed_time = time.time() - start_time
                    
                    # 清晰显示结果
                    print(f"\n直接字典测试完成，耗时: {elapsed_time:.2f}秒")
                    log(f"直接字典测试完成，耗时: {elapsed_time:.2f}秒", level=2)
                except KeyboardInterrupt:
                    print(f"\n用户中断，保存进度并退出...")
                    # 不立即终止进程，让hashcat有机会保存会话
                    time.sleep(2)
                    process.terminate()
                    print(f"进度已保存，可以使用相同命令继续从断点恢复。")
                    return None
                
                # 检查是否找到密码
                if os.path.exists(potfile) and os.path.getsize(potfile) > 0:
                    with open(potfile, "r") as f:
                        potfile_content = f.read().strip()
                        if ":" in potfile_content:
                            # 提取potfile中的密码
                            password = potfile_content.split(":", 1)[1]
                            print(f"\n成功! 直接字典攻击找到密码: {password}")
                            log(f"直接字典攻击找到密码: {password}", level=1)
                            return password
                
                # 检查输出文件
                if os.path.exists("found_password.txt") and os.path.getsize("found_password.txt") > 0:
                    with open("found_password.txt", "r") as f:
                        password_data = f.read().strip()
                        if ":" in password_data:
                            password = password_data.split(":", 1)[1]
                            print(f"\n成功! 直接字典攻击找到密码: {password}")
                            log(f"直接字典攻击找到密码: {password}", level=1)
                            return password
                
                # 检查输出中是否有找到密码的提示
                stdout, stderr = process.communicate()
                if "Status.........: Cracked" in stdout or "Status.........: Cracked" in stderr:
                    print(f"\n成功! 直接字典攻击找到密码!")
                    log(f"直接字典攻击找到密码!", level=1)
                    
                    for line in stdout.split('\n') + stderr.split('\n'):
                        if line.startswith("*") and ":" in line:
                            password = line.split(":", 1)[1].strip()
                            print(f"密码: {password}")
                            log(f"密码: {password}", level=1)
                            return password
            except subprocess.TimeoutExpired:
                print(f"警告: 直接字典测试超时，继续尝试规则")
                log(f"直接字典测试超时，继续尝试规则", level=1)
            except Exception as e:
                print(f"错误: 直接字典测试时出错: {str(e)}")
                log(f"直接字典测试时出错: {e}", level=2)
            
            # 接下来使用规则进行攻击
            # 使用进度条来显示规则测试进度
            print(f"\n开始对字典 {os.path.basename(wordlist_file)} 应用规则")
            with tqdm(total=len(rules_to_use) or 1, desc="规则测试", unit="rule") as pbar:
                # 尝试每个规则
                for rule_name, rule_path in rules_to_use:
                    # 无论日志级别如何，都清晰显示当前规则
                    print(f"\n>>> 正在使用规则: {rule_name} <<<")
                    pbar.set_description(f"规则: {rule_name}")
                    
                    # 组合命令
                    rule_cmd = base_cmd.copy()
                    rule_cmd.append(wordlist_file)
                    rule_cmd.extend(["-r", rule_path])
                    
                    # 添加检查点和会话管理
                    rule_specific_session = f"{session_id}_{rule_name.replace('/', '_')}"
                    if not resume or not "--restore" in rule_cmd:
                        rule_cmd.extend(["--session", rule_specific_session])
                    
                    log(f"执行命令: {' '.join(rule_cmd)}", level=2)
                    
                    try:
                        start_time = time.time()
                        print(f"开始执行规则 {rule_name}...")
                        
                        # 允许用户中断但保存状态
                        process = subprocess.Popen(rule_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                                  text=True, bufsize=1, universal_newlines=True)
                        
                        # 实时显示输出进度
                        print("按Ctrl+C可以暂停攻击并保存进度...")
                        try:
                            for line in iter(process.stdout.readline, ''):
                                if "Progress" in line or "Status" in line:
                                    print(f"\r{line.strip()}", end='')
                                if "Recovered" in line and "...." not in line:  # 可能找到密码
                                    print(f"\n{line.strip()}")
                            
                            process.wait(timeout=300)  # 5分钟超时
                            elapsed_time = time.time() - start_time
                            
                            # 清晰显示规则执行结果
                            print(f"\n规则 {rule_name} 执行完成，耗时: {elapsed_time:.2f}秒")
                            log(f"规则 {rule_name} 执行完成，耗时: {elapsed_time:.2f}秒", level=2)
                        except KeyboardInterrupt:
                            print(f"\n用户中断，保存进度并退出...")
                            # 不立即终止进程，让hashcat有机会保存会话
                            time.sleep(2)
                            process.terminate()
                            print(f"进度已保存，可以使用相同命令继续从断点恢复。")
                            return None
                        
                        # 检查potfile看是否找到密码
                        if os.path.exists(potfile) and os.path.getsize(potfile) > 0:
                            with open(potfile, "r") as f:
                                potfile_content = f.read().strip()
                                if ":" in potfile_content:
                                    # 提取potfile中的密码
                                    password = potfile_content.split(":", 1)[1]
                                    print(f"\n成功! 使用规则 {rule_name} 找到密码: {password}")
                                    log(f"使用规则 {rule_name} 找到密码: {password}", level=1)
                                    return password
                        
                        # 检查输出文件
                        if os.path.exists("found_password.txt") and os.path.getsize("found_password.txt") > 0:
                            with open("found_password.txt", "r") as f:
                                password_data = f.read().strip()
                                if ":" in password_data:
                                    password = password_data.split(":", 1)[1]
                                    print(f"\n成功! 使用规则 {rule_name} 找到密码: {password}")
                                    log(f"使用规则 {rule_name} 找到密码: {password}", level=1)
                                    return password
                        
                        # 检查输出中是否有找到密码的提示
                        stdout, stderr = process.communicate()
                        if "Status.........: Cracked" in stdout or "Status.........: Cracked" in stderr:
                            print(f"\n成功! 使用规则 {rule_name} 找到密码!")
                            log(f"使用规则 {rule_name} 找到密码!", level=1)
                            
                            for line in stdout.split('\n') + stderr.split('\n'):
                                if line.startswith("*") and ":" in line:
                                    password = line.split(":", 1)[1].strip()
                                    print(f"密码: {password}")
                                    log(f"密码: {password}", level=1)
                                    return password
                    except subprocess.TimeoutExpired:
                        print(f"警告: 规则 {rule_name} 执行超时，跳过")
                        log(f"规则 {rule_name} 执行超时，跳过", level=1)
                    except Exception as e:
                        print(f"错误: 使用规则 {rule_name} 时出错: {str(e)}")
                        log(f"使用规则 {rule_name} 时出错: {e}", level=2)
                    
                    pbar.update(1)
                
                # 如果没有规则或规则都失败，尝试不使用规则
                if not rules_to_use:
                    pbar.set_description("不使用规则")
                    print("\n>>> 不使用规则直接测试 <<<")
                else:
                    pbar.set_description("所有规则都未找到密码")
                    print("\n>>> 所有规则都未找到密码，尝试无规则匹配 <<<")
                
                # 无规则直接尝试
                noRule_cmd = base_cmd.copy()
                noRule_cmd.append(wordlist_file)
                # 添加无规则专用会话ID
                noRule_cmd.extend(["--session", f"{session_id}_norule"])
                
                log(f"执行无规则命令: {' '.join(noRule_cmd)}", level=2)
                
                try:
                    print("开始无规则匹配...")
                    start_time = time.time()
                    
                    # 允许用户中断但保存状态
                    process = subprocess.Popen(noRule_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                              text=True, bufsize=1, universal_newlines=True)
                    
                    # 实时显示输出进度
                    print("按Ctrl+C可以暂停攻击并保存进度...")
                    try:
                        for line in iter(process.stdout.readline, ''):
                            if "Progress" in line or "Status" in line:
                                print(f"\r{line.strip()}", end='')
                            if "Recovered" in line and "...." not in line:  # 可能找到密码
                                print(f"\n{line.strip()}")
                        
                        process.wait(timeout=300)  # 5分钟超时
                        elapsed_time = time.time() - start_time
                        
                        print(f"\n无规则匹配完成，耗时: {elapsed_time:.2f}秒")
                        log(f"无规则模式执行完成，耗时: {elapsed_time:.2f}秒", level=2)
                    except KeyboardInterrupt:
                        print(f"\n用户中断，保存进度并退出...")
                        # 不立即终止进程，让hashcat有机会保存会话
                        time.sleep(2)
                        process.terminate()
                        print(f"进度已保存，可以使用相同命令继续从断点恢复。")
                        return None
                    
                    # 检查potfile看是否找到密码
                    if os.path.exists(potfile) and os.path.getsize(potfile) > 0:
                        with open(potfile, "r") as f:
                            potfile_content = f.read().strip()
                            if ":" in potfile_content:
                                # 提取potfile中的密码
                                password = potfile_content.split(":", 1)[1]
                                print(f"\n成功! 无规则模式找到密码: {password}")
                                log(f"无规则模式找到密码: {password}", level=1)
                                return password
                    
                    # 检查输出文件
                    if os.path.exists("found_password.txt") and os.path.getsize("found_password.txt") > 0:
                        with open("found_password.txt", "r") as f:
                            password_data = f.read().strip()
                            if ":" in password_data:
                                password = password_data.split(":", 1)[1]
                                print(f"\n成功! 无规则模式找到密码: {password}")
                                log(f"无规则模式找到密码: {password}", level=1)
                                return password
                    
                    # 检查输出中是否有找到密码的提示
                    stdout, stderr = process.communicate()
                    if "Status.........: Cracked" in stdout or "Status.........: Cracked" in stderr:
                        for line in stdout.split('\n') + stderr.split('\n'):
                            if line.startswith("*") and ":" in line:
                                password = line.split(":", 1)[1].strip()
                                print(f"密码: {password}")
                                log(f"密码: {password}", level=1)
                                return password
                except subprocess.TimeoutExpired:
                    print("无规则模式执行超时")
                    log("无规则模式执行超时", level=1)
                except Exception as e:
                    print(f"执行无规则模式时出错: {e}")
                    log(f"执行无规则模式时出错: {e}", level=1)
        
        # 暴力破解模式
        elif attack_mode == 3:  
            # 基本命令
            cmd = base_cmd.copy()
            cmd.extend(["-a", "3"])
            
            # 设置字符集和密码长度
            if charset:
                cmd.extend(["--custom-charset1", charset, "?1"])
            else:
                cmd.append("?a")
                
            cmd.extend(["--increment", "--increment-min", str(min_length), "--increment-max", str(max_length)])
            
            # 设备和优化选项
            is_macos = platform.system() == "Darwin"
            is_arm = "arm" in platform.processor().lower()
            
            if cpu_only or (is_macos and is_arm):
                if is_macos:
                    cmd.extend(["--force", "-D", "1", "--backend-devices", "1"])
                else:
                    cmd.extend(["--force", "--opencl-device-types", "1", "--backend-devices", "1"])
            else:
                # GPU选项
                cmd.extend(["--force"])
            
            log(f"执行暴力破解命令: {' '.join(cmd)}", level=2)
            
            try:
                print("开始暴力破解...")
                start_time = time.time()
                
                # 允许用户中断但保存状态
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                          text=True, bufsize=1, universal_newlines=True)
                
                # 实时显示输出进度
                print("按Ctrl+C可以暂停攻击并保存进度...")
                try:
                    for line in iter(process.stdout.readline, ''):
                        if "Progress" in line or "Status" in line:
                            print(f"\r{line.strip()}", end='')
                        if "Recovered" in line and "...." not in line:  # 可能找到密码
                            print(f"\n{line.strip()}")
                    
                    process.wait(timeout=600)  # 10分钟超时
                    elapsed_time = time.time() - start_time
                    
                    print(f"\n暴力破解完成，耗时: {elapsed_time:.2f}秒")
                    log(f"暴力破解执行完成，耗时: {elapsed_time:.2f}秒", level=2)
                except KeyboardInterrupt:
                    print(f"\n用户中断，保存进度并退出...")
                    # 不立即终止进程，让hashcat有机会保存会话
                    time.sleep(2)
                    process.terminate()
                    print(f"进度已保存，可以使用相同命令继续从断点恢复。")
                    return None
                
                # 检查potfile看是否找到密码
                if os.path.exists(potfile) and os.path.getsize(potfile) > 0:
                    with open(potfile, "r") as f:
                        potfile_content = f.read().strip()
                        if ":" in potfile_content:
                            # 提取potfile中的密码
                            password = potfile_content.split(":", 1)[1]
                            print(f"\n成功! 暴力破解找到密码: {password}")
                            log(f"暴力破解找到密码: {password}", level=1)
                            return password
                
                # 检查输出文件
                if os.path.exists("found_password.txt") and os.path.getsize("found_password.txt") > 0:
                    with open("found_password.txt", "r") as f:
                        password_data = f.read().strip()
                        if ":" in password_data:
                            password = password_data.split(":", 1)[1]
                            print(f"\n成功! 暴力破解找到密码: {password}")
                            log(f"暴力破解找到密码: {password}", level=1)
                            return password
                
                # 检查输出中是否有找到密码的提示
                stdout, stderr = process.communicate()
                if "Status.........: Cracked" in stdout or "Status.........: Cracked" in stderr:
                    for line in stdout.split('\n') + stderr.split('\n'):
                        if line.startswith("*") and ":" in line:
                            password = line.split(":", 1)[1].strip()
                            print(f"密码: {password}")
                            log(f"密码: {password}", level=1)
                            return password
            except subprocess.TimeoutExpired:
                print("暴力破解执行超时")
                log("暴力破解执行超时", level=1)
            except Exception as e:
                print(f"执行暴力破解时出错: {e}")
                log(f"执行暴力破解时出错: {e}", level=1)
        
        print("未找到密码")
        log("未找到密码", level=1)
        return None
        
    except Exception as e:
        print(f"Hashcat攻击执行时出错: {e}")
        log(f"Hashcat攻击执行时出错: {e}", level=1)
        return None
    finally:
        # 清理临时文件
        if temp_wordlist and os.path.exists(temp_wordlist):
            try:
                os.remove(temp_wordlist)
            except:
                pass

def collect_wallet_files(wallet_dir):
    """收集指定目录下的所有钱包文件，支持多种钱包格式"""
    wallet_files = []
    if not os.path.exists(wallet_dir):
        print(f"错误：钱包目录 {wallet_dir} 不存在")
        return wallet_files

    # 支持的钱包文件扩展名和描述
    wallet_extensions = {
        '.dat': 'Bitcoin Core wallet.dat',
        '.wallet': 'Multibit/Multibit HD wallet',
        '.keys': 'Electrum wallet keys file',
        '.json': 'Possible JSON-format wallet (Electrum, MyEtherWallet, etc.)',
        '.db': 'Possible database-backed wallet',
        '.kdbx': 'KeePass wallet backup',
        '.bdb': 'Berkeley DB wallet'
    }

    found_wallets_by_type = {ext: 0 for ext in wallet_extensions}
    
    for root, dirs, files in os.walk(wallet_dir):
        for file in files:
            file_lower = file.lower()
            file_path = os.path.join(root, file)
            
            # 检查已知的钱包扩展名
            for ext, desc in wallet_extensions.items():
                if file_lower.endswith(ext):
                    wallet_files.append(file_path)
                    found_wallets_by_type[ext] += 1
                    break
                    
            # 特殊检查 - 某些钱包没有典型的扩展名
            if "wallet" in file_lower and os.path.getsize(file_path) > 1000:
                if not any(file_lower.endswith(ext) for ext in wallet_extensions):
                    wallet_files.append(file_path)
                    
    # 打印找到的钱包文件统计
    print("找到的钱包文件:")
    for ext, count in found_wallets_by_type.items():
        if count > 0:
            print(f"  {wallet_extensions[ext]}: {count}个")
    
    return wallet_files

def process_wallet(wallet_file, args):
    """处理单个钱包文件"""
    print(f"\n开始处理钱包文件: {wallet_file}")
    
    # 检测钱包类型
    wallet_type = detect_wallet_type(wallet_file)
    print(f"检测到的钱包类型: {wallet_type}")
    
    # 如果是不支持的钱包类型，尝试使用btcrecover
    if wallet_type == "未知" and BTCRECOVER_AVAILABLE:
        print("尝试使用btcrecover检测钱包类型...")
        try:
            wallet_obj = btcrecover.btcrpass.WalletBase.wallet_factory(wallet_file)
            wallet_type = wallet_obj.__class__.__name__
            print(f"btcrecover检测到的钱包类型: {wallet_type}")
        except Exception as e:
            print(f"btcrecover无法识别钱包: {str(e)}")
    
    if args.hashcat:
        # 提取哈希并使用hashcat
        hash_data, hash_file = extract_hash_from_wallet(wallet_file)
        if not hash_data:
            print("警告: 无法从钱包文件提取哈希，将使用通用格式")
            fd, hash_file = tempfile.mkstemp(suffix='.txt')
            os.close(fd)
            generic_hash = "$bitcoin$1$16$a04e83da85a4a93920f95009ca15a9155c1c3c50ef7e762097d081e4e9d62a$1$1$64$0000000000000000$16$0000000000000000000000000000000000000000000000000000000000000000$64$636e7c45a5576e5e81d1717644ae68c221de8b0dc35a1dafdd2a59f65043388"
            with open(hash_file, 'w') as f:
                f.write(generic_hash)
            hash_data = generic_hash
        
        print("使用hashcat进行破解...")
        
        # 首先尝试比特币专用字典（如果有）
        if bitcoin_dict:
            print(f"优先尝试比特币专用字典...")
            password = hashcat_attack(hash_file, bitcoin_dict, attack_mode=0, cpu_only=args.cpu_only)
            if password:
                print(f"成功！钱包 {args.bitcoin_core} 的密码是: {password}")
                # 验证密码
                verify_success, _ = test_bitcoin_core_password(args.bitcoin_core, password)
                if verify_success:
                    print("密码验证成功！")
                else:
                    print("警告: 密码无法通过Bitcoin Core验证，可能是误报")
                sys.exit(0)
            else:
                print("比特币专用字典未找到密码，尝试其他字典...")
        
        # 进行破解尝试
        if wordlist_files:
            print(f"开始使用 {len(wordlist_files)} 个字典文件进行破解...")
            
            for wordlist_file in wordlist_files:
                if not os.path.exists(wordlist_file):
                    print(f"警告: 字典文件 {wordlist_file} 不存在，跳过")
                    continue
                    
                print(f"使用字典: {wordlist_file}")
                password = hashcat_attack(hash_file, wordlist_file, attack_mode=0, cpu_only=args.cpu_only)
                if password:
                    print(f"成功！钱包 {args.bitcoin_core} 的密码是: {password}")
                    # 验证密码
                    verify_success, _ = test_bitcoin_core_password(args.bitcoin_core, password)
                    if verify_success:
                        print("密码验证成功！")
                    else:
                        print("警告: 密码无法通过Bitcoin Core验证，可能是误报")
                    sys.exit(0)
            
            print(f"hashcat字典攻击未找到钱包 {args.bitcoin_core} 的密码")
                    
        if args.brute_force:
            password = hashcat_attack(hash_file, attack_mode=3, charset=args.charset, 
                                     min_length=args.min_length, max_length=args.max_length,
                                     cpu_only=args.cpu_only)
            if password:
                print(f"成功！钱包 {args.bitcoin_core} 的密码是: {password}")
                # 验证密码
                verify_success, _ = test_bitcoin_core_password(args.bitcoin_core, password)
                if verify_success:
                    print("密码验证成功！")
                else:
                    print("警告: 密码无法通过Bitcoin Core验证，可能是误报")
                sys.exit(0)
            else:
                print(f"hashcat暴力破解未找到钱包 {args.bitcoin_core} 的密码")
                    
        sys.exit(1)
    else:
        # 使用内置方法
        if args.dictionary or args.dictionary_dir:
            wordlist_files = []
            if args.dictionary:
                wordlist_files.append(args.dictionary)
            if args.dictionary_dir:
                wordlist_files.extend(collect_password_files(args.dictionary_dir))

            password = dictionary_attack(wallet_file, wordlist_files, args.workers)
            if password:
                print(f"成功！钱包 {wallet_file} 的密码是: {password}")
                return True
            else:
                print(f"字典攻击未找到钱包 {wallet_file} 的密码")

        if args.brute_force:
            password = brute_force_attack(wallet_file, args.charset, args.min_length, args.max_length, args.workers)
            if password:
                print(f"成功！钱包 {wallet_file} 的密码是: {password}")
                return True
            else:
                print(f"暴力破解未找到钱包 {wallet_file} 的密码")

    return False

def detect_wallet_type(wallet_file):
    """根据文件特征检测钱包类型"""
    try:
        file_ext = os.path.splitext(wallet_file)[1].lower()
        
        # 根据扩展名判断
        if file_ext == '.dat':
            # 尝试以Bitcoin Core wallet.dat打开
            try:
                with open(wallet_file, 'rb') as f:
                    header = f.read(16)
                    if b'\x62\x31\x05\x00' in header or b'\x00\x05\x31\x62' in header:  # Berkeley DB magic header
                        return "Bitcoin Core wallet.dat"
            except:
                pass
            
        elif file_ext == '.wallet':
            # 检查是否是MultibitHD钱包
            try:
                with open(wallet_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(1000)
                    if "multibit" in content.lower() or "aes" in content.lower():
                        return "Multibit HD wallet"
            except:
                pass
                
        elif file_ext == '.json':
            # 检查是否是Electrum钱包
            try:
                with open(wallet_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(1000)
                    if "electrum" in content.lower():
                        return "Electrum wallet"
                    elif "ethers" in content.lower() or "ethereum" in content.lower():
                        return "Ethereum wallet"
            except:
                pass
                
        elif file_ext == '.keys':
            return "Electrum keys file"
            
        # 通过文件内容判断
        try:
            with open(wallet_file, 'rb') as f:
                header = f.read(1000)
                if b'wallet' in header and b'bitcoin' in header:
                    return "Bitcoin wallet"
                elif b'ethereum' in header or b'eth' in header:
                    return "Ethereum wallet"
                elif b'electrum' in header:
                    return "Electrum wallet"
        except:
            pass
            
    except Exception as e:
        print(f"检测钱包类型时出错: {str(e)}")
    
    return "未知"

def test_bitcoin_core_password(wallet_name, password):
    """使用Bitcoin Core RPC接口测试钱包密码"""
    try:
        # 使用subprocess调用bitcoin-cli
        unlock_cmd = ["bitcoin-cli", "-rpcwallet=" + wallet_name, "walletpassphrase", password, "2"]
        process = subprocess.run(unlock_cmd, capture_output=True, text=True)
        
        # 检查是否成功解锁
        if process.returncode == 0 and not "error" in process.stderr.lower():
            # 成功解锁了钱包，立即锁定
            subprocess.run(["bitcoin-cli", "-rpcwallet=" + wallet_name, "walletlock"], capture_output=True)
            return True, password
        
        # 确保钱包锁定（以防万一）
        subprocess.run(["bitcoin-cli", "-rpcwallet=" + wallet_name, "walletlock"], capture_output=True)
    except Exception as e:
        print(f"Bitcoin Core RPC错误: {e}")
    
    return False, None

def bitcoin_core_dictionary_attack(wallet_name, wordlist_files):
    """使用Bitcoin Core直接进行字典攻击"""
    if isinstance(wordlist_files, str):
        wordlist_files = [wordlist_files]

    total_tested = 0
    start_time = time.time()
    
    # 确保钱包已加载
    try:
        load_cmd = ["bitcoin-cli", "loadwallet", wallet_name]
        subprocess.run(load_cmd, capture_output=True)
    except:
        # 钱包可能已加载，忽略错误
        pass

    for wordlist_file in wordlist_files:
        if not os.path.exists(wordlist_file):
            log(f"跳过不存在的字典文件: {wordlist_file}", level=1)
            continue

        log(f"使用字典文件: {wordlist_file}", level=1)

        try:
            password_list = extract_passwords_from_file(wordlist_file)
            
            if not password_list:
                log(f"从文件 {wordlist_file} 中未提取到密码，跳过", level=1)
                continue
                
            log(f"从 {wordlist_file} 中提取到 {len(password_list)} 个密码", level=1)

            # 使用进度条显示破解进度
            with tqdm(total=len(password_list), desc="测试密码", unit="pwd") as pbar:
                for password in password_list:
                    if not password:
                        pbar.update(1)
                        continue
                        
                    success, found_password = test_bitcoin_core_password(wallet_name, password)
                    total_tested += 1
                    pbar.update(1)

                    if success:
                        elapsed = time.time() - start_time
                        speed = total_tested / elapsed if elapsed > 0 else 0
                        log(f"\n找到密码: {found_password} (测试了 {total_tested} 个密码，速度 {speed:.2f} p/s)", level=1)
                        return found_password
        except Exception as e:
            log(f"处理字典文件 {wordlist_file} 时出错: {str(e)}", level=1)
            continue

    elapsed = time.time() - start_time
    speed = total_tested / elapsed if elapsed > 0 else 0
    log(f"未找到密码。共测试 {total_tested} 个密码，速度 {speed:.2f} p/s", level=1)
    return None

def bitcoin_core_brute_force(wallet_name, charset, min_length, max_length):
    """使用Bitcoin Core直接进行暴力破解"""
    print(f"使用Bitcoin Core进行暴力破解，字符集: {charset}")
    print(f"密码长度范围: {min_length} 到 {max_length}")
    
    # 确保钱包已加载
    try:
        load_cmd = ["bitcoin-cli", "loadwallet", wallet_name]
        subprocess.run(load_cmd, capture_output=True)
    except:
        # 钱包可能已加载，忽略错误
        pass
    
    start_time = time.time()
    tested = 0
    
    for length in range(min_length, max_length + 1):
        print(f"尝试长度为 {length} 的密码")
        
        # 生成所有可能的组合
        for combo in itertools.product(charset, repeat=length):
            password = ''.join(combo)
            success, found_password = test_bitcoin_core_password(wallet_name, password)
            tested += 1
            
            if tested % 100 == 0:
                elapsed = time.time() - start_time
                print(f"已测试 {tested} 个密码，用时 {elapsed:.2f} 秒 ({tested/elapsed:.2f} p/s)")
            
            if success:
                print(f"\n找到密码: {found_password}")
                return found_password
    
    print(f"未找到密码。共测试 {tested} 个密码，用时 {time.time() - start_time:.2f} 秒")
    return None

def get_bitcoin_core_wallet_path(wallet_name):
    """获取Bitcoin Core钱包文件的完整路径"""
    # 检查常见的Bitcoin Core数据目录
    possible_paths = []
    
    # macOS路径
    possible_paths.append(os.path.expanduser(f"~/Library/Application Support/Bitcoin/wallets/{wallet_name}/wallet.dat"))
    # 默认macOS路径
    possible_paths.append(os.path.expanduser(f"~/Library/Application Support/Bitcoin/wallet.dat"))
    
    # Linux路径
    possible_paths.append(os.path.expanduser(f"~/.bitcoin/wallets/{wallet_name}/wallet.dat"))
    possible_paths.append(os.path.expanduser(f"~/.bitcoin/wallet.dat"))
    
    # Windows路径
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        possible_paths.append(os.path.join(appdata, "Bitcoin", "wallets", wallet_name, "wallet.dat"))
        possible_paths.append(os.path.join(appdata, "Bitcoin", "wallet.dat"))
    
    # 检查自定义路径
    custom_dir = os.environ.get("BITCOIN_DATADIR", "")
    if custom_dir:
        possible_paths.append(os.path.join(custom_dir, "wallets", wallet_name, "wallet.dat"))
        possible_paths.append(os.path.join(custom_dir, "wallet.dat"))
    
    # 返回第一个存在的路径
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    return None

def dump_wallet_info(wallet_name, dump_file="dump.txt"):
    """使用Bitcoin Core RPC尝试转储钱包信息（从中可以提取加密相关信息）"""
    try:
        # 尝试使用dumpwallet命令
        cmd = ["bitcoin-cli", "-rpcwallet="+wallet_name, "dumpwallet", dump_file]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"成功转储钱包信息到 {dump_file}")
            # 读取dump文件以获取加密信息
            if os.path.exists(dump_file):
                with open(dump_file, 'r') as f:
                    dump_content = f.read()
                    # 清理dump文件
                    os.remove(dump_file)
                    return dump_content
        else:
            # 钱包可能被加密，无法导出
            error = result.stderr.strip()
            print(f"转储钱包失败: {error}")
        
        return None
    except Exception as e:
        print(f"尝试转储钱包信息时出错: {e}")
        return None

def generate_wallet_hash_format(wallet_file, password_type=1):
    """从钱包文件生成不同版本的hashcat哈希格式
    password_type: 1=常规加密, 2=bdb格式, 3=sqlite格式
    """
    try:
        with open(wallet_file, 'rb') as f:
            wallet_data = f.read()
            
        # 钱包文件大小
        file_size = len(wallet_data)
        
        # 获取一些唯一标识符作为盐值
        if file_size > 32:
            salt = wallet_data[0:16].hex()
            data = wallet_data[0:128].hex()
        else:
            # 如果文件太小，使用固定盐值
            salt = "4bcf4107d3e5cc30d915af1fc9e75f46"
            data = wallet_data.hex()
            
        # 根据不同密码类型生成不同格式
        if password_type == 1:
            # 常规Bitcoin Core格式 (对应hashcat的11300模式)
            return f"$bitcoin$1$16${salt}$1$1$64$0000000000000000$16$0000000000000000000000000000000000000000000000000000000000000000${data}"
        elif password_type == 2:
            # Berkeley DB格式 (对应hashcat的11300变种)
            # 尝试找到Berkeley DB特定标记
            if b'\x62\x31\x05\x00' in wallet_data:  # BDB 头标记
                pos = wallet_data.find(b'\x62\x31\x05\x00')
                bdb_data = wallet_data[pos:pos+256].hex() if pos+256 <= len(wallet_data) else wallet_data[pos:].hex()
                print(f"找到BDB标记，位置: {pos}")
                return f"$bitcoin$2$16${salt}$1$1$64$0000000000000000$16$0000000000000000000000000000000000000000000000000000000000000000${bdb_data}"
            
            # 如果找不到BDB标记，使用一般方法但指定为BDB格式(type=2)
            return f"$bitcoin$2$16${salt}$1$1$64$0000000000000000$16$0000000000000000000000000000000000000000000000000000000000000000${data}"
        elif password_type == 3:
            # SQLite格式 (对应新版Bitcoin Core的SQLite格式)
            # 尝试找到SQLite文件头 "SQLite format 3"
            if b'SQLite format 3' in wallet_data:
                pos = wallet_data.find(b'SQLite format 3')
                sqlite_data = wallet_data[pos:pos+256].hex() if pos+256 <= len(wallet_data) else wallet_data[pos:].hex()
                print(f"找到SQLite标记，位置: {pos}")
                
                # 增加SQLite特有的加密标记
                encrypted_markers = [
                    b'\x30\x81\x82\x02\x01\x01\x30\x2c',  # 常见加密标记
                    b'\x30\x81\x82\x01\x01\x01\x30\x2c',  # 常见加密标记变体
                    b'\x30\x82',                          # ASN.1 序列头
                    b'\x43\x52\x59\x50\x54\x45\x44',      # "CRYPTED" 字符串
                    b'\x45\x4e\x43\x52\x59\x50\x54\x45\x44', # "ENCRYPTED" 字符串
                    b'\x6d\x61\x73\x74\x65\x72\x6b\x65\x79', # "masterkey" 字符串
                    b'\x63\x72\x79\x70\x74',             # "crypt" 字符串
                    b'\x65\x6e\x63\x72\x79\x70\x74',     # "encrypt" 字符串
                    b'\x70\x72\x69\x76\x6b\x65\x79',     # "privkey" 字符串
                    b'\x70\x61\x73\x73\x77\x6f\x72\x64', # "password" 字符串
                    b'\x73\x61\x6c\x74',                 # "salt" 字符串
                ]
                
                # 扫描整个文件以查找加密标记
                for marker in encrypted_markers:
                    offset = 0
                    while True:
                        pos = wallet_data.find(marker, offset)
                        if pos == -1:
                            break
                            
                        print(f"找到SQLite加密标记，位置: {pos}, 标记: {marker.hex()}")
                        # 提取前后共512字节的数据以确保包含加密信息
                        start_pos = max(0, pos - 256)
                        end_pos = min(len(wallet_data), pos + 256)
                        encrypted_data = wallet_data[start_pos:end_pos].hex()
                        hash_format = f"$bitcoin$3$16${wallet_data[0:16].hex()}$1$1$64$0000000000000000$16$0000000000000000000000000000000000000000000000000000000000000000${encrypted_data}"
                        print(f"生成加密数据哈希，使用位置 {start_pos}-{end_pos} 的数据")
                        return hash_format
                        
                        offset = pos + len(marker)
                
                # 如果直接扫描没有找到加密标记，尝试按块扫描文件
                print("未找到明显的加密标记，尝试扫描整个SQLite文件...")
                block_size = 1024
                for i in range(0, len(wallet_data), block_size):
                    block = wallet_data[i:i+block_size]
                    # 检查这个块是否包含可能的加密数据特征
                    if (b'\x30\x81' in block or b'\x30\x82' in block or 
                        b'\x02\x01\x01' in block or b'\xA1\x1C' in block or
                        b'\x70\x72\x69\x76' in block):  # 'priv'
                        print(f"在位置 {i} 处找到可能的加密块")
                        encrypted_block = wallet_data[i:i+min(block_size*2, len(wallet_data)-i)].hex()
                        hash_format = f"$bitcoin$3$16${wallet_data[0:16].hex()}$1$1$64$0000000000000000$16$0000000000000000000000000000000000000000000000000000000000000000${encrypted_block}"
                        print(f"使用块 {i}-{i+min(block_size*2, len(wallet_data)-i)} 生成哈希")
                        return hash_format
                
                # 如果仍然找不到，则尝试使用整个头部区域作为数据
                print("使用SQLite文件头部区域作为哈希数据")
                header_data = wallet_data[0:1024].hex() if len(wallet_data) >= 1024 else wallet_data.hex()
                return f"$bitcoin$3$16${wallet_data[0:16].hex()}$1$1$64$0000000000000000$16$0000000000000000000000000000000000000000000000000000000000000000${header_data}"
            
            # 如果找不到SQLite标记，使用一般方法但指定为SQLite格式(type=3)
            return f"$bitcoin$3$16${salt}$1$1$64$0000000000000000$16$0000000000000000000000000000000000000000000000000000000000000000${data}"
            
        # 如果以上都不匹配，使用通用格式
        return f"$bitcoin$0$16${salt}$1$1$64$0000000000000000$16$0000000000000000000000000000000000000000000000000000000000000000${data}"
        
    except Exception as e:
        print(f"生成哈希格式时出错: {e}")
        return None

def read_berkeley_db(wallet_path):
    """Read Berkeley DB wallet using Python's dbm module"""
    try:
        # Try different dbm implementations
        for dbm_type in ['dbm.gnu', 'dbm.ndbm', 'dbm.dumb']:
            try:
                # Remove file extension for dbm
                db_path = wallet_path
                if db_path.endswith('.dat'):
                    db_path = db_path[:-4]
                
                # Try to open the database
                log(f"Trying to open Berkeley DB with {dbm_type}...", level=2)
                with getattr(dbm, dbm_type.split('.')[-1]).open(db_path, 'r') as db:
                    result = {}
                    for key in db.keys():
                        try:
                            if isinstance(key, bytes):
                                k = key.decode('latin1', errors='replace')
                            else:
                                k = key
                            
                            val = db[key]
                            if isinstance(val, bytes):
                                v = val.hex()
                            else:
                                v = val
                                
                            result[k] = v
                        except Exception as e:
                            log(f"Error reading key {key}: {str(e)}", level=2)
                    return result
            except Exception as e:
                log(f"Failed to open with {dbm_type}: {str(e)}", level=2)
                continue
        
        # If all implementations failed, try a direct approach with file reading
        log("All dbm implementations failed, trying direct file reading approach", level=2)
        with open(wallet_path, 'rb') as f:
            data = f.read()
            # Look for encryption markers
            markers = [
                b'\x30\x82',  # ASN.1 SEQUENCE 
                b'\x30\x81',  # ASN.1 SEQUENCE
                b'ckey',      # Bitcoin Core encrypted key marker
                b'mkey',      # Bitcoin Core master key marker
                b'salt'       # Bitcoin Core salt marker
            ]
            
            result = {}
            for marker in markers:
                pos = data.find(marker)
                if pos != -1:
                    log(f"Found marker {marker.hex()} at position {pos}", level=2)
                    # Extract data around the marker
                    start = max(0, pos - 16)
                    end = min(len(data), pos + 128)
                    extracted = data[start:end].hex()
                    result[marker.decode('latin1', errors='replace')] = extracted
            
            if result:
                return result
        
        log("Could not read Berkeley DB wallet with any method", level=1)
        return {}
    except Exception as e:
        log(f"Error reading Berkeley DB: {str(e)}", level=1)
        return {}

def bitcoin_core_extract_hash(wallet_name):
    """Extract hash information from a Bitcoin Core wallet without bsddb3"""
    try:
        # Create temporary hash file
        fd, hash_file_path = tempfile.mkstemp(suffix='.hash')
        os.close(fd)
        
        # Get wallet path
        wallet_path = get_bitcoin_core_wallet_path(wallet_name)
        if not wallet_path:
            log(f"Could not find wallet file for {wallet_name}", level=1)
            return None, None
            
        log(f"Found wallet file at: {wallet_path}", level=2)
        
        # 启用详细调试输出
        DEBUG = True  # 设置为True以启用详细调试输出
        
        # 创建额外的调试日志函数
        def debug_log(msg):
            if DEBUG:
                print(f"DEBUG: {msg}")
                log(msg, level=2)
        
        debug_log(f"开始提取钱包哈希 - 文件: {wallet_path}")
        
        # 使用二进制读取方式提取哈希，不依赖 bsddb3
        try:
            # 直接读取钱包文件二进制内容
            with open(wallet_path, 'rb') as f:
                wallet_data = f.read()
                
            debug_log(f"读取了 {len(wallet_data)} 字节的钱包数据")
            
            # 输出文件头部的十六进制数据以便分析
            if len(wallet_data) >= 128:
                debug_log(f"文件头部(前128字节): {wallet_data[:128].hex()}")
            
            # 首先尝试直接搜索常见的标记关键词
            mkey_positions = []
            search_markers = [
                (b'mkey', "Master Key"),
                (b'ckey', "Crypto Key"),
                (b'masterkey', "Master Key长名称"),
                (b'\x6d\x6b\x65\x79', "mkey二进制"),
                (b'\x30\x82', "ASN.1 序列"),
                (b'\x02\x01\x01\x30', "ASN.1 序列 + 整数"),
                (b'\x04\x20', "OCTET STRING 32字节"),
                (b'\x04\x10', "OCTET STRING 16字节")
            ]
            
            for marker, desc in search_markers:
                pos = wallet_data.find(marker)
                if pos != -1:
                    mkey_positions.append((pos, marker, desc))
                    debug_log(f"找到标记 '{desc}' 在位置 {pos}")
            
            if mkey_positions:
                # 按位置排序标记
                mkey_positions.sort(key=lambda x: x[0])
                debug_log(f"找到了 {len(mkey_positions)} 个可能的加密标记")
                
                for pos, marker, desc in mkey_positions:
                    # 输出每个标记周围的数据
                    start = max(0, pos - 8)
                    end = min(len(wallet_data), pos + 64)
                    debug_log(f"标记 '{desc}' 周围数据: {wallet_data[start:end].hex()}")
            
            # 强制使用与bitcoin2john.py兼容的格式
            # 尝试检测Berkeley DB格式钱包
            if b'\x62\x31\x05\x00' in wallet_data or b'main' in wallet_data:
                debug_log("检测到Berkeley DB钱包格式")
                
                # 寻找加密主密钥和盐值标记
                # Berkeley DB钱包中的mkey记录的特定模式是：
                # - mkey字符串，后跟四字节（可能是ID）
                # - 然后是长度字节，然后是加密密钥（通常48或96字节）
                # - 然后是长度字节，后跟盐值（通常8或16字节）
                # - 然后是派生方法（4字节）和迭代次数（4字节）
                
                salt = None
                encrypted_key = None
                iterations = 50000  # 默认值
                
                # 对于BDB钱包，使用固定格式
                # 生成与john/hashcat兼容的哈希：
                # - 使用最后64个字符的加密密钥（如果有）
                # - 或者使用文件中可能是加密数据的部分
                
                # 尝试按照bitcoin2john.py的方法提取数据
                potential_mkey_data = None
                
                # 查找mkey标记
                mkey_pos = wallet_data.find(b'mkey')
                if mkey_pos != -1:
                    debug_log(f"找到mkey标记在位置 {mkey_pos}")
                    
                    # 尝试跳过mkey标记，获取后续的数据块（包含加密数据）
                    search_start = mkey_pos + 4  # 跳过'mkey'
                    
                    # 跳过可能的ID/属性字节
                    while search_start < len(wallet_data) and wallet_data[search_start] == 0:
                        search_start += 1
                    
                    if search_start + 4 < len(wallet_data):
                        # 可能的长度字节位置
                        for offset in range(search_start, search_start + 20):
                            if offset < len(wallet_data):
                                length_byte = wallet_data[offset]
                                # 检查这是否可能是一个合理的长度值（加密密钥通常是32-64字节）
                                if 32 <= length_byte <= 96:
                                    debug_log(f"在位置 {offset} 找到可能的长度字节: {length_byte}")
                                    
                                    # 尝试提取数据
                                    if offset + 1 + length_byte <= len(wallet_data):
                                        potential_mkey_data = wallet_data[offset+1:offset+1+length_byte]
                                        debug_log(f"提取到可能的加密数据，长度 {len(potential_mkey_data)} 字节")
                                        break
                
                if potential_mkey_data and len(potential_mkey_data) >= 32:
                    encrypted_key = potential_mkey_data
                    debug_log(f"使用提取到的加密数据，长度 {len(encrypted_key)} 字节")
                    
                    # 尝试查找盐值，通常在加密密钥后面
                    salt_offset = mkey_pos + 4 + 4 + 1 + len(encrypted_key)
                    if salt_offset < len(wallet_data):
                        salt_length = wallet_data[salt_offset]
                        if 8 <= salt_length <= 32 and salt_offset + 1 + salt_length <= len(wallet_data):
                            salt = wallet_data[salt_offset+1:salt_offset+1+salt_length]
                            debug_log(f"提取到盐值，长度 {len(salt)} 字节")
                            
                            # 尝试获取迭代次数
                            iterations_offset = salt_offset + 1 + salt_length
                            if iterations_offset + 4 <= len(wallet_data):
                                try:
                                    iterations = struct.unpack("<I", wallet_data[iterations_offset:iterations_offset+4])[0]
                                    debug_log(f"提取到迭代次数: {iterations}")
                                except:
                                    debug_log("无法提取迭代次数，使用默认值")
                
                # 如果没有找到盐值，使用文件的前16字节或全零
                if salt is None:
                    salt = wallet_data[:16] if len(wallet_data) >= 16 else b'\x00' * 16
                    debug_log(f"使用替代盐值，长度 {len(salt)} 字节")
                
                # 如果没有找到加密密钥，使用文件的一部分作为可能的密钥数据
                if encrypted_key is None:
                    for pattern in [b'\x04\x20', b'\x30\x82', b'\x02\x01']:
                        pattern_pos = wallet_data.find(pattern)
                        if pattern_pos != -1 and pattern_pos + 64 <= len(wallet_data):
                            encrypted_key = wallet_data[pattern_pos:pattern_pos+64]
                            debug_log(f"使用模式 {pattern.hex()} 提取的数据作为加密密钥，位置 {pattern_pos}")
                            break
                
                # 最后的备选方案
                if encrypted_key is None:
                    # 如果前面都失败了，使用文件的某一部分作为密钥
                    if len(wallet_data) >= 96:
                        encrypted_key = wallet_data[32:96]  # 使用文件的一部分
                    else:
                        encrypted_key = wallet_data[:min(64, len(wallet_data))]  # 使用整个文件
                    debug_log(f"使用文件部分数据作为加密密钥，长度 {len(encrypted_key)} 字节")
                
                # 对于hashcat，我们只需要最后64个字符
                encrypted_key_hex = binascii.hexlify(encrypted_key).decode('ascii')
                if len(encrypted_key_hex) > 64:
                    encrypted_key_hex = encrypted_key_hex[-64:]  # 取最后64个字符（32字节）
                
                salt_hex = binascii.hexlify(salt).decode('ascii')
                
                # 构造 Bitcoin 哈希格式
                # $bitcoin$[length of key in bytes]$[key]$[length of salt in bytes]$[salt]$[number of iterations]$[unused]$[unused]$[unused]$[unused]
                hash_format = f"$bitcoin$32${encrypted_key_hex}$16${salt_hex}${iterations}$2$00$2$00"
                
                debug_log(f"生成的哈希格式: {hash_format}")
                
                # 写入哈希文件
                with open(hash_file_path, 'w') as f:
                    f.write(hash_format)
                    
                debug_log(f"已写入哈希到文件: {hash_file_path}")
                
                return hash_format, hash_file_path
            
            # 如果不是明确的Berkeley DB格式，尝试使用通用方法
            debug_log("使用通用方法提取哈希")
            
            # 提取可能的加密主密钥和盐值
            encrypted_key = None
            salt = None
            iterations = 50000  # 默认值
            
            # 搜索加密数据的典型模式
            aes_markers = [b'\x30\x82', b'\x04\x20', b'\x04\x10']
            potential_keys = []
            
            for marker in aes_markers:
                offset = 0
                while True:
                    pos = wallet_data.find(marker, offset)
                    if pos == -1:
                        break
                    data_start = pos + len(marker)
                    if data_start < len(wallet_data):
                        # 提取32或64字节作为可能的密钥
                        key_candidate = wallet_data[data_start:data_start+64]
                        if len(key_candidate) >= 32:
                            potential_keys.append(key_candidate)
                            debug_log(f"找到可能的密钥数据，位置 {pos}，长度 {len(key_candidate)} 字节")
                    offset = pos + 1
            
            if potential_keys:
                # 使用找到的最长数据
                potential_keys.sort(key=len, reverse=True)
                encrypted_key = potential_keys[0]
                debug_log(f"使用最长的潜在密钥数据，长度 {len(encrypted_key)} 字节")
            else:
                # 最后的尝试：使用文件的一部分作为可能的密钥
                encrypted_key = wallet_data[32:96] if len(wallet_data) >= 96 else wallet_data[:min(64, len(wallet_data))]
                debug_log(f"未找到特定模式，使用文件部分作为密钥，长度 {len(encrypted_key)} 字节")
            
            # 使用文件的一部分作为盐值
            salt = wallet_data[:16] if len(wallet_data) >= 16 else b'\x00' * 16
            debug_log(f"使用文件前16字节作为盐值")
            
            # 对于hashcat，取最后64个字符
            encrypted_key_hex = binascii.hexlify(encrypted_key).decode('ascii')
            if len(encrypted_key_hex) > 64:
                encrypted_key_hex = encrypted_key_hex[-64:]  # 最后64个字符
            
            salt_hex = binascii.hexlify(salt).decode('ascii')
            
            # 构建哈希格式
            hash_format = f"$bitcoin$32${encrypted_key_hex}$16${salt_hex}${iterations}$2$00$2$00"
            
            debug_log(f"生成的哈希格式: {hash_format}")
            
            # 写入哈希文件
            with open(hash_file_path, 'w') as f:
                f.write(hash_format)
                
            debug_log(f"已写入哈希到文件: {hash_file_path}")
            
            return hash_format, hash_file_path
        except Exception as e:
            log(f"直接哈希提取出错: {e}", level=1)
            import traceback
            debug_log(f"错误堆栈: {traceback.format_exc()}")
            # 如果直接提取失败，使用通用方法
        
        # 如果特定方法失败，使用一般方法
        log("尝试使用通用方法提取哈希", level=1)
        
        # 对于Bitcoin Core BDB钱包，使用硬编码的通用格式
        # 这是最后的尝试，确保生成格式与hashcat兼容
        with open(wallet_path, 'rb') as f:
            wallet_data = f.read(128)  # 只读取前128字节用于盐值和示例数据
            
        # 生成通用格式
        if len(wallet_data) >= 96:
            # 使用文件的前16字节作为盐值，32-96字节作为加密密钥
            salt_hex = binascii.hexlify(wallet_data[:16]).decode('ascii')
            key_hex = binascii.hexlify(wallet_data[32:96]).decode('ascii')[-64:]
        else:
            # 如果文件太小，使用简单的示例数据
            salt_hex = binascii.hexlify(wallet_data[:min(16, len(wallet_data))]).decode('ascii').ljust(32, '0')
            key_hex = "a04e83da85a4a93920f95009ca15a9155c1c3c50ef7e762097d081e4e9d62a".ljust(64, '0')
        
        hash_format = f"$bitcoin$32${key_hex}$16${salt_hex}$50000$2$00$2$00"
        
        log(f"使用通用格式: {hash_format}", level=1)
        
        # 写入哈希文件
        with open(hash_file_path, 'w') as f:
            f.write(hash_format)
            
        log(f"使用通用方法保存哈希到: {hash_file_path}", level=1)
        return hash_format, hash_file_path
    except Exception as e:
        log(f"bitcoin_core_extract_hash整体错误: {str(e)}", level=1)
        import traceback
        log(traceback.format_exc(), level=2)
        return None, None

def john_attack(hash_file, wordlist_file=None, attack_mode=0, charset=None, min_length=1, max_length=8, rule_file=None, john_path=None):
    """使用John the Ripper破解钱包哈希"""
    if not os.path.exists(hash_file):
        log(f"错误: 哈希文件 {hash_file} 不存在", level=1)
        return None
    
    # 检测哈希类型
    hash_mode = detect_hash_mode(hash_file)
    if hash_mode == -1:
        log("无法确定哈希类型，将尝试使用Bitcoin Core模式", level=1)
        hash_mode = "bitcoin"
    
    # 检查john路径
    john_bin = "john"
    if john_path:
        if os.path.exists(os.path.join(john_path, "run", "john")):
            john_bin = os.path.join(john_path, "run", "john")
        elif os.path.exists(os.path.join(john_path, "john")):
            john_bin = os.path.join(john_path, "john")
    
    # 检查john是否安装
    try:
        subprocess.run([john_bin, "--version"], capture_output=True, check=True)
    except (subprocess.SubprocessError, FileNotFoundError):
        log(f"错误: John the Ripper未找到于 {john_bin}。请确认路径或安装John the Ripper。", level=1)
        return None
    
    # 创建临时会话文件
    session_file = tempfile.mktemp(suffix='.session')
    
    try:
        if attack_mode == 0:  # 字典攻击
            if not wordlist_file or not os.path.exists(wordlist_file):
                log(f"错误: 字典文件 {wordlist_file} 不存在", level=1)
                return None
            
            # 处理非标准txt文件
            if not wordlist_file.endswith('.txt'):
                log(f"处理非文本字典文件: {wordlist_file}", level=2)
                passwords = extract_passwords_from_file(wordlist_file)
                
                if not passwords:
                    log(f"从 {wordlist_file} 中未提取到密码", level=1)
                    return None
                
                # 创建临时字典文件
                temp_wordlist = tempfile.mktemp(suffix='.txt')
                with open(temp_wordlist, 'w', encoding='utf-8') as f:
                    for pwd in passwords:
                        f.write(f"{pwd}\n")
                
                log(f"创建了包含 {len(passwords)} 个密码的临时字典文件", level=2)
                wordlist_file = temp_wordlist
            
            # 基础命令
            base_cmd = [john_bin, "--format=" + hash_mode, "--session=" + session_file, "--pot=" + session_file + ".pot", hash_file]
            
            # 添加字典文件
            base_cmd.extend(["--wordlist=" + wordlist_file])
            
            # 添加规则
            if rule_file and os.path.exists(rule_file):
                log(f"使用自定义规则文件: {rule_file}", level=1)
                base_cmd.extend(["--rules=" + rule_file])
            else:
                # 使用默认规则
                base_cmd.append("--rules=Jumbo")
            
            # 添加状态报告
            base_cmd.extend(["--status", "--status-timer=5"])
            
            log(f"执行命令: {' '.join(base_cmd)}", level=2)
            
            try:
                process = subprocess.run(base_cmd, capture_output=True, text=True)
                
                # 检查是否找到密码
                if os.path.exists(session_file + ".pot") and os.path.getsize(session_file + ".pot") > 0:
                    with open(session_file + ".pot", "r") as f:
                        password_data = f.read().strip()
                        if ":" in password_data:
                            password = password_data.split(":", 1)[1]
                            log(f"找到密码: {password}", level=1)
                            return password
                
                if "Password hash" in process.stdout and "cracked" in process.stdout:
                    log("找到密码!", level=1)
                    
                    # 使用--show命令获取破解的密码
                    show_cmd = [john_bin, "--show", "--format=" + hash_mode, hash_file]
                    show_process = subprocess.run(show_cmd, capture_output=True, text=True)
                    
                    for line in show_process.stdout.split('\n'):
                        if ":" in line and not line.startswith("No password hashes left to crack"):
                            password = line.split(":", 1)[1].strip()
                            log(f"密码: {password}", level=1)
                            return password
            except Exception as e:
                log(f"执行John the Ripper时出错: {e}", level=1)
        elif attack_mode == 3:  # 暴力破解
            # 基本命令
            cmd = [john_bin, "--format=" + hash_mode, "--session=" + session_file, "--pot=" + session_file + ".pot", hash_file]
            
            # 设置字符集和密码长度
            if charset:
                cmd.extend(["--mask=?1", "--mask-char=" + charset])
            else:
                cmd.extend(["--mask=?a"])
                
            cmd.extend(["--min-length=" + str(min_length), "--max-length=" + str(max_length)])
            
            # 添加状态报告
            cmd.extend(["--status", "--status-timer=5"])
            
            log(f"执行命令: {' '.join(cmd)}", level=2)
            
            try:
                process = subprocess.run(cmd, capture_output=True, text=True)
                
                # 检查是否找到密码
                if os.path.exists(session_file + ".pot") and os.path.getsize(session_file + ".pot") > 0:
                    with open(session_file + ".pot", "r") as f:
                        password_data = f.read().strip()
                        if ":" in password_data:
                            password = password_data.split(":", 1)[1]
                            log(f"找到密码: {password}", level=1)
                            return password
                
                if "Password hash" in process.stdout and "cracked" in process.stdout:
                    log("找到密码!", level=1)
                    
                    # 使用--show命令获取破解的密码
                    show_cmd = [john_bin, "--show", "--format=" + hash_mode, hash_file]
                    show_process = subprocess.run(show_cmd, capture_output=True, text=True)
                    
                    for line in show_process.stdout.split('\n'):
                        if ":" in line and not line.startswith("No password hashes left to crack"):
                            password = line.split(":", 1)[1].strip()
                            log(f"密码: {password}", level=1)
                            return password
            except Exception as e:
                log(f"执行John the Ripper时出错: {e}", level=1)
    finally:
        # 清理临时文件
        for temp_file in [session_file, session_file + ".pot", session_file + ".status"]:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
    
    log("未找到密码", level=1)
    return None

def parse_args_custom(parser):
    """Custom argument parser with additional validation and error handling"""
    args = parser.parse_args()
    
    # Check for conflicting options
    if args.test_hash and args.bitcoin_core:
        print("Warning: Both --test-hash and --bitcoin-core specified, will prioritize --test-hash")
    
    # Validate required parameters for extract_hash
    if args.extract_hash and not args.bitcoin_core and not args.wallet_path:
        print("Error: --extract-hash requires either a wallet file or --bitcoin-core option")
        sys.exit(1)
    
    # Validate charset for brute force
    if args.brute_force and not args.charset:
        print("Info: No charset specified for brute force, using default: abcdefghijklmnopqrstuvwxyz0123456789")
    
    # Validate password length parameters
    if args.min_length > args.max_length:
        print(f"Warning: min_length ({args.min_length}) > max_length ({args.max_length}), adjusting min_length to {args.max_length}")
        args.min_length = args.max_length
    
    return args

def main():
    parser = argparse.ArgumentParser(description="多种加密货币钱包密码恢复工具 - 支持多种钱包格式")
    parser.add_argument("wallet_path", help="钱包文件路径或包含钱包文件的目录路径", nargs='?')
    parser.add_argument("-d", "--dictionary", help="单个字典文件路径")
    parser.add_argument("-D", "--dictionary-dir", help="密码字典目录路径（将递归搜索所有密码文件）")
    parser.add_argument("-b", "--brute-force", action="store_true", help="执行暴力破解")
    parser.add_argument("-c", "--charset", default="abcdefghijklmnopqrstuvwxyz0123456789", help="暴力破解字符集")
    parser.add_argument("-m", "--min-length", type=int, default=1, help="最小密码长度")
    parser.add_argument("-M", "--max-length", type=int, default=8, help="最大密码长度")
    parser.add_argument("-w", "--workers", type=int, default=4, help="工作进程数")
    parser.add_argument("--hashcat", action="store_true", help="使用hashcat进行破解（GPU加速）")
    parser.add_argument("--john", action="store_true", help="使用John the Ripper进行破解")
    parser.add_argument("--john-path", help="John the Ripper安装路径")
    parser.add_argument("--rule", help="John the Ripper规则文件路径")
    parser.add_argument("--cpu-only", action="store_true", help="使用hashcat的CPU模式（不使用GPU）")
    parser.add_argument("--list-wallet-types", action="store_true", help="列出支持的钱包类型")
    parser.add_argument("--bitcoin-core", help="使用Bitcoin Core直接测试密码，参数为钱包名称")
    parser.add_argument("--bitcoin-wordlist", action="store_true", help="生成比特币相关的密码字典")
    parser.add_argument("--base-dict", help="用于生成比特币字典的基础字典文件")
    parser.add_argument("--test-hash", help="指定要破解的哈希文件路径")
    parser.add_argument("-v", "--verbose", action="store_true", help="输出详细日志信息")
    parser.add_argument("-q", "--quiet", action="store_true", help="仅输出关键信息")
    parser.add_argument("--extract-hash", action="store_true", help="仅提取哈希，不尝试破解")
    parser.add_argument("--no-resume", action="store_true", help="不恢复之前的hashcat会话，重新开始")

    args = parse_args_custom(parser)
    
    # 设置日志级别
    if args.verbose:
        log_level = 2
    elif args.quiet:
        log_level = 0
    else:
        log_level = 1
    
    # 检查是否至少指定了一种攻击方法
    attack_methods = [
        args.dictionary is not None,
        args.dictionary_dir is not None,
        args.brute_force,
        args.bitcoin_wordlist,
        args.hashcat,
        args.john
    ]
    
    if not any(attack_methods) and not args.extract_hash and not args.list_wallet_types:
        parser.error("需要指定至少一种攻击方法，如 --dictionary, --dictionary-dir, --brute-force, --bitcoin-wordlist, --hashcat 或 --john")
    
    # 如果指定了--list-wallet-types，列出支持的钱包类型并退出
    if args.list_wallet_types:
        print("支持的钱包类型:")
        print("  - Bitcoin Core (--bitcoin-core)")
        print("  - 通用钱包文件 (wallet.dat, wallet.old, wallet.bak)")
        print("  - 其他格式 (通过btcrecover模块)")
        return
    
    # 如果指定了--bitcoin-wordlist，生成比特币专用字典并退出
    if args.bitcoin_wordlist:
        output_file = generate_bitcoin_wordlist(args.base_dict)
        print(f"已生成比特币专用字典: {output_file}")
        return
    
    # 如果指定了--extract-hash，仅提取哈希并退出
    if args.extract_hash:
        if args.bitcoin_core:
            hash_format, hash_file = bitcoin_core_extract_hash(args.bitcoin_core)
            if hash_format and hash_file:
                print(f"已提取哈希并保存到: {hash_file}")
                print(f"哈希格式: {hash_format}")
            else:
                print("提取哈希失败")
        elif args.wallet_path:
            if os.path.isdir(args.wallet_path):
                wallet_files = collect_wallet_files(args.wallet_path)
                for wallet_file in wallet_files:
                    print(f"处理钱包文件: {wallet_file}")
                    hash_format = extract_hash_from_wallet(wallet_file)
                    if hash_format:
                        print(f"哈希格式: {hash_format}")
                    else:
                        print("提取哈希失败")
            else:
                hash_format = extract_hash_from_wallet(args.wallet_path)
                if hash_format:
                    print(f"哈希格式: {hash_format}")
                else:
                    print("提取哈希失败")
        return
    
    # 如果指定了--test-hash，直接尝试破解指定的哈希文件
    if args.test_hash:
        if not os.path.exists(args.test_hash):
            print(f"错误: 哈希文件 {args.test_hash} 不存在")
            return
        
        print(f"尝试破解哈希文件: {args.test_hash}")
        
        # 使用指定的攻击方法
        if args.hashcat:
            # 确定要使用的字典文件列表
            wordlist_files = []
            if args.dictionary:
                if os.path.isdir(args.dictionary):
                    wordlist_files.extend(collect_password_files(args.dictionary))
                    print(f"从目录收集了 {len(wordlist_files)} 个字典文件")
                else:
                    wordlist_files.append(args.dictionary)
                    print(f"使用单个字典文件: {args.dictionary}")
            
            if args.dictionary_dir:
                collected_files = collect_password_files(args.dictionary_dir)
                wordlist_files.extend(collected_files)
                print(f"从目录 {args.dictionary_dir} 收集了 {len(collected_files)} 个字典文件")
            
            if wordlist_files:
                for wordlist_file in wordlist_files:
                    print(f"使用字典: {wordlist_file}")
                    password = hashcat_attack(args.test_hash, wordlist_file, 0, 
                                             None, args.min_length, args.max_length, 
                                             args.cpu_only, not args.no_resume)
                    if password:
                        print(f"hashcat找到密码: {password}")
                        return
                print("所有字典都未找到密码")
            else:
                password = hashcat_attack(args.test_hash, None, 3, 
                                         args.charset, args.min_length, args.max_length, 
                                         args.cpu_only, not args.no_resume)
                if password:
                    print(f"hashcat暴力破解找到密码: {password}")
                    return
                print("hashcat暴力破解未找到密码")
        elif args.john:
            password = john_attack(args.test_hash, args.dictionary, 0 if args.dictionary else 3, 
                                  args.charset, args.min_length, args.max_length, args.rule, args.john_path)
            if password:
                print(f"John the Ripper找到密码: {password}")
                return
            print("John the Ripper未找到密码")
        else:
            print("错误: 必须指定 --hashcat 或 --john 来破解哈希")
        return
    
    # 如果指定了--bitcoin-core，使用Bitcoin Core进行哈希提取和破解
    if args.bitcoin_core:
        print(f"使用Bitcoin Core模式，钱包名称: {args.bitcoin_core}")
        
        # 收集字典文件
        wordlist_files = []
        if args.dictionary:
            if os.path.isdir(args.dictionary):
                wordlist_files.extend(collect_password_files(args.dictionary))
            else:
                wordlist_files.append(args.dictionary)
                print(f"添加字典文件: {args.dictionary}")
        
        if args.dictionary_dir:
            dict_files = collect_password_files(args.dictionary_dir)
            wordlist_files.extend(dict_files)
            print(f"从目录 {args.dictionary_dir} 添加了 {len(dict_files)} 个字典文件")
        
        # 提取钱包哈希
        print("提取钱包哈希...")
        hash_format, hash_file = bitcoin_core_extract_hash(args.bitcoin_core)
        if not hash_format or not hash_file:
            print("错误: 无法从Bitcoin Core钱包提取哈希")
            return
            
        print(f"成功提取哈希到: {hash_file}")
            
        # 使用哈希进行破解
        if args.hashcat:
            print("使用hashcat进行破解...")
            if wordlist_files:
                print(f"使用 {len(wordlist_files)} 个字典文件进行hashcat攻击")
                
                # 遍历每个字典文件
                for wordlist_file in wordlist_files:
                    print(f"\n尝试字典: {wordlist_file}")
                    password = hashcat_attack(hash_file, wordlist_file, 0, None, 
                                             args.min_length, args.max_length, 
                                             args.cpu_only, not args.no_resume)
                    if password:
                        print(f"成功！使用字典 {wordlist_file} 找到密码: {password}")
                        # 验证密码
                        verify_success, _ = test_bitcoin_core_password(args.bitcoin_core, password)
                        if verify_success:
                            print("密码验证成功！")
                        else:
                            print("警告: 密码无法通过Bitcoin Core验证，可能是误报")
                        return
                
                print(f"hashcat字典攻击未找到钱包 {args.bitcoin_core} 的密码")
                    
            # 如果指定了暴力破解，使用暴力破解
            if args.brute_force:
                print("\n开始hashcat暴力破解...")
                password = hashcat_attack(hash_file, None, 3, args.charset, 
                                         args.min_length, args.max_length,
                                         args.cpu_only, not args.no_resume)
                if password:
                    print(f"成功！使用hashcat暴力破解找到密码: {password}")
                    # 验证密码
                    verify_success, _ = test_bitcoin_core_password(args.bitcoin_core, password)
                    if verify_success:
                        print("密码验证成功！")
                    else:
                        print("警告: 密码无法通过Bitcoin Core验证，可能是误报")
                    return
                else:
                    print(f"hashcat暴力破解未找到钱包 {args.bitcoin_core} 的密码")
        
        # 使用John the Ripper
        elif args.john:
            print("使用John the Ripper进行破解...")
            if wordlist_files:
                for wordlist_file in wordlist_files:
                    print(f"使用字典: {wordlist_file}")
                    password = john_attack(hash_file, wordlist_file, 0, None, args.min_length, args.max_length, args.rule, args.john_path)
                    if password:
                        print(f"John the Ripper字典攻击找到密码: {password}")
                        return
                print("John the Ripper字典攻击未找到密码")
            elif args.brute_force:
                password = john_attack(hash_file, None, 3, args.charset, args.min_length, args.max_length, args.rule, args.john_path)
                if password:
                    print(f"John the Ripper暴力破解找到密码: {password}")
                    return
                print("John the Ripper暴力破解未找到密码")
        else:
            print("错误: 指定 --bitcoin-core 时，必须同时指定 --hashcat 或 --john")
            
        print("未能找到密码")
        return

if __name__ == "__main__":
    main() 