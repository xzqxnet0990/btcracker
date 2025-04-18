#!/usr/bin/env python3
# 测试哈希检测功能

import sys
import tempfile
import os
from btcracker.attacks.hashcat import detect_hash_mode
from btcracker.utils.logging import set_log_level

def main():
    # 设置详细日志
    set_log_level(2)
    
    # 创建包含比特币钱包哈希的测试文件
    temp_hash = tempfile.mktemp(suffix='.txt')
    bitcoin_hash = "$bitcoin$64$4056efd04f56fb1f2c55d1421ade1155f7118160c5eca4a89450d90bbc4fb6e5$16$8e76459faa448d54b1d4a71fce3c0e0e$2052$2$00$2$00"
    
    with open(temp_hash, 'w') as f:
        f.write(bitcoin_hash)
        
    try:
        # 测试哈希模式检测
        print(f"测试文件: {temp_hash}")
        print(f"测试哈希: {bitcoin_hash}")
        
        hash_mode = detect_hash_mode(temp_hash)
        
        if hash_mode == 11300:
            print("\n成功 ✓ 正确检测到Bitcoin钱包哈希模式(11300)")
        else:
            print(f"\n失败 ✗ 检测到错误的哈希模式: {hash_mode}, 应为11300")
        
    finally:
        # 清理临时文件
        if os.path.exists(temp_hash):
            os.unlink(temp_hash)

if __name__ == "__main__":
    main() 