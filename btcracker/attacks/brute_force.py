import time
import itertools
from concurrent.futures import ProcessPoolExecutor
from btcracker.core.wallet import test_password
import subprocess
from btcracker.attacks.dictionary import test_bitcoin_core_password

def brute_force_attack(wallet_file, charset, min_length, max_length, num_workers=4):
    """Perform a brute force attack using the given character set and length range."""
    print(f"Starting brute force attack with charset: {charset}")
    print(f"Length range: {min_length} to {max_length}")
    
    start_time = time.time()
    tested = 0
    
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        for length in range(min_length, max_length + 1):
            print(f"Trying passwords of length {length}")
            
            # Generate all possible combinations of the given length
            for combo in itertools.product(charset, repeat=length):
                password = ''.join(combo)
                future = executor.submit(test_password, wallet_file, password)
                success, found_password = future.result()
                tested += 1
                
                if tested % 1000 == 0:
                    elapsed = time.time() - start_time
                    print(f"Tested {tested} passwords in {elapsed:.2f} seconds ({tested/elapsed:.2f} p/s)")
                
                if success:
                    print(f"\nPassword found: {found_password}")
                    return found_password
    
    print(f"Password not found. Tested {tested} passwords in {time.time() - start_time:.2f} seconds")
    return None

def bitcoin_core_brute_force(wallet_name, charset, min_length, max_length):
    """使用Bitcoin Core直接进行暴力破解"""
    print(f"使用Bitcoin Core进行暴力破解，字符集: {charset}")
    print(f"密码长度范围: {min_length} 到 {max_length}")
    
    # 确保钱包已加载
    try:
        load_cmd = ["bitcoin-cli", "loadwallet", wallet_name]
        subprocess.run(load_cmd, capture_output=True)
    except:
        # 钱包可能已加载，忽略错误
        pass
    
    start_time = time.time()
    tested = 0
    
    for length in range(min_length, max_length + 1):
        print(f"尝试长度为 {length} 的密码")
        
        # 生成所有可能的组合
        for combo in itertools.product(charset, repeat=length):
            password = ''.join(combo)
            success, found_password = test_bitcoin_core_password(wallet_name, password)
            tested += 1
            
            if tested % 100 == 0:
                elapsed = time.time() - start_time
                print(f"已测试 {tested} 个密码，用时 {elapsed:.2f} 秒 ({tested/elapsed:.2f} p/s)")
            
            if success:
                print(f"\n找到密码: {found_password}")
                return found_password
    
    print(f"未找到密码。共测试 {tested} 个密码，用时 {time.time() - start_time:.2f} 秒")
    return None 