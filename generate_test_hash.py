#!/usr/bin/env python3
import os
import sys
import hashlib

def generate_test_hash(password="bitcoin"):
    """生成适合hashcat的bitcoin钱包哈希，格式与wallet_cracker.py兼容"""
    
    # 使用固定的盐值便于测试
    salt = "1234567890123456"
    
    # 根据密码和盐值计算关键数据
    key_material = hashlib.pbkdf2_hmac(
        'sha512', 
        password.encode('utf-8'),
        bytes.fromhex(salt),
        16,  # 迭代次数设置为16，与wallet_cracker.py中格式兼容
        64
    )
    
    # 添加Berkeley DB标记
    bdb_marker = "62310500"  # BDB 头标记 b'\x62\x31\x05\x00' 的十六进制表示
    hash_data = bdb_marker + key_material.hex()[:64]
    
    # 使用与wallet_cracker.py中完全相同的格式创建哈希字符串
    bitcoin_hash = f"$bitcoin$2$16${salt}$1$1$64$0000000000000000$16$0000000000000000000000000000000000000000000000000000000000000000${hash_data}"
    
    return bitcoin_hash

def main():
    # 默认使用'bitcoin'密码
    password = sys.argv[1] if len(sys.argv) > 1 else "bitcoin"
    hash_string = generate_test_hash(password)
    
    # 保存到文件
    with open("test_hash.txt", "w") as f:
        f.write(hash_string)
    
    # 创建包含正确密码的字典文件
    with open("test_dict.txt", "w") as f:
        f.write(f"{password}\n")
        # 添加一些明显错误的密码
        f.write("wrong1\nwrong2\nwrong3\nwrong4\n")
    
    print(f"生成的测试哈希: {hash_string}")
    print(f"哈希已保存到: test_hash.txt")
    print(f"测试字典已保存到: test_dict.txt")
    print(f"正确密码: {password}")
    print("\n可以使用以下命令测试:")
    print("python3 wallet_cracker.py --test-hash test_hash.txt -d test_dict.txt")

if __name__ == "__main__":
    main() 