#!/usr/bin/env python3
"""
直接使用 hashcat 测试 Bitcoin 钱包哈希
用法: python test_hashcat_direct.py
"""

import os
import sys
import subprocess
import tempfile
from btcracker.core.processor import bitcoin_core_extract_hash_with_bitcoin2john

def main():
    wallet_name = "test_wallet"  # 钱包名称
    hash_format, hash_file = bitcoin_core_extract_hash_with_bitcoin2john(wallet_name)
    
    if not hash_format:
        print(f"错误: 无法从 {wallet_name} 提取哈希")
        return
    
    print(f"成功提取哈希: {hash_format}")
    print(f"哈希文件: {hash_file}")
    
    # 创建密码文件
    pwd_file = tempfile.mktemp(suffix='.txt')
    with open(pwd_file, 'w') as f:
        f.write("test123\n")
        f.write("password123\n")
        f.write("bitcoin\n")
    
    print(f"密码文件: {pwd_file}")
    
    # 构建直接的 hashcat 命令 - 最简化版本
    cmd = [
        "hashcat",
        "-m", "11300",  # Bitcoin/Litecoin wallet.dat
        hash_file,
        pwd_file,
        "--force",       # 必须的，跳过所有警告
        "--status",
        "-o", "found_password.txt"
    ]
    
    print(f"执行 hashcat 命令: {' '.join(cmd)}")
    
    # 直接执行 hashcat 命令，显示全部输出
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                  text=True, bufsize=1, universal_newlines=True)
        
        # 实时输出标准输出
        print("=== STDOUT 输出 ===")
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip())
        
        # 获取并输出错误信息
        stderr_output = process.stderr.read()
        if stderr_output:
            print("\n=== STDERR 输出 ===")
            print(stderr_output)
        
        # 获取返回码
        return_code = process.poll()
        print(f"\nhashcat 返回码: {return_code}")
        
        # 如果提示发现所有哈希，则运行 --show 命令
        if return_code == 0:
            print("\n尝试使用 --show 命令查看是否有匹配：")
            show_cmd = ["hashcat", "-m", "11300", hash_file, "--show", "--force"]
            show_process = subprocess.run(show_cmd, capture_output=True, text=True)
            print(show_process.stdout.strip())
            
            if show_process.stdout.strip():
                print(f"找到密码匹配！")
            else:
                print("--show 未返回匹配结果")
        
        # 检查是否找到密码
        if os.path.exists("found_password.txt") and os.path.getsize("found_password.txt") > 0:
            with open("found_password.txt", "r") as f:
                password_data = f.read().strip()
                print(f"找到密码: {password_data}")
        else:
            print("未找到密码")
            
        # 保存哈希文件内容供检查
        if hash_file and os.path.exists(hash_file):
            with open(hash_file, 'r') as f:
                hash_content = f.read().strip()
                print(f"\n哈希文件内容: {hash_content}")
            
    except Exception as e:
        print(f"执行 hashcat 命令时出错: {e}")
    finally:
        # 清理临时文件
        if os.path.exists(pwd_file):
            os.unlink(pwd_file)

if __name__ == "__main__":
    main() 