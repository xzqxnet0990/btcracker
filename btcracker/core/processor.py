import os
import sys
from btcracker.utils.logging import log
from btcracker.core.wallet import detect_wallet_type, test_password
from btcracker.core.hash_extraction import extract_hash_from_wallet, bitcoin_core_extract_hash, bitcoin_core_extract_hash_with_bitcoin2john
from btcracker.attacks.dictionary import dictionary_attack, bitcoin_core_dictionary_attack, test_bitcoin_core_password
from btcracker.attacks.brute_force import brute_force_attack, bitcoin_core_brute_force

# Conditional imports - these may not be available on all systems
try:
    from btcracker.attacks.hashcat import hashcat_attack
    HASHCAT_AVAILABLE = True
except ImportError:
    HASHCAT_AVAILABLE = False
    log("Hashcat module not available", level=1)

try:
    from btcracker.attacks.john import john_attack
    JOHN_AVAILABLE = True
except ImportError:
    JOHN_AVAILABLE = False
    log("John the Ripper module not available", level=1)

def process_wallet(wallet_file, args):
    """处理单个钱包文件"""
    print(f"\n开始处理钱包文件: {wallet_file}")
    
    # 检测钱包类型
    wallet_type = detect_wallet_type(wallet_file)
    print(f"检测到的钱包类型: {wallet_type}")
    
    # 尝试使用字典和暴力破解方法
    if args.hashcat and HASHCAT_AVAILABLE:
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
        
        # 进行破解尝试
        if args.dictionary or args.dictionary_dir:
            wordlist_files = []
            if args.dictionary:
                wordlist_files.append(args.dictionary)
            if args.dictionary_dir:
                from btcracker.utils.file_handling import collect_password_files
                wordlist_files.extend(collect_password_files(args.dictionary_dir))
                
            print(f"开始使用 {len(wordlist_files)} 个字典文件进行破解...")
            
            for wordlist_file in wordlist_files:
                if not os.path.exists(wordlist_file):
                    print(f"警告: 字典文件 {wordlist_file} 不存在，跳过")
                    continue
                    
                print(f"使用字典: {wordlist_file}")
                password = hashcat_attack(hash_file, wordlist_file, 0, None, args.min_length, args.max_length, args.cpu_only)
                if password:
                    print(f"成功！钱包 {wallet_file} 的密码是: {password}")
                    return True
            
            print(f"hashcat字典攻击未找到钱包 {wallet_file} 的密码")
                    
        if args.brute_force:
            password = hashcat_attack(hash_file, None, 3, args.charset, args.min_length, args.max_length, args.cpu_only)
            if password:
                print(f"成功！钱包 {wallet_file} 的密码是: {password}")
                return True
            else:
                print(f"hashcat暴力破解未找到钱包 {wallet_file} 的密码")
                    
    elif args.john and JOHN_AVAILABLE:
        # 提取哈希并使用John the Ripper
        hash_data, hash_file = extract_hash_from_wallet(wallet_file)
        if not hash_data:
            print("警告: 无法从钱包文件提取哈希")
            return False
            
        print("使用John the Ripper进行破解...")
        
        if args.dictionary or args.dictionary_dir:
            wordlist_files = []
            if args.dictionary:
                wordlist_files.append(args.dictionary)
            if args.dictionary_dir:
                from btcracker.utils.file_handling import collect_password_files
                wordlist_files.extend(collect_password_files(args.dictionary_dir))
                
            for wordlist_file in wordlist_files:
                print(f"使用字典: {wordlist_file}")
                password = john_attack(hash_file, wordlist_file, 0, rule_file=args.rule, john_path=args.john_path)
                if password:
                    print(f"成功！钱包 {wallet_file} 的密码是: {password}")
                    return True
            
            print(f"john字典攻击未找到钱包 {wallet_file} 的密码")
        
        if args.brute_force:
            password = john_attack(hash_file, None, 3, args.charset, args.min_length, args.max_length, args.rule, args.john_path)
            if password:
                print(f"成功！钱包 {wallet_file} 的密码是: {password}")
                return True
            else:
                print(f"john暴力破解未找到钱包 {wallet_file} 的密码")
                
    else:
        # 使用内置方法
        if args.dictionary or args.dictionary_dir:
            wordlist_files = []
            if args.dictionary:
                wordlist_files.append(args.dictionary)
            if args.dictionary_dir:
                from btcracker.utils.file_handling import collect_password_files
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

def process_bitcoin_core_wallet(wallet_name, args):
    """处理Bitcoin Core钱包"""
    print(f"\n开始处理Bitcoin Core钱包: {wallet_name}")
    
    # 初始化 hashcat/john 是否运行标志
    external_tool_used = False
    
    # 提取钱包哈希
    if args.hashcat and HASHCAT_AVAILABLE:
        external_tool_used = True
        print("提取钱包哈希...")
        
        # 首先尝试使用bitcoin2john提取哈希
        hash_format, hash_file = bitcoin_core_extract_hash_with_bitcoin2john(wallet_name)
        
        # 如果bitcoin2john失败，使用原来的方法
        if not hash_format or not hash_file:
            print("使用bitcoin2john提取哈希失败，尝试备用方法...")
            hash_format, hash_file = bitcoin_core_extract_hash(wallet_name)
            
        if not hash_format or not hash_file:
            print("错误: 无法从Bitcoin Core钱包提取哈希")
            print("将尝试内置方法...")
            external_tool_used = False
        else:    
            print(f"成功提取哈希到: {hash_file}")
                    
            # 使用哈希进行破解
            print("使用hashcat进行破解...")
            
            # 收集字典文件
            wordlist_files = []
            if args.dictionary:
                wordlist_files.append(args.dictionary)
            if args.dictionary_dir:
                from btcracker.utils.file_handling import collect_password_files
                wordlist_files.extend(collect_password_files(args.dictionary_dir))
                
            hashcat_success = False
            if wordlist_files:
                for wordlist_file in wordlist_files:
                    print(f"\n尝试字典: {wordlist_file}")
                    password = hashcat_attack(hash_file, wordlist_file, 0, None, 
                                            args.min_length, args.max_length, 
                                            args.cpu_only)
                    if password:
                        print(f"成功！使用字典 {wordlist_file} 找到密码: {password}")
                        # 验证密码
                        verify_success, _ = test_bitcoin_core_password(wallet_name, password)
                        if verify_success:
                            print("密码验证成功！")
                            hashcat_success = True
                            return True
                        else:
                            print("警告: 密码无法通过Bitcoin Core验证，可能是误报")
                
                print(f"hashcat字典攻击未找到钱包 {wallet_name} 的密码")
                        
            # 如果指定了暴力破解，使用暴力破解
            if args.brute_force and not hashcat_success:
                print("\n开始hashcat暴力破解...")
                password = hashcat_attack(hash_file, None, 3, args.charset, 
                                        args.min_length, args.max_length,
                                        args.cpu_only)
                if password:
                    print(f"成功！使用hashcat暴力破解找到密码: {password}")
                    # 验证密码
                    verify_success, _ = test_bitcoin_core_password(wallet_name, password)
                    if verify_success:
                        print("密码验证成功！")
                        hashcat_success = True
                        return True
                    else:
                        print("警告: 密码无法通过Bitcoin Core验证，可能是误报")
                else:
                    print(f"hashcat暴力破解未找到钱包 {wallet_name} 的密码")
    
    elif args.john and JOHN_AVAILABLE:
        external_tool_used = True
        print("提取钱包哈希...")
        
        # 首先尝试使用bitcoin2john提取哈希
        hash_format, hash_file = bitcoin_core_extract_hash_with_bitcoin2john(wallet_name)
        
        # 如果bitcoin2john失败，使用原来的方法
        if not hash_format or not hash_file:
            print("使用bitcoin2john提取哈希失败，尝试备用方法...")
            hash_format, hash_file = bitcoin_core_extract_hash(wallet_name)
            
        if not hash_format or not hash_file:
            print("错误: 无法从Bitcoin Core钱包提取哈希")
            print("将尝试内置方法...")
            external_tool_used = False
        else:
            print(f"成功提取哈希到: {hash_file}")
                
            print("使用John the Ripper进行破解...")
            
            # 收集字典文件
            wordlist_files = []
            if args.dictionary:
                wordlist_files.append(args.dictionary)
            if args.dictionary_dir:
                from btcracker.utils.file_handling import collect_password_files
                wordlist_files.extend(collect_password_files(args.dictionary_dir))
            
            john_success = False
            if wordlist_files:
                for wordlist_file in wordlist_files:
                    print(f"使用字典: {wordlist_file}")
                    password = john_attack(hash_file, wordlist_file, 0, None, args.min_length, args.max_length, args.rule, args.john_path)
                    if password:
                        print(f"John the Ripper字典攻击找到密码: {password}")
                        # 验证密码
                        verify_success, _ = test_bitcoin_core_password(wallet_name, password)
                        if verify_success:
                            print("密码验证成功！")
                            john_success = True
                            return True
                        else:
                            print("警告: 密码无法通过Bitcoin Core验证，可能是误报")
                print("John the Ripper字典攻击未找到密码")
            
            if args.brute_force and not john_success:
                password = john_attack(hash_file, None, 3, args.charset, args.min_length, args.max_length, args.rule, args.john_path)
                if password:
                    print(f"John the Ripper暴力破解找到密码: {password}")
                    # 验证密码
                    verify_success, _ = test_bitcoin_core_password(wallet_name, password)
                    if verify_success:
                        print("密码验证成功！")
                        john_success = True
                        return True
                    else:
                        print("警告: 密码无法通过Bitcoin Core验证，可能是误报")
                else:
                    print("John the Ripper暴力破解未找到密码")
    
    # 如果外部工具失败或未启用，使用内置方法
    if not args.extract_hash:  # 只有在不是仅提取哈希的情况下才使用内置方法
        # 仅当外部工具失败或未使用外部工具时才显示此消息
        if (args.hashcat and HASHCAT_AVAILABLE) or (args.john and JOHN_AVAILABLE):
            print("\n外部工具未找到密码，尝试使用内置方法...")
        else:
            print("使用内置方法进行破解...")
        
        # 收集字典文件
        wordlist_files = []
        if args.dictionary:
            wordlist_files.append(args.dictionary)
        if args.dictionary_dir:
            from btcracker.utils.file_handling import collect_password_files
            wordlist_files.extend(collect_password_files(args.dictionary_dir))
            
        if wordlist_files:
            password = bitcoin_core_dictionary_attack(wallet_name, wordlist_files)
            if password:
                print(f"成功！找到密码: {password}")
                return True
            print("内置字典攻击未找到密码")
            
        if args.brute_force:
            password = bitcoin_core_brute_force(wallet_name, args.charset, args.min_length, args.max_length)
            if password:
                print(f"成功！找到密码: {password}")
                return True
            print("内置暴力破解未找到密码")
    
    print("未能破解钱包 " + wallet_name)
    return False 