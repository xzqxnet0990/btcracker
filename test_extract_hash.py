#!/usr/bin/env python3
# 测试提取比特币钱包哈希的不同方法

import os
import tempfile
import binascii
import struct
import subprocess
import time
from btcracker.utils.logging import log

# 钱包文件路径
WALLET_NAME = "bdb_wallet"
WALLET_PATH = os.path.expanduser(f"~/Library/Application Support/Bitcoin/wallets/{WALLET_NAME}/wallet.dat")

# 打印信息
def debug_log(msg):
    print(f"DEBUG: {msg}")

def read_wallet_data():
    """读取钱包文件数据"""
    with open(WALLET_PATH, 'rb') as f:
        wallet_data = f.read()
    return wallet_data

def generate_hash_format(key_data, salt_data, iterations=50000):
    """生成hashcat兼容的哈希格式"""
    key_hex = key_data.hex()
    salt_hex = salt_data.hex()
    return f"$bitcoin${len(key_data)}${key_hex}${len(salt_data)}${salt_hex}${iterations}$2$00$2$00"

def extract_all_candidate_pairs(wallet_data, mkey_pos=None):
    """提取所有可能的密钥-盐值对"""
    candidates = []
    
    # 首先查找可能的mkey标记
    if mkey_pos is None:
        mkey_pos = wallet_data.find(b'mkey')
        if mkey_pos == -1:
            debug_log("未找到mkey标记，使用完整搜索")
        else:
            debug_log(f"找到mkey标记在位置 {mkey_pos}")
    
    # 方法1: 从mkey标记周围提取
    if mkey_pos >= 0:
        debug_log(f"分析mkey位置: {mkey_pos}")
        # 显示mkey周围的数据
        context_start = max(0, mkey_pos - 32)
        context_end = min(len(wallet_data), mkey_pos + 256)
        debug_log(f"mkey上下文数据: {wallet_data[context_start:context_end].hex()}")
        
        # 尝试寻找标准结构中的值
        for offset in range(mkey_pos + 4, mkey_pos + 20):
            if offset < len(wallet_data):
                length_byte = wallet_data[offset]
                if 16 <= length_byte <= 96 and offset + 1 + length_byte < len(wallet_data):
                    key_data = wallet_data[offset+1:offset+1+length_byte]
                    debug_log(f"在偏移 {offset} 找到可能的密钥数据，长度 {length_byte}: {key_data.hex()}")
                    
                    # 检查后续的盐值
                    salt_pos = offset + 1 + length_byte
                    if salt_pos < len(wallet_data):
                        salt_length = wallet_data[salt_pos]
                        if 8 <= salt_length <= 32 and salt_pos + 1 + salt_length < len(wallet_data):
                            salt_data = wallet_data[salt_pos+1:salt_pos+1+salt_length]
                            debug_log(f"找到可能的盐值，长度 {salt_length}: {salt_data.hex()}")
                            
                            # 迭代次数
                            iterations = 50000
                            iter_pos = salt_pos + 1 + salt_length
                            if iter_pos + 4 <= len(wallet_data):
                                try:
                                    iter_bytes = wallet_data[iter_pos:iter_pos+4]
                                    iterations = struct.unpack("<I", iter_bytes)[0]
                                    debug_log(f"找到迭代次数: {iterations}")
                                except Exception as e:
                                    debug_log(f"解析迭代次数出错: {str(e)}")
                            
                            # 添加到候选列表
                            candidates.append((key_data, salt_data, iterations, "mkey_structure"))
    
    # 方法2: 搜索固定区域的所有组合
    regions = [
        (0, 32), (32, 64), (64, 96), (96, 128),
        (128, 160), (160, 192), (192, 224), (224, 256),
        (256, 288), (288, 320), (320, 352), (352, 384),
        (384, 416), (416, 448), (448, 480), (480, 512),
        (512, 544), (544, 576), (576, 608), (608, 640),
        (1024, 1056), (2048, 2080), (4096, 4128), (8192, 8224),
        (16376, 16408)  # mkey位置附近
    ]
    
    salt_candidates = [
        wallet_data[:16],  # 文件开头
        wallet_data[32:48],  # 第二个区块
        b'Bitcoin Core\x00\x00\x00\x00',  # 常见盐值
        b'mkey\x01' + b'\x00' * 12  # mkey标记
    ]
    
    for start, end in regions:
        if end <= len(wallet_data):
            key_data = wallet_data[start:end]
            if len(key_data) >= 32 and len(set(key_data)) > 5:  # 至少有5个不同字节
                debug_log(f"测试区域 {start}-{end} 的密钥: {key_data.hex()[:64]}")
                
                for salt in salt_candidates:
                    candidates.append((key_data[:32], salt[:16], 50000, f"region_{start}_{end}"))
    
    return candidates

def write_hash_to_file(hash_format):
    """将哈希写入临时文件"""
    fd, hash_file = tempfile.mkstemp(suffix='.hash')
    os.close(fd)
    
    with open(hash_file, 'w') as f:
        f.write(hash_format)
    
    return hash_file

def test_hash_with_hashcat(hash_file, wordlist_file):
    """使用hashcat测试哈希"""
    cmd = [
        "hashcat", 
        "-m", "11300", 
        hash_file, 
        "--status", 
        "--status-timer", "5", 
        "--potfile-path", f"hashcat_sessions/temp.potfile",
        "-o", "found_password.txt", 
        "--force", 
        "-D", "1", 
        "--backend-devices", "1", 
        "--self-test-disable",
        wordlist_file
    ]
    
    debug_log(f"运行hashcat命令: {' '.join(cmd)}")
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # 等待一段时间
        time.sleep(5)
        
        # 检查potfile
        potfile = "hashcat_sessions/temp.potfile"
        if os.path.exists(potfile) and os.path.getsize(potfile) > 0:
            with open(potfile, "r") as f:
                potfile_content = f.read().strip()
                if ":" in potfile_content:
                    password = potfile_content.split(":", 1)[1]
                    debug_log(f"找到密码: {password}")
                    process.terminate()
                    return password
        
        # 检查输出文件
        output_file = "found_password.txt"
        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            with open(output_file, "r") as f:
                content = f.read().strip()
                if ":" in content:
                    password = content.split(":", 1)[1]
                    debug_log(f"找到密码: {password}")
                    process.terminate()
                    return password
        
        # 终止进程
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        
    except Exception as e:
        debug_log(f"执行hashcat时出错: {str(e)}")
    
    return None

def main():
    # 确保输出目录存在
    os.makedirs("hashcat_sessions", exist_ok=True)
    
    # 读取钱包数据
    wallet_data = read_wallet_data()
    debug_log(f"读取了 {len(wallet_data)} 字节的钱包数据")
    
    # 设置测试的密码字典
    wordlist_file = "test_passwords.txt"
    if not os.path.exists(wordlist_file):
        debug_log(f"错误: 密码字典 {wordlist_file} 不存在")
        return
    
    # 提取所有可能的候选密钥-盐值对
    candidates = extract_all_candidate_pairs(wallet_data)
    debug_log(f"生成了 {len(candidates)} 个候选哈希值")
    
    # 测试每个候选
    for i, (key_data, salt_data, iterations, method) in enumerate(candidates):
        debug_log(f"\n测试候选 {i+1}/{len(candidates)} (方法: {method})")
        
        # 生成哈希格式
        hash_format = generate_hash_format(key_data, salt_data, iterations)
        debug_log(f"哈希格式: {hash_format}")
        
        # 写入文件
        hash_file = write_hash_to_file(hash_format)
        debug_log(f"哈希已写入文件: {hash_file}")
        
        # 使用hashcat测试
        password = test_hash_with_hashcat(hash_file, wordlist_file)
        
        # 如果找到密码，输出并退出
        if password:
            print(f"\n成功! 找到密码: {password}")
            print(f"使用方法: {method}")
            print(f"密钥数据: {key_data.hex()}")
            print(f"盐值数据: {salt_data.hex()}")
            print(f"迭代次数: {iterations}")
            print(f"哈希格式: {hash_format}")
            return
        
        # 清理临时文件
        try:
            os.remove(hash_file)
        except:
            pass
    
    print("未找到匹配的密码")

if __name__ == "__main__":
    main() 