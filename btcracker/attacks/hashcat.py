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
    
    # 直接使用本地hashcat/rules目录
    local_rules_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../hashcat/rules")
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
    
    rules_to_use = []
    if os.path.exists(local_rules_dir) and os.path.isdir(local_rules_dir):
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
    else:
        print(f"警告：本地规则目录 {local_rules_dir} 不存在或不是目录")
        log(f"警告：本地规则目录 {local_rules_dir} 不存在或不是目录", level=1)
    
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
            
            # 从字典文件提取密码，以备内置方法使用
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
        
        # 基本命令
        base_cmd = [
            "hashcat",
            "-m", str(hash_mode),
            hash_file,
            "--potfile-path", potfile,
            "-o", output_file,
            "--status",
            "--status-timer", "5",
            "--outfile-format", "3"
        ]

        # 根据攻击模式构建命令并执行
        found_password = None
        
        # 字典攻击模式
        if attack_mode == 0:
            if wordlist_file:
                cmd = base_cmd.copy()
                cmd.extend(["-a", "0", wordlist_file])
                
                print(f"执行字典攻击命令: {' '.join(cmd)}")
                
                try:
                    # 执行hashcat
                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                             text=True, bufsize=1, universal_newlines=True)
                    
                    # 设置超时时间，避免单个规则文件花费太长时间
                    start_time = time.time()
                    max_rule_time = 120  # 每个规则最多运行2分钟
                    
                    # 监控输出
                    while process.poll() is None and (time.time() - start_time) < max_rule_time:
                        stdout_line = process.stdout.readline().strip()
                        if stdout_line:
                            print(f"hashcat输出: {stdout_line}")
                            if "Status....." in stdout_line and "Cracked" in stdout_line:
                                print(f"检测到hashcat已破解密码! 读取结果...")
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
                                    found_password = show_output.split(":", 1)[1]
                                    print(f"\n成功! 在potfile中找到匹配的密码: {found_password}")
                                break
                        
                        # 检查是否找到密码
                        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                            with open(output_file, "r") as f:
                                output_content = f.read().strip()
                                if ":" in output_content:
                                    found_password = output_content.split(":", 1)[1]
                                    print(f"\n成功! 找到密码: {found_password}")
                                    process.terminate()
                                    break
                        
                        # 检查potfile是否有内容
                        if os.path.exists(potfile) and os.path.getsize(potfile) > 0:
                            with open(potfile, "r") as f:
                                potfile_content = f.read().strip()
                                if ":" in potfile_content:
                                    found_password = potfile_content.split(":", 1)[1]
                                    print(f"\n成功! 在potfile中找到密码: {found_password}")
                                    process.terminate()
                                    break
                        
                        time.sleep(1)  # 每秒检查一次
                    
                    # 终止超时的进程
                    if process.poll() is None:
                        print(f"规则运行超时，终止处理")
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                    
                    # 再次检查是否找到密码
                    if not found_password:
                        if os.path.exists(potfile) and os.path.getsize(potfile) > 0:
                            with open(potfile, "r") as f:
                                potfile_content = f.read().strip()
                                if ":" in potfile_content:
                                    found_password = potfile_content.split(":", 1)[1]
                                    print(f"\n成功! 在potfile中找到密码: {found_password}")
                except Exception as e:
                    print(f"执行hashcat字典攻击时出错: {e}")
            
            # 检查是否找到密码
            valid_password = None
            
            if found_password:
                # 验证密码
                if "bitcoin" in hash_file:
                    try:
                        wallet_name = os.path.basename(os.path.dirname(hash_file))
                        success, _ = test_bitcoin_core_password(wallet_name, found_password)
                        if success:
                            print("密码验证成功！")
                            valid_password = found_password
                            return valid_password
                        else:
                            print("警告: 密码无法通过Bitcoin Core验证，可能是误报")
                            # 不立即返回，继续尝试其他方法
                    except Exception as e:
                        print(f"验证密码时出错: {e}")
                        # 出错时也不要立即返回
                else:
                    # 非Bitcoin钱包情况，直接返回找到的密码
                    valid_password = found_password
                    return valid_password
                    
            # 如果hashcat没有找到有效密码，尝试内置字典攻击方法
            if not valid_password and passwords and "bitcoin" in hash_file:
                print("hashcat未找到有效密码，尝试使用内置字典攻击方法...")
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
            
            # 如果找到了密码但验证失败，且没有找到更好的密码，返回最初找到的密码
            # 这样调用者可以决定如何处理可能的误报
            if found_password and not valid_password:
                print(f"警告: 返回可能的密码: {found_password}，但Bitcoin Core验证失败")
                return found_password
            
            # 如果没有找到任何密码（甚至可能的误报），返回None
            return None
        
        # 规则攻击模式
        elif attack_mode == 1:
            # 如果没有指定字典，创建一个包含常见密码的字典
            if not wordlist_file:
                wordlist_file = os.path.join(os.path.dirname(hash_file), "common_passwords.txt")
                try:
                    with open(wordlist_file, "w") as f:
                        f.write("\n".join([
                            "password", "123456", "12345678", "abc123", "qwerty", "monkey", "letmein",
                            "dragon", "111111", "baseball", "iloveyou", "trustno1", "1234567", "sunshine",
                            "master", "123123", "welcome", "shadow", "ashley", "football", "jesus",
                            "michael", "ninja", "mustang", "password1", "123456789", "bitcoin", "satoshi"
                        ]))
                    print(f"创建默认密码字典: {wordlist_file}")
                except Exception as e:
                    print(f"创建默认密码字典时出错: {e}")
                    return None
            
            # 遍历规则文件
            for rule_name, rule_path in rules_to_use:
                # 基本命令
                cmd = base_cmd.copy()
                cmd.extend(["-a", "0", wordlist_file, "-r", rule_path])
                
                try:
                    print(f"使用规则 {rule_name} 执行攻击命令: {' '.join(cmd)}")
                    
                    # 执行破解过程 - 非阻塞方式
                    with open(os.devnull, 'w') as devnull:
                        process = subprocess.Popen(cmd, stdout=devnull, stderr=subprocess.PIPE, text=True)
                    
                    # 等待一段时间让 hashcat 开始工作
                    time.sleep(5)
                    
                    # 每5秒检查一次是否找到密码
                    max_checks = 6  # 最多等待30秒
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
                                        print(f"\n成功! 规则 {rule_name} 找到密码: {password}")
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
                                        print(f"\n成功! 规则 {rule_name} 找到密码: {password}")
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
                    
                    # 如果这个规则没有找到密码，我们继续下一个规则
                    print(f"规则 {rule_name} 未找到密码，尝试下一个规则")
                    
                except Exception as e:
                    print(f"使用规则 {rule_name} 执行hashcat时出错: {e}")
            
            print("所有规则均未找到密码")
            return None
        
        # 其他攻击模式暂未实现
        else:
            print(f"攻击模式 {attack_mode} 暂未实现")
            return None
            
    except Exception as e:
        print(f"执行hashcat攻击时出错: {e}")
        
    finally:
        # 清理临时文件
        if temp_wordlist and os.path.exists(temp_wordlist):
            try:
                os.remove(temp_wordlist)
                print(f"已移除临时字典文件: {temp_wordlist}")
            except Exception as e:
                print(f"移除临时字典文件时出错: {e}")
    
    return None