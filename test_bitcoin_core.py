#!/usr/bin/env python3
# 直接测试 Bitcoin Core 钱包密码

import os
import subprocess
import time
from tqdm import tqdm

# 钱包名称
WALLET_NAME = "bdb_wallet"

def test_password(wallet_name, password):
    """直接测试 Bitcoin Core 钱包密码"""
    # 构建调用 Bitcoin-CLI 的命令
    cmd = [
        "bitcoin-cli",
        "-rpcwallet=" + wallet_name,
        "walletpassphrase",
        password,
        "1"  # 解锁1秒钟
    ]
    
    try:
        # 执行命令
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # 检查是否成功
        if result.returncode == 0:
            # 命令成功执行，没有错误输出
            return True, "成功"
        else:
            # 检查错误消息
            if "incorrect passphrase" in result.stderr.lower():
                return False, "密码错误"
            else:
                return False, result.stderr.strip()
    except Exception as e:
        return False, f"执行错误: {str(e)}"

def load_passwords(password_file):
    """从密码文件加载密码列表"""
    passwords = []
    try:
        with open(password_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                password = line.strip()
                if password:
                    passwords.append(password)
        return passwords
    except Exception as e:
        print(f"读取密码文件错误: {str(e)}")
        return []

def main():
    # 加载测试密码
    password_file = "test_passwords.txt"
    if not os.path.exists(password_file):
        print(f"错误: 密码文件 {password_file} 不存在")
        return
        
    passwords = load_passwords(password_file)
    if not passwords:
        print("错误: 未从密码文件加载到任何密码")
        return
        
    print(f"从 {password_file} 中提取到 {len(passwords)} 个密码")
    
    # 测试每个密码
    success = False
    start_time = time.time()
    tested_count = 0
    
    with tqdm(total=len(passwords), desc="测试密码") as pbar:
        for password in passwords:
            success, message = test_password(WALLET_NAME, password)
            tested_count += 1
            pbar.update(1)
            
            if success:
                elapsed = time.time() - start_time
                speed = tested_count / elapsed if elapsed > 0 else 0
                print(f"找到密码: {password} (测试了 {tested_count} 个密码，速度 {speed:.2f} p/s)")
                break
                
            # 每5个密码暂停一下，避免请求过快
            if tested_count % 5 == 0:
                time.sleep(0.5)
    
    if not success:
        print(f"未找到匹配的密码，测试了 {tested_count} 个密码")
            
if __name__ == "__main__":
    main() 