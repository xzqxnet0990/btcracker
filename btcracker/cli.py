#!/usr/bin/env python3
# Bitcoin wallet.dat password cracker
# For educational purposes only
#
# 使用方法:
# 1. 直接破解钱包文件:   python -m btcracker.cli wallet.dat -D 字典目录
# 2. Bitcoin Core模式:  python -m btcracker.cli --bitcoin-core 钱包名 -D 字典目录
# 3. 使用Hashcat加速:   python -m btcracker.cli --bitcoin-core 钱包名 --hashcat -D 字典目录
# 4. 暴力破解:          python -m btcracker.cli wallet.dat -b -m 4 -M 8
# 5. 列出支持的钱包类型: python -m btcracker.cli --list-wallet-types
# 6. 仅提取哈希:        python -m btcracker.cli wallet.dat --extract-hash
# 7. 使用bitcoin2john:  python -m btcracker.cli wallet.dat --extract-hash --bitcoin2john

import os
import sys
import argparse
import tempfile
from btcracker.utils.logging import log, set_log_level
from btcracker.utils.file_handling import collect_password_files
from btcracker.core.wallet import collect_wallet_files, test_password, detect_wallet_type
from btcracker.core.processor import process_wallet, process_bitcoin_core_wallet
from btcracker.core.processor import extract_hash_from_wallet, bitcoin_core_extract_hash_with_bitcoin2john, bitcoin_core_extract_hash

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
    parser.add_argument("--test-hash", help="指定要破解的哈希文件路径")
    parser.add_argument("-v", "--verbose", action="store_true", help="输出详细日志信息")
    parser.add_argument("-q", "--quiet", action="store_true", help="仅输出关键信息")
    parser.add_argument("--extract-hash", action="store_true", help="仅提取哈希，不尝试破解")
    parser.add_argument("--bitcoin2john", action="store_true", help="使用内置的bitcoin2john提取哈希")
    parser.add_argument("--no-resume", action="store_true", help="不恢复之前的hashcat会话，重新开始")

    args = parse_args_custom(parser)
    
    # 设置日志级别
    if args.verbose:
        set_log_level(2)
    elif args.quiet:
        set_log_level(0)
    else:
        set_log_level(1)
    
    # 检查是否至少指定了一种攻击方法
    attack_methods = [
        args.dictionary is not None,
        args.dictionary_dir is not None,
        args.brute_force,
        args.hashcat,
        args.john
    ]
    
    if not any(attack_methods) and not args.extract_hash and not args.list_wallet_types:
        parser.error("需要指定至少一种攻击方法，如 --dictionary, --dictionary-dir, --brute-force, --hashcat 或 --john")
    
    # 如果指定了--list-wallet-types，列出支持的钱包类型并退出
    if args.list_wallet_types:
        print("支持的钱包类型:")
        print("  - Bitcoin Core (--bitcoin-core)")
        print("  - 通用钱包文件 (wallet.dat, wallet.old, wallet.bak)")
        print("  - 其他格式 (通过btcrecover模块)")
        return
    
    # 如果指定了--extract-hash，仅提取哈希并退出
    if args.extract_hash:
        if args.bitcoin_core:
            # 使用bitcoin2john方法
            if args.bitcoin2john:
                hash_format, hash_file = bitcoin_core_extract_hash_with_bitcoin2john(args.bitcoin_core)
                if hash_format and hash_file:
                    print(f"已使用bitcoin2john提取哈希并保存到: {hash_file}")
                    print(f"哈希格式: {hash_format}")
                else:
                    print("使用bitcoin2john提取哈希失败")
            else:
                # 使用原始方法
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
                    # 根据参数选择提取方法
                    if args.bitcoin2john:
                        hash_data, hash_file = extract_hash_from_wallet(wallet_file)
                    else:
                        # 这里可以调用其他的hash提取方法
                        hash_data, hash_file = extract_hash_from_wallet(wallet_file)
                        
                    if hash_data:
                        print(f"哈希格式: {hash_data[:50]}...")
                        print(f"保存到: {hash_file}")
                    else:
                        print("提取哈希失败")
            else:
                # 根据参数选择提取方法
                if args.bitcoin2john:
                    hash_data, hash_file = extract_hash_from_wallet(args.wallet_path)
                else:
                    # 这里可以调用其他的hash提取方法
                    hash_data, hash_file = extract_hash_from_wallet(args.wallet_path)
                    
                if hash_data:
                    print(f"哈希格式: {hash_data[:50]}...")
                    print(f"保存到: {hash_file}")
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
            # Importing here to avoid circular imports
            from btcracker.attacks.hashcat import hashcat_attack
            
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
            # Importing here to avoid circular imports
            from btcracker.attacks.john import john_attack
            
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
        success = process_bitcoin_core_wallet(args.bitcoin_core, args)
        if success:
            print(f"成功破解钱包 {args.bitcoin_core}")
            sys.exit(0)
        else:
            print(f"未能破解钱包 {args.bitcoin_core}")
            sys.exit(1)
    
    # 处理常规钱包文件
    if args.wallet_path:
        if os.path.isdir(args.wallet_path):
            # 处理目录中的所有钱包文件
            wallet_files = collect_wallet_files(args.wallet_path)
            if not wallet_files:
                print(f"在目录 {args.wallet_path} 中未找到任何钱包文件")
                sys.exit(1)
                
            success = False
            for wallet_file in wallet_files:
                if process_wallet(wallet_file, args):
                    success = True
                    print(f"成功破解钱包 {wallet_file}")
                    break
                    
            if not success:
                print("未能破解任何钱包文件")
                sys.exit(1)
        else:
            # 处理单个钱包文件
            if not os.path.exists(args.wallet_path):
                print(f"错误: 钱包文件 {args.wallet_path} 不存在")
                sys.exit(1)
                
            if process_wallet(args.wallet_path, args):
                print(f"成功破解钱包 {args.wallet_path}")
                sys.exit(0)
            else:
                print(f"未能破解钱包 {args.wallet_path}")
                sys.exit(1)
    else:
        print("错误: 必须指定钱包文件或Bitcoin Core钱包名称")
        sys.exit(1)

if __name__ == "__main__":
    main() 