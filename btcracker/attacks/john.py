import os
import tempfile
import subprocess
from btcracker.utils.logging import log
from btcracker.utils.file_handling import extract_passwords_from_file

def john_attack(hash_file, wordlist_file=None, attack_mode=0, charset=None, 
               min_length=1, max_length=8, rule_file=None, john_path=None):
    """使用John the Ripper破解钱包哈希"""
    if not os.path.exists(hash_file):
        log(f"错误: 哈希文件 {hash_file} 不存在", level=1)
        return None
    
    # 默认使用bitcoin模式
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
            base_cmd = [john_bin, "--format=" + hash_mode, "--session=" + session_file, 
                        "--pot=" + session_file + ".pot", hash_file]
            
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
            cmd = [john_bin, "--format=" + hash_mode, "--session=" + session_file, 
                   "--pot=" + session_file + ".pot", hash_file]
            
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