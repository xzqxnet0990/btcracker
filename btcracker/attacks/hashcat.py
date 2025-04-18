import os
import time
import platform
import tempfile
import subprocess
from btcracker.utils.logging import log
from btcracker.utils.file_handling import extract_passwords_from_file
from btcracker.attacks.dictionary import test_bitcoin_core_password, dictionary_attack

def detect_hash_mode(hash_file):
    """检测Hash文件的哈希模式
    
    参数:
        hash_file: Hash文件路径
        
    返回:
        int: Hashcat的哈希模式代码，如果无法检测则返回-1
    """
    try:
        if not os.path.exists(hash_file):
            log(f"错误: Hash文件不存在: {hash_file}", level=0)
            return -1
            
        with open(hash_file, 'r') as f:
            hash_data = f.read().strip()
            
        # 检测Bitcoin钱包哈希格式
        if hash_data.startswith('$bitcoin$'):
            return 11300  # Bitcoin/Litecoin wallet.dat
            
        # 其他格式可以在这里添加
        
        # 如果无法确定类型，返回-1
        log(f"警告: 无法识别Hash格式: {hash_data[:50]}...", level=1)
        return -1
        
    except Exception as e:
        log(f"检测Hash模式时出错: {str(e)}", level=0)
        return -1

def hashcat_attack(hash_file, wordlist_file=None, attack_mode=0, charset=None, 
                  min_length=1, max_length=8, cpu_only=False, resume=True):
    """Basic hashcat attack interface"""
    if not os.path.exists(hash_file):
        log(f"Error: Hash file {hash_file} not found", level=1)
        return None
    
    print(f"\n===== Hashcat攻击开始 =====")
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
    checkpoint_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../hashcat_sessions")
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
    output_file = os.path.join(os.getcwd(), "found_password.txt")
    
    try:
        # 检查hashcat是否安装
        try:
            hashcat_version = subprocess.run(["hashcat", "--version"], capture_output=True, text=True, timeout=5)
            print(f"检测到hashcat版本: {hashcat_version.stdout.strip()}")
        except (subprocess.SubprocessError, FileNotFoundError):
            print("错误: 未找到hashcat。请先安装hashcat。")
            return None
        
        # 字典攻击准备工作
        if attack_mode == 0 and wordlist_file:  
            if not os.path.exists(wordlist_file):
                print(f"错误: 字典文件 {wordlist_file} 不存在")
                return None
            
            # 处理非标准txt文件
            if not wordlist_file.endswith('.txt'):
                print(f"处理非文本字典文件: {wordlist_file}")
                passwords = extract_passwords_from_file(wordlist_file)
                
                if not passwords:
                    print(f"从 {wordlist_file} 中未提取到密码")
                    return None
                
                # 创建临时字典文件
                temp_wordlist = tempfile.mktemp(suffix='.txt')
                with open(temp_wordlist, 'w', encoding='utf-8') as f:
                    for pwd in passwords:
                        f.write(f"{pwd}\n")
                
                print(f"创建了包含 {len(passwords)} 个密码的临时字典文件")
                wordlist_file = temp_wordlist
        
        # 基础命令
        base_cmd = ["hashcat", "-m", str(hash_mode), hash_file, "--status", "--status-timer", "3"]
        
        # 添加会话和恢复功能
        base_cmd.extend(["--session", session_id, "--potfile-path", potfile])
        
        # 检查是否存在恢复文件，如果存在且resume=True则添加恢复参数
        if resume and os.path.exists(restore_file):
            print(f"找到恢复文件，从断点继续")
            base_cmd.append("--restore")
        else:
            # 如果不是恢复模式，则添加输出文件
            base_cmd.extend(["-o", output_file])
        
        # 检测操作系统和设备类型
        is_macos = platform.system() == "Darwin"
        is_arm = "arm" in platform.processor().lower()
        
        # Bitcoin钱包专用优化参数
        if hash_mode == 11300:
            print("应用Bitcoin钱包专用优化参数")
            # 优化内核速度参数
            base_cmd.extend(["--optimized-kernel-enable", "--workload-profile=3"])
            
            # 如果是CPU模式，增加线程优化
            if cpu_only or (is_macos and is_arm):
                base_cmd.extend(["--opencl-device-types=1", "--hwmon-disable", "--bitmap-min=12", "--bitmap-max=24", "--loopback"])
                
                # 使用单一密码模式，可能更适合某些 CPU
                base_cmd.append("--slow-candidates")
                
                # 降低工作量，增加成功率
                base_cmd.append("--weak")
        
        # 设置CPU/GPU选项
        if cpu_only or (is_macos and is_arm):
            if not cpu_only:
                print("检测到Apple Silicon，自动切换到CPU模式")
            else:
                print("根据用户设置，使用CPU模式")
                
            # macOS上的优化设置
            if is_macos:
                # 增加Apple Silicon上的CPU优化选项
                base_cmd.extend(["--force", "-D", "1", "--backend-devices", "1", "--backend-ignore-cuda", "--backend-ignore-opencl"])
                
                # 增加线程数和循环速度
                thread_count = os.cpu_count() or 8
                base_cmd.extend(["-T", str(thread_count), "--backend-info"])
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
        
        # 进行攻击 - 字典模式
        if attack_mode == 0 and wordlist_file:
            # 解析从输入文件提取所有密码用于备用方案
            passwords = []
            if os.path.exists(wordlist_file):
                try:
                    with open(wordlist_file, 'r', encoding='utf-8', errors='ignore') as f:
                        for line in f:
                            password = line.strip()
                            if password:
                                passwords.append(password)
                    print(f"从 {wordlist_file} 中提取了 {len(passwords)} 个密码")
                except Exception as e:
                    print(f"读取密码文件时出错: {e}")
            
            # 组合命令
            cmd = base_cmd.copy()
            cmd.append(wordlist_file)
            
            try:
                print(f"执行字典攻击命令: {' '.join(cmd)}")
                
                # 当处理比特币钱包时，在后台单独进行直接密码测试
                direct_test_result = None
                direct_test_thread = None
                
                # 执行主要破解过程 - 使用管道获取输出
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, universal_newlines=True)
                
                # 在 process 启动后启动后台线程
                if "bitcoin" in hash_file and passwords:
                    # 创建一个函数来在后台测试密码
                    def test_passwords_directly():
                        nonlocal direct_test_result
                        wallet_name = None
                        try:
                            # 尝试从钱包路径提取名称
                            # 从临时文件名提取钱包名称
                            # 查找Bitcoin钱包目录
                            bitcoin_dir = os.path.expanduser("~/Library/Application Support/Bitcoin/wallets")
                            if os.path.exists(bitcoin_dir):
                                for wallet_dir in os.listdir(bitcoin_dir):
                                    if os.path.isdir(os.path.join(bitcoin_dir, wallet_dir)):
                                        wallet_name = wallet_dir
                                        print(f"后台任务: 找到钱包名称 {wallet_name}")
                                        break
                                        
                            if wallet_name:
                                print(f"后台任务: 开始内置方法测试密码...")
                                # 测试前 3 个密码
                                test_passwords = passwords[:3]
                                for password in test_passwords:
                                    print(f"后台任务: 测试密码 {password}")
                                    success, _ = test_bitcoin_core_password(wallet_name, password)
                                    if success:
                                        direct_test_result = password
                                        print(f"后台任务: 找到密码: {direct_test_result}")
                                        # 提前终止 hashcat 进程
                                        if process.poll() is None:
                                            process.terminate()
                                        return
                        except Exception as e:
                            print(f"后台任务错误: {e}")
                    
                    # 启动后台线程
                    import threading
                    direct_test_thread = threading.Thread(target=test_passwords_directly)
                    direct_test_thread.daemon = True
                    print("启动后台密码测试线程...")
                    direct_test_thread.start()
                
                # 增加超时时间 - 最长等待5分钟
                start_time = time.time()
                max_wait_time = 600  # 增加到10分钟
                check_interval = 3    # 每3秒检查一次
                
                found_password = None
                
                # 直接从输出流读取结果
                while process.poll() is None and (time.time() - start_time) < max_wait_time:
                    # 检查是否找到密码 - 从输出流直接读取
                    stdout_line = process.stdout.readline().strip()
                    if stdout_line:
                        print(f"hashcat输出: {stdout_line}")  # 增加输出调试信息
                        if "Status....." in stdout_line and "Cracked" in stdout_line:
                            print(f"检测到hashcat已破解密码! 读取结果...")
                            # 终止进程
                            process.terminate()
                            break
                        elif "All hashes found as potfile" in stdout_line:
                            print(f"hashcat检测到哈希已在potfile中找到! 使用--show查看结果...")
                            process.terminate()
                            
                            # 使用--show选项查看匹配密码
                            show_cmd = ["hashcat", "-m", str(hash_mode), hash_file, "--show", "--force"]
                            show_process = subprocess.run(show_cmd, capture_output=True, text=True)
                            show_output = show_process.stdout.strip()
                            print(f"--show输出: {show_output}")
                            
                            if show_output and ":" in show_output:
                                password = show_output.split(":", 1)[1]
                                print(f"\n成功! 在potfile中找到匹配的密码: {password}")
                                found_password = password
                            break
                        elif "All hashes found" in stdout_line or "Exhausted" in stdout_line or "Recovered" in stdout_line:
                            print(f"hashcat可能已找到密码，检查结果...")
                            
                    # 检查potfile是否有内容
                    if os.path.exists(potfile) and os.path.getsize(potfile) > 0:
                        # 终止主进程
                        process.terminate()
                        
                        # 读取 potfile 获取密码
                        with open(potfile, "r") as f:
                            potfile_content = f.read().strip()
                            if ":" in potfile_content:
                                password = potfile_content.split(":", 1)[1]
                                if "exception" not in password.lower():  # 排除异常信息
                                    print(f"\n成功! 字典攻击找到密码: {password}")
                                    found_password = password
                                    break
                    
                    # 检查输出文件
                    if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                        # 终止主进程
                        process.terminate()
                        
                        with open(output_file, "r") as f:
                            password_data = f.read().strip()
                            if ":" in password_data:
                                password = password_data.split(":", 1)[1]
                                if "exception" not in password.lower():  # 排除异常信息
                                    print(f"\n成功! 字典攻击找到密码: {password}")
                                    found_password = password
                                    break
                    
                    # 等待一小段时间
                    time.sleep(check_interval)
                
                # 确保进程终止
                if process.poll() is None:
                    print("正在终止hashcat进程...")
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        print("强制终止hashcat进程")
                        process.kill()
                
                # 如果启动了后台线程，等待它完成
                if direct_test_thread and direct_test_thread.is_alive():
                    print("等待后台密码测试完成...")
                    direct_test_thread.join(timeout=5)  # 最多等待5秒钟
                
                # 检查后台密码测试结果
                if direct_test_result:
                    print(f"\n成功! 后台直接测试找到密码: {direct_test_result}")
                    return direct_test_result
                
                # 再次检查输出文件和potfile
                if not found_password:
                    if os.path.exists(potfile) and os.path.getsize(potfile) > 0:
                        with open(potfile, "r") as f:
                            potfile_content = f.read().strip()
                            if ":" in potfile_content:
                                password = potfile_content.split(":", 1)[1]
                                if "exception" not in password.lower():
                                    print(f"\n成功! 字典攻击找到密码: {password}")
                                    found_password = password
                
                    if not found_password and os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                        with open(output_file, "r") as f:
                            password_data = f.read().strip()
                            if ":" in password_data:
                                password = password_data.split(":", 1)[1]
                                if "exception" not in password.lower():
                                    print(f"\n成功! 字典攻击找到密码: {password}")
                                    found_password = password
                
                # 最后尝试使用内置方法
                if found_password:
                    # 验证密码
                    if "bitcoin" in hash_file:
                        wallet_name = os.path.basename(os.path.dirname(hash_file))
                        try:
                            success, _ = test_bitcoin_core_password(wallet_name, found_password)
                            if success:
                                print("密码验证成功！")
                                return found_password
                            else:
                                print("警告: 密码无法通过Bitcoin Core验证，可能是误报")
                        except Exception as e:
                            print(f"验证密码时出错: {e}")
                            # 但仍然返回找到的密码
                            return found_password
                    else:
                        return found_password
                
                print("Hashcat未找到密码")
                
                # 由于 hashcat 可能存在问题，如果我们有从字典文件提取的密码列表，使用内置方法尝试破解
                if passwords and "bitcoin" in hash_file:
                    print("hashcat无法找到密码，尝试使用内置字典攻击方法...")
                    wallet_name = None
                    
                    # 尝试从哈希文件路径提取钱包名称
                    try:
                        # 从临时文件名提取钱包名称
                        hash_basename = os.path.basename(hash_file)
                        if hash_basename.startswith("tmp") and hash_basename.endswith(".hash"):
                            # 查找Bitcoin钱包目录
                            bitcoin_dir = os.path.expanduser("~/Library/Application Support/Bitcoin/wallets")
                            if os.path.exists(bitcoin_dir):
                                for wallet_dir in os.listdir(bitcoin_dir):
                                    if os.path.isdir(os.path.join(bitcoin_dir, wallet_dir)):
                                        wallet_name = wallet_dir
                                        print(f"推测钱包名称: {wallet_name}")
                                        break
                    except Exception as e:
                        print(f"提取钱包名称时出错: {e}")
                    
                    if wallet_name:
                        print(f"尝试使用内置字典攻击方法破解钱包: {wallet_name}")
                        password = dictionary_attack(wallet_name, passwords)
                        if password:
                            print(f"\n成功! 内置字典攻击找到密码: {password}")
                            return password
                
                return None
                
            except Exception as e:
                print(f"执行hashcat字典攻击时出错: {e}")
                
                # 出错时尝试使用内置方法
                if passwords and "bitcoin" in hash_file:
                    print("hashcat出错，尝试使用内置字典攻击方法...")
                    wallet_name = None
                    
                    # 尝试从哈希文件路径提取钱包名称
                    try:
                        # 从临时文件名提取钱包名称
                        hash_basename = os.path.basename(hash_file)
                        if hash_basename.startswith("tmp") and hash_basename.endswith(".hash"):
                            # 查找Bitcoin钱包目录
                            bitcoin_dir = os.path.expanduser("~/Library/Application Support/Bitcoin/wallets")
                            if os.path.exists(bitcoin_dir):
                                for wallet_dir in os.listdir(bitcoin_dir):
                                    if os.path.isdir(os.path.join(bitcoin_dir, wallet_dir)):
                                        wallet_name = wallet_dir
                                        print(f"推测钱包名称: {wallet_name}")
                                        break
                    except Exception as e:
                        print(f"提取钱包名称时出错: {e}")
                    
                    if wallet_name:
                        print(f"尝试使用内置字典攻击方法破解钱包: {wallet_name}")
                        password = dictionary_attack(wallet_name, passwords)
                        if password:
                            print(f"\n成功! 内置字典攻击找到密码: {password}")
                            return password
        
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
            
            try:
                print(f"执行暴力破解命令: {' '.join(cmd)}")
                
                # 执行主要破解过程 - 非阻塞方式
                with open(os.devnull, 'w') as devnull:
                    process = subprocess.Popen(cmd, stdout=devnull, stderr=subprocess.PIPE, text=True)
                
                # 等待一段时间让 hashcat 开始工作
                time.sleep(5)
                
                # 每5秒检查一次是否找到密码
                max_checks = 10
                for i in range(max_checks):
                    # 检查是否找到密码
                    if os.path.exists(potfile) and os.path.getsize(potfile) > 0:
                        # 终止主进程
                        process.terminate()
                        
                        # 读取 potfile 获取密码
                        with open(potfile, "r") as f:
                            potfile_content = f.read().strip()
                            if ":" in potfile_content:
                                password = potfile_content.split(":", 1)[1]
                                if "exception" not in password.lower():  # 排除异常信息
                                    print(f"\n成功! 暴力破解找到密码: {password}")
                                    # 验证密码
                                    if "bitcoin" in hash_file:
                                        wallet_name = os.path.basename(os.path.dirname(hash_file))
                                        success, _ = test_bitcoin_core_password(wallet_name, password)
                                        if success:
                                            print("密码验证成功！")
                                            return password
                                        else:
                                            print("警告: 密码无法通过Bitcoin Core验证，可能是误报")
                                    else:
                                        return password
                    
                    # 检查输出文件
                    if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                        # 终止主进程
                        process.terminate()
                        
                        with open(output_file, "r") as f:
                            password_data = f.read().strip()
                            if ":" in password_data:
                                password = password_data.split(":", 1)[1]
                                if "exception" not in password.lower():  # 排除异常信息
                                    print(f"\n成功! 暴力破解找到密码: {password}")
                                    # 验证密码
                                    if "bitcoin" in hash_file:
                                        wallet_name = os.path.basename(os.path.dirname(hash_file))
                                        success, _ = test_bitcoin_core_password(wallet_name, password)
                                        if success:
                                            print("密码验证成功！")
                                            return password
                                        else:
                                            print("警告: 密码无法通过Bitcoin Core验证，可能是误报")
                                    else:
                                        return password
                    
                    # 检查进程是否已结束
                    if process.poll() is not None:
                        # 进程已结束，再次检查 potfile 和输出文件
                        if os.path.exists(potfile) and os.path.getsize(potfile) > 0:
                            with open(potfile, "r") as f:
                                potfile_content = f.read().strip()
                                if ":" in potfile_content:
                                    password = potfile_content.split(":", 1)[1]
                                    if "exception" not in password.lower():  # 排除异常信息
                                        print(f"\n成功! 暴力破解找到密码: {password}")
                                        # 验证密码
                                        if "bitcoin" in hash_file:
                                            wallet_name = os.path.basename(os.path.dirname(hash_file))
                                            success, _ = test_bitcoin_core_password(wallet_name, password)
                                            if success:
                                                print("密码验证成功！")
                                                return password
                                            else:
                                                print("警告: 密码无法通过Bitcoin Core验证，可能是误报")
                                        else:
                                            return password
                        
                        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                            with open(output_file, "r") as f:
                                password_data = f.read().strip()
                                if ":" in password_data:
                                    password = password_data.split(":", 1)[1]
                                    if "exception" not in password.lower():  # 排除异常信息
                                        print(f"\n成功! 暴力破解找到密码: {password}")
                                        # 验证密码
                                        if "bitcoin" in hash_file:
                                            wallet_name = os.path.basename(os.path.dirname(hash_file))
                                            success, _ = test_bitcoin_core_password(wallet_name, password)
                                            if success:
                                                print("密码验证成功！")
                                                return password
                                            else:
                                                print("警告: 密码无法通过Bitcoin Core验证，可能是误报")
                                        else:
                                            return password
                        
                        # 如果进程已结束且未找到密码，则跳出循环
                        break
                    
                    # 等待5秒
                    time.sleep(5)
                
                # 确保进程终止
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        
                print("未找到密码")
                return None
                
            except Exception as e:
                print(f"执行hashcat暴力破解时出错: {e}")
        
        print("未找到密码")
        return None
        
    except Exception as e:
        print(f"Hashcat攻击执行时出错: {e}")
        return None
    finally:
        # 清理临时文件
        if temp_wordlist and os.path.exists(temp_wordlist):
            try:
                os.remove(temp_wordlist)
            except:
                pass 