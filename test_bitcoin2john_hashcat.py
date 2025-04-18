#!/usr/bin/env python3
# 测试直接使用bitcoin2john导出哈希并用hashcat破解

import os
import sys
import tempfile
import subprocess
import importlib.util
import binascii
import time

# 设置变量
WALLET_NAME = "bdb_wallet"
WALLET_PATH = os.path.expanduser(f"~/Library/Application Support/Bitcoin/wallets/{WALLET_NAME}/wallet.dat")
PASSWORD_FILE = "test_passwords.txt"

def debug_log(msg):
    """打印调试信息"""
    print(f"DEBUG: {msg}")

def extract_hash_with_bitcoin2john():
    """使用bitcoin2john提取哈希"""
    debug_log(f"使用bitcoin2john处理钱包: {WALLET_PATH}")
    
    # 检查钱包文件是否存在
    if not os.path.exists(WALLET_PATH):
        debug_log(f"错误: 找不到钱包文件 {WALLET_PATH}")
        return None, None
    
    # 检查bitcoin2john.py是否存在
    module_path = os.path.join(os.getcwd(), "btcracker", "core", "bitcoin2john.py")
    debug_log(f"查找bitcoin2john模块: {module_path}")
    
    if not os.path.exists(module_path):
        debug_log(f"错误: 找不到bitcoin2john.py文件")
        return None, None
    
    try:
        # 创建临时文件保存哈希
        fd, hash_file = tempfile.mkstemp(suffix='.hash')
        os.close(fd)
        debug_log(f"创建哈希输出文件: {hash_file}")
        
        # 导入bitcoin2john模块
        spec = importlib.util.spec_from_file_location("bitcoin2john", module_path)
        bitcoin2john = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bitcoin2john)
        
        # 运行bitcoin2john读取钱包
        json_db = {}
        debug_log(f"开始读取钱包文件...")
        result = bitcoin2john.read_wallet(json_db, WALLET_PATH)
        
        if result == -1:
            debug_log(f"错误: bitcoin2john无法读取钱包")
            os.remove(hash_file)
            return None, None
        
        debug_log(f"成功读取钱包, json_db内容: {json_db}")
        
        # 提取密钥和盐值
        cry_master = binascii.unhexlify(json_db['mkey']['encrypted_key'])
        cry_salt = binascii.unhexlify(json_db['mkey']['salt'])
        cry_rounds = json_db['mkey']['nDerivationIterations']
        
        debug_log(f"提取的加密密钥: {json_db['mkey']['encrypted_key']}")
        debug_log(f"提取的盐值: {json_db['mkey']['salt']}")
        debug_log(f"迭代次数: {cry_rounds}")
        
        # 只使用最后两个AES块
        if len(cry_master) >= 64:
            cry_master = cry_master[-64:]
            debug_log(f"截取最后64字节的密钥")
        
        # 创建hashcat格式哈希
        hash_format = (
            f"$bitcoin${len(cry_master)}${binascii.hexlify(cry_master).decode()}"
            f"${len(cry_salt)}${binascii.hexlify(cry_salt).decode()}"
            f"${cry_rounds}$2$00$2$00"
        )
        
        debug_log(f"生成的哈希格式: {hash_format}")
        
        # 写入哈希文件
        with open(hash_file, 'w') as f:
            f.write(hash_format)
        
        debug_log(f"哈希已写入文件")
        return hash_format, hash_file
        
    except Exception as e:
        debug_log(f"提取哈希出错: {str(e)}")
        import traceback
        traceback.print_exc()
        
        if 'hash_file' in locals() and os.path.exists(hash_file):
            os.remove(hash_file)
            
        return None, None

def run_hashcat(hash_file, wordlist_file):
    """运行hashcat测试破解密码"""
    debug_log(f"开始使用hashcat测试哈希文件: {hash_file}")
    debug_log(f"使用密码字典: {wordlist_file}")
    
    # 检查文件是否存在
    if not os.path.exists(hash_file):
        debug_log(f"错误: 哈希文件不存在")
        return None
    
    if not os.path.exists(wordlist_file):
        debug_log(f"错误: 密码字典不存在")
        return None
    
    # 确保输出目录存在
    os.makedirs("hashcat_sessions", exist_ok=True)
    
    # 生成potfile路径
    potfile = os.path.join(os.getcwd(), "hashcat_sessions", "test.potfile")
    if os.path.exists(potfile):
        os.remove(potfile)
    
    # 生成输出文件路径
    output_file = os.path.join(os.getcwd(), "found_password.txt")
    if os.path.exists(output_file):
        os.remove(output_file)
    
    # 构建hashcat命令
    cmd = [
        "hashcat",
        "-m", "11300",  # Bitcoin Core钱包模式
        hash_file,
        "--status",
        "--status-timer", "5",
        "--potfile-path", potfile,
        "-o", output_file,
        "--force",
        "-D", "1",  # CPU模式
        "--backend-devices", "1",
        "--self-test-disable",
        wordlist_file
    ]
    
    debug_log(f"执行命令: {' '.join(cmd)}")
    
    try:
        # 执行hashcat命令
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        
        # 监控进程输出
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip())
        
        # 等待hashcat完成
        process.wait()
        debug_log(f"Hashcat 执行完成，返回码: {process.returncode}")
        
        # 检查potfile
        if os.path.exists(potfile) and os.path.getsize(potfile) > 0:
            with open(potfile, "r") as f:
                potfile_content = f.read().strip()
                if ":" in potfile_content:
                    password = potfile_content.split(":", 1)[1]
                    debug_log(f"在potfile中找到密码: {password}")
                    return password
        
        # 检查输出文件
        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            with open(output_file, "r") as f:
                content = f.read().strip()
                if ":" in content:
                    password = content.split(":", 1)[1]
                    debug_log(f"在输出文件中找到密码: {password}")
                    return password
        
        debug_log("未找到密码")
        return None
        
    except Exception as e:
        debug_log(f"执行hashcat时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def test_password_directly():
    """直接测试已知密码"""
    known_password = "bitcoin1234"
    debug_log(f"直接测试已知密码: {known_password}")
    
    cmd = [
        "bitcoin-cli",
        "-rpcwallet=" + WALLET_NAME,
        "walletpassphrase",
        known_password,
        "1"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            debug_log(f"密码 {known_password} 验证成功!")
            return True
        else:
            debug_log(f"密码验证失败: {result.stderr}")
            return False
    except Exception as e:
        debug_log(f"验证密码时出错: {str(e)}")
        return False

def main():
    print("=== 测试直接使用bitcoin2john和hashcat ===")
    
    # 1. 直接验证已知密码
    if test_password_directly():
        print("已知密码验证成功")
    else:
        print("已知密码验证失败")
    
    # 2. 提取哈希
    hash_format, hash_file = extract_hash_with_bitcoin2john()
    if not hash_format or not hash_file:
        print("提取哈希失败，无法继续")
        return
    
    print(f"成功提取哈希: {hash_format[:30]}...")
    
    # 3. 使用hashcat测试
    password = run_hashcat(hash_file, PASSWORD_FILE)
    
    if password:
        print(f"Hashcat成功找到密码: {password}")
    else:
        print("Hashcat未找到密码，尝试修改哈希格式...")
        
        # 尝试修改哈希格式
        with open(hash_file, 'r') as f:
            original_hash = f.read().strip()
        
        # 修改后的哈希格式 (去掉最后一个2$00，这是可选的)
        modified_hash = original_hash.rsplit('$2$00', 1)[0]
        
        # 写入修改后的哈希
        modified_hash_file = hash_file + '.mod'
        with open(modified_hash_file, 'w') as f:
            f.write(modified_hash)
        
        print(f"使用修改后的哈希格式: {modified_hash[:30]}...")
        
        # 再次尝试hashcat
        password = run_hashcat(modified_hash_file, PASSWORD_FILE)
        
        if password:
            print(f"使用修改后格式，Hashcat成功找到密码: {password}")
        else:
            print("Hashcat仍未找到密码")

if __name__ == "__main__":
    main() 