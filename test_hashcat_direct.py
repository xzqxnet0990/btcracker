#!/usr/bin/env python3
"""
直接使用 hashcat 测试 Bitcoin 钱包哈希
用法: python test_hashcat_direct.py [钱包名称或路径]
"""

import os
import sys
import subprocess
import tempfile
import time
import json
from btcracker.core.processor import bitcoin_core_extract_hash_with_bitcoin2john
from btcracker.attacks.dictionary import test_bitcoin_core_password

def main():
    # 允许从命令行参数传入钱包名称或路径
    wallet_arg = sys.argv[1] if len(sys.argv) > 1 else "bdb_wallet"
    
    # 判断是钱包名称还是完整路径
    if os.path.exists(wallet_arg) and os.path.isfile(wallet_arg):
        wallet_path = wallet_arg
        wallet_name = os.path.basename(os.path.dirname(wallet_path))
        print(f"===== 测试钱包路径: {wallet_path} =====")
        print(f"推测钱包名称: {wallet_name}")
        
        # 直接使用路径从wallet.dat提取哈希
        hash_format, hash_file = bitcoin_core_extract_hash_with_bitcoin2john(wallet_path)
    else:
        # 使用钱包名称
        wallet_name = wallet_arg
        print(f"===== 测试钱包名称: {wallet_name} =====")
        hash_format, hash_file = bitcoin_core_extract_hash_with_bitcoin2john(wallet_name)
    
    if not hash_format:
        print(f"错误: 无法从 {wallet_arg} 提取哈希")
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
        # Bitcoin Core RPC状态检查
        # ========================
        print("\n===== Bitcoin Core RPC状态预检 =====")
        
        # 检查RPC连接
        print("检查Bitcoin Core RPC连接:")
        check_cmd = ["bitcoin-cli", "getnetworkinfo"]
        try:
            check_process = subprocess.run(check_cmd, capture_output=True, text=True)
            if check_process.returncode == 0:
                print("✅ Bitcoin Core RPC连接正常")
                try:
                    network_info = json.loads(check_process.stdout)
                    print(f"版本信息: {network_info.get('version', '未知')}")
                    print(f"协议版本: {network_info.get('protocolversion', '未知')}")
                except:
                    print("无法解析网络信息JSON")
            else:
                print(f"❌ Bitcoin Core RPC连接失败: {check_process.stderr}")
                # 这里是关键点，我们尝试手动启动比特币核心RPC
                print("尝试检查Bitcoin Core是否在运行...")
                ps_cmd = ["ps", "aux"]
                ps_process = subprocess.run(ps_cmd, capture_output=True, text=True)
                if "bitcoind" in ps_process.stdout:
                    print("✅ bitcoind进程正在运行")
                else:
                    print("❌ 未检测到bitcoind进程")
        except Exception as e:
            print(f"执行RPC检查时出错: {e}")
            
        # 检查钱包列表
        print("\n检查钱包列表:")
        list_cmd = ["bitcoin-cli", "listwallets"]
        try:
            list_process = subprocess.run(list_cmd, capture_output=True, text=True)
            wallets_output = list_process.stdout.strip() or "[]"
            print(f"钱包列表: {wallets_output}")
            
            # 尝试解析JSON
            try:
                wallets = json.loads(wallets_output)
                print(f"检测到 {len(wallets)} 个已加载钱包")
                
                if wallet_name not in wallets:
                    print(f"⚠️ 警告: '{wallet_name}' 不在已加载钱包列表中!")
                else:
                    print(f"✅ 钱包 '{wallet_name}' 已在已加载列表中")
            except:
                print(f"⚠️ 无法解析钱包列表JSON: {wallets_output}")
        except Exception as e:
            print(f"获取钱包列表时出错: {e}")
            
        # 尝试加载钱包
        print(f"\n尝试加载钱包 '{wallet_name}':")
        load_cmd = ["bitcoin-cli", "loadwallet", wallet_name]
        try:
            load_process = subprocess.run(load_cmd, capture_output=True, text=True)
            result = load_process.stdout.strip() or load_process.stderr.strip()
            print(f"加载结果: {result}")
            
            # 检查常见错误信息
            if "already loaded" in result:
                print("✅ 钱包已经加载 (这是正常的)")
            elif "not found" in result:
                print(f"❌ 钱包文件未找到! 请确认 '{wallet_name}' 是正确的钱包名称")
            elif "error" in result.lower():
                print(f"❌ 加载钱包时出错")
        except Exception as e:
            print(f"加载钱包时出错: {e}")
            
        # 检查钱包信息
        print(f"\n检查钱包 '{wallet_name}' 信息:")
        info_cmd = ["bitcoin-cli", "-rpcwallet=" + wallet_name, "getwalletinfo"]
        try:
            info_process = subprocess.run(info_cmd, capture_output=True, text=True)
            wallet_info = info_process.stdout.strip() or info_process.stderr.strip()
            print(f"钱包信息: {wallet_info}")
            
            # 尝试解析JSON获取更详细信息
            try:
                wallet_data = json.loads(wallet_info)
                if "error" in wallet_data:
                    print(f"❌ 获取钱包信息错误: {wallet_data['error']['message']}")
                else:
                    # 钱包正常信息
                    print(f"✅ 钱包名称: {wallet_data.get('walletname', '未知')}")
                    print(f"✅ 钱包版本: {wallet_data.get('walletversion', '未知')}")
                    print(f"✅ 钱包余额: {wallet_data.get('balance', '未知')}")
                    print(f"✅ 锁定状态: {'已锁定' if wallet_data.get('unlocked_until', 0) == 0 else '已解锁'}")
            except json.JSONDecodeError:
                print(f"⚠️ 无法解析钱包信息JSON: {wallet_info}")
                
        except Exception as e:
            print(f"获取钱包信息时出错: {e}")
            
        # ========================
        # Bitcoin Core验证步骤
        # ========================
        print("\n===== Bitcoin Core验证步骤 =====")
        print(f"使用密码 '{found_password}' 尝试验证Bitcoin Core钱包 '{wallet_name}'")
        
        # 直接使用bitcoin-cli自己尝试解锁
        print("\n直接通过bitcoin-cli验证密码:")
        unlock_cmd = ["bitcoin-cli", "-rpcwallet=" + wallet_name, "walletpassphrase", found_password, "2"]
        try:
            direct_unlock = subprocess.run(unlock_cmd, capture_output=True, text=True)
            if direct_unlock.returncode == 0 and not direct_unlock.stderr:
                print(f"✅ 直接验证成功! 钱包使用密码 '{found_password}' 成功解锁")
                # 立即锁定
                subprocess.run(["bitcoin-cli", "-rpcwallet=" + wallet_name, "walletlock"], capture_output=True)
                direct_success = True
            else:
                error_msg = direct_unlock.stderr.strip() or direct_unlock.stdout.strip()
                print(f"❌ 直接验证失败: {error_msg}")
                direct_success = False
        except Exception as e:
            print(f"直接验证时出错: {e}")
            direct_success = False

        # 通过函数验证
        print("\n通过test_bitcoin_core_password函数验证密码:")
        try:
            # 手动执行test_bitcoin_core_password中的逻辑来获取更多调试信息
            unlock_cmd = ["bitcoin-cli", "-rpcwallet=" + wallet_name, "walletpassphrase", found_password, "2"]
            process = subprocess.run(unlock_cmd, capture_output=True, text=True)
            
            print(f"解锁命令返回码: {process.returncode}")
            print(f"解锁命令标准输出: '{process.stdout}'")
            print(f"解锁命令错误输出: '{process.stderr}'")
            
            if process.returncode == 0 and not "error" in process.stderr.lower():
                print("✅ 解锁成功")
                success = True
                message = "密码验证成功"
            else:
                print("❌ 解锁失败")
                success = False
                message = process.stderr or "未知错误"
                
                # 额外检查常见错误
                if "Method not found" in message:
                    print("❌ 钱包可能未加密或RPC方法不存在")
                elif "wallet is not encrypted" in message.lower():
                    print("⚠️ 钱包未加密，无需密码")
                elif "incorrect passphrase" in message.lower():
                    print("❌ 密码不正确")
                    
            # 确保钱包锁定
            lock_cmd = ["bitcoin-cli", "-rpcwallet=" + wallet_name, "walletlock"]
            lock_process = subprocess.run(lock_cmd, capture_output=True, text=True)
            if lock_process.returncode == 0:
                print("✅ 已重新锁定钱包")
            else:
                print(f"⚠️ 锁定钱包失败: {lock_process.stderr}")
                
        except Exception as e:
            success = False
            message = str(e)
            print(f"❌ 验证过程中出错: {e}")
        
        if success:
            print(f"✅ 验证成功! 密码 '{found_password}' 成功解锁钱包!")
        else:
            print(f"❌ 验证失败! 密码 '{found_password}' 无法解锁钱包!")
            print(f"失败信息: {message}")
            
        # 尝试手动获取钱包列表信息
        print("\n获取可用钱包目录:")
        try:
            bitcoin_dirs = [
                os.path.expanduser("~/.bitcoin/wallets"),           # Linux/MacOS默认
                os.path.expanduser("~/Library/Application Support/Bitcoin/wallets"),  # MacOS备用
                os.path.expanduser("~/AppData/Roaming/Bitcoin/wallets"),  # Windows
            ]
            
            for bitcoin_dir in bitcoin_dirs:
                if os.path.exists(bitcoin_dir):
                    print(f"找到钱包目录: {bitcoin_dir}")
                    wallets = os.listdir(bitcoin_dir)
                    print(f"目录内容: {wallets}")
                    
                    # 检查钱包是否存在
                    if wallet_name in wallets:
                        print(f"✅ 找到钱包 '{wallet_name}' 在 {bitcoin_dir}")
                    else:
                        print(f"❌ 在 {bitcoin_dir} 中未找到 '{wallet_name}'")
                        
                        # 检查是否使用了完整路径
                        for potential_wallet in wallets:
                            if potential_wallet in wallet_name or wallet_name in potential_wallet:
                                print(f"⚠️ 可能相关的钱包: {potential_wallet}")
        except Exception as e:
            print(f"检查钱包目录时出错: {e}")
            
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