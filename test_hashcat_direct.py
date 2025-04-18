#!/usr/bin/env python3
"""
直接使用 hashcat 测试 Bitcoin 钱包哈希
用法: python test_hashcat_direct.py <钱包名称>
"""

import os
import sys
import subprocess
import tempfile
import time
from btcracker.core.processor import bitcoin_core_extract_hash_with_bitcoin2john
from btcracker.attacks.dictionary import test_bitcoin_core_password

def main():
    # 允许从命令行参数传入钱包名称
    wallet_name = sys.argv[1] if len(sys.argv) > 1 else "test_wallet"
    
    print(f"===== 测试钱包: {wallet_name} =====")
    
    # 提取哈希
    hash_format, hash_file = bitcoin_core_extract_hash_with_bitcoin2john(wallet_name)
    
    if not hash_format:
        print(f"错误: 无法从 {wallet_name} 提取哈希")
        return
    
    print(f"成功提取哈希: {hash_format}")
    print(f"哈希文件: {hash_file}")
    
    # 保存哈希文件内容供检查
    if hash_file and os.path.exists(hash_file):
        with open(hash_file, 'r') as f:
            hash_content = f.read().strip()
            print(f"\n哈希文件内容: {hash_content}")
    
    # 创建密码文件
    pwd_file = tempfile.mktemp(suffix='.txt')
    with open(pwd_file, 'w') as f:
        f.write("test123\n")
        f.write("password123\n")
        f.write("bitcoin\n")
    
    print(f"密码文件: {pwd_file}")
    
    # 创建输出文件和potfile
    output_file = "found_password.txt"
    potfile = "test_hashcat.potfile"
    
    # 构建直接的 hashcat 命令 - 最简化版本
    cmd = [
        "hashcat",
        "-m", "11300",  # Bitcoin/Litecoin wallet.dat
        hash_file,
        pwd_file,
        "--force",       # 必须的，跳过所有警告
        "--status",
        "--potfile-path", potfile,
        "-o", output_file
    ]
    
    print(f"执行 hashcat 命令: {' '.join(cmd)}")
    
    # 直接执行 hashcat 命令，显示全部输出
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                  text=True, bufsize=1, universal_newlines=True)
        
        found_password = None
        start_time = time.time()
        max_time = 60  # 最多等待60秒
        
        # 实时输出标准输出
        print("=== STDOUT 输出 ===")
        while process.poll() is None and (time.time() - start_time) < max_time:
            output = process.stdout.readline()
            if not output:
                time.sleep(0.1)
                continue
                
            print(output.strip())
            
            # 检查是否找到密码
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                with open(output_file, "r") as f:
                    output_content = f.read().strip()
                    if ":" in output_content:
                        found_password = output_content.split(":", 1)[1]
                        print(f"\n成功! 找到密码: {found_password}")
                        break
            
            # 检查potfile是否有内容
            if os.path.exists(potfile) and os.path.getsize(potfile) > 0:
                with open(potfile, "r") as f:
                    potfile_content = f.read().strip()
                    if ":" in potfile_content:
                        found_password = potfile_content.split(":", 1)[1]
                        print(f"\n成功! 在potfile中找到密码: {found_password}")
                        break
        
        # 终止进程
        if process.poll() is None:
            print("终止hashcat进程...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        
        # 获取并输出错误信息
        stderr_output = process.stderr.read()
        if stderr_output:
            print("\n=== STDERR 输出 ===")
            print(stderr_output)
        
        # 获取返回码
        return_code = process.poll()
        print(f"\nhashcat 返回码: {return_code}")
        
        # 如果提示发现所有哈希，则运行 --show 命令
        if return_code == 0 or found_password:
            print("\n尝试使用 --show 命令查看是否有匹配：")
            show_cmd = ["hashcat", "-m", "11300", hash_file, "--show", "--force"]
            show_process = subprocess.run(show_cmd, capture_output=True, text=True)
            print(show_process.stdout.strip())
            
            if show_process.stdout.strip():
                if ":" in show_process.stdout.strip():
                    found_password = show_process.stdout.strip().split(":", 1)[1]
                    print(f"--show 找到密码: {found_password}")
            else:
                print("--show 未返回匹配结果")
        
        # 检查是否找到密码
        if not found_password:
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                with open(output_file, "r") as f:
                    password_data = f.read().strip()
                    if ":" in password_data:
                        found_password = password_data.split(":", 1)[1]
                        print(f"从输出文件找到密码: {found_password}")
            
            if not found_password and os.path.exists(potfile) and os.path.getsize(potfile) > 0:
                with open(potfile, "r") as f:
                    potfile_content = f.read().strip()
                    if ":" in potfile_content:
                        found_password = potfile_content.split(":", 1)[1]
                        print(f"从potfile找到密码: {found_password}")
        
        if not found_password:
            print("未找到密码")
            return
            
        # ========================
        # Bitcoin Core验证步骤
        # ========================
        print("\n===== Bitcoin Core验证步骤 =====")
        print(f"使用密码 '{found_password}' 尝试验证Bitcoin Core钱包 '{wallet_name}'")
        
        success, message = test_bitcoin_core_password(wallet_name, found_password)
        
        if success:
            print(f"✅ 验证成功! 密码 '{found_password}' 成功解锁钱包!")
        else:
            print(f"❌ 验证失败! 密码 '{found_password}' 无法解锁钱包!")
            print(f"失败信息: {message}")
            
        # ========================
        # 调试信息 
        # ========================
        print("\n===== 调试信息 =====")
        
        # 检查RPC连接
        print("检查Bitcoin Core RPC连接:")
        check_cmd = ["bitcoin-cli", "getnetworkinfo"]
        try:
            check_process = subprocess.run(check_cmd, capture_output=True, text=True)
            if check_process.returncode == 0:
                print("Bitcoin Core RPC连接正常")
            else:
                print(f"Bitcoin Core RPC连接失败: {check_process.stderr}")
        except Exception as e:
            print(f"执行RPC检查时出错: {e}")
            
        # 检查钱包列表
        print("\n检查钱包列表:")
        list_cmd = ["bitcoin-cli", "listwallets"]
        try:
            list_process = subprocess.run(list_cmd, capture_output=True, text=True)
            print(list_process.stdout.strip())
            
            if wallet_name not in list_process.stdout:
                print(f"警告: '{wallet_name}' 不在已加载钱包列表中!")
        except Exception as e:
            print(f"获取钱包列表时出错: {e}")
            
        # 尝试加载钱包
        print(f"\n尝试加载钱包 '{wallet_name}':")
        load_cmd = ["bitcoin-cli", "loadwallet", wallet_name]
        try:
            load_process = subprocess.run(load_cmd, capture_output=True, text=True)
            print(load_process.stdout.strip() or load_process.stderr.strip())
        except Exception as e:
            print(f"加载钱包时出错: {e}")
            
        # 检查钱包信息
        print(f"\n检查钱包 '{wallet_name}' 信息:")
        info_cmd = ["bitcoin-cli", "-rpcwallet=" + wallet_name, "getwalletinfo"]
        try:
            info_process = subprocess.run(info_cmd, capture_output=True, text=True)
            print(info_process.stdout.strip() or info_process.stderr.strip())
        except Exception as e:
            print(f"获取钱包信息时出错: {e}") 
            
    except Exception as e:
        print(f"执行 hashcat 命令时出错: {e}")
    finally:
        # 清理临时文件
        try:
            if os.path.exists(pwd_file):
                os.unlink(pwd_file)
            if os.path.exists(output_file):
                os.unlink(output_file)
            if os.path.exists(potfile):
                os.unlink(potfile)
        except Exception as e:
            print(f"清理临时文件时出错: {e}")

if __name__ == "__main__":
    main() 