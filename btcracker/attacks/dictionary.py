import os
import time
from concurrent.futures import ProcessPoolExecutor
from btcracker.utils.progress import tqdm
from btcracker.utils.logging import log
from btcracker.utils.file_handling import extract_passwords_from_file
from btcracker.core.wallet import test_password
import subprocess

def dictionary_attack(wallet_file, wordlist_files, num_workers=4):
    """使用多个字典文件进行字典攻击"""
    if isinstance(wordlist_files, str):
        wordlist_files = [wordlist_files]

    total_tested = 0
    start_time = time.time()

    for wordlist_file in wordlist_files:
        if not os.path.exists(wordlist_file):
            log(f"跳过不存在的字典文件: {wordlist_file}", level=1)
            continue

        log(f"使用字典文件: {wordlist_file}", level=1)

        try:
            # 使用我们的提取函数处理文件
            password_list = extract_passwords_from_file(wordlist_file)
            
            if not password_list:
                log(f"从文件 {wordlist_file} 中未提取到密码，跳过", level=1)
                continue
                
            log(f"从 {wordlist_file} 中提取到 {len(password_list)} 个密码", level=1)

            with ProcessPoolExecutor(max_workers=num_workers) as executor:
                batch_size = 1000
                password_batches = [password_list[i:i+batch_size] for i in range(0, len(password_list), batch_size)]

                # 创建进度条
                with tqdm(total=len(password_list), desc="密码测试", unit="pwd") as pbar:
                    for batch in password_batches:
                        futures = []
                        for password in batch:
                            if not password:
                                continue
                            futures.append(executor.submit(test_password, wallet_file, password))

                        for future in futures:
                            success, found_password = future.result()
                            total_tested += 1
                            pbar.update(1)

                            if success:
                                elapsed = time.time() - start_time
                                speed = total_tested / elapsed if elapsed > 0 else 0
                                log(f"\n找到密码: {found_password} (测试了 {total_tested} 个密码，速度 {speed:.2f} p/s)", level=1)
                                return found_password
        except Exception as e:
            log(f"处理字典文件 {wordlist_file} 时出错: {str(e)}", level=1)
            continue

    elapsed = time.time() - start_time
    speed = total_tested / elapsed if elapsed > 0 else 0
    log(f"未找到密码。共测试 {total_tested} 个密码，速度 {speed:.2f} p/s", level=1)
    return None

def bitcoin_core_dictionary_attack(wallet_name, wordlist_files):
    """使用Bitcoin Core直接进行字典攻击"""
    if isinstance(wordlist_files, str):
        wordlist_files = [wordlist_files]

    total_tested = 0
    start_time = time.time()
    
    # 确保钱包已加载
    try:
        load_cmd = ["bitcoin-cli", "loadwallet", wallet_name]
        subprocess.run(load_cmd, capture_output=True)
    except:
        # 钱包可能已加载，忽略错误
        pass

    for wordlist_file in wordlist_files:
        if not os.path.exists(wordlist_file):
            log(f"跳过不存在的字典文件: {wordlist_file}", level=1)
            continue

        log(f"使用字典文件: {wordlist_file}", level=1)

        try:
            password_list = extract_passwords_from_file(wordlist_file)
            
            if not password_list:
                log(f"从文件 {wordlist_file} 中未提取到密码，跳过", level=1)
                continue
                
            log(f"从 {wordlist_file} 中提取到 {len(password_list)} 个密码", level=1)

            # 使用进度条显示破解进度
            with tqdm(total=len(password_list), desc="测试密码", unit="pwd") as pbar:
                for password in password_list:
                    if not password:
                        pbar.update(1)
                        continue
                        
                    success, found_password = test_bitcoin_core_password(wallet_name, password)
                    total_tested += 1
                    pbar.update(1)

                    if success:
                        elapsed = time.time() - start_time
                        speed = total_tested / elapsed if elapsed > 0 else 0
                        log(f"\n找到密码: {found_password} (测试了 {total_tested} 个密码，速度 {speed:.2f} p/s)", level=1)
                        return found_password
        except Exception as e:
            log(f"处理字典文件 {wordlist_file} 时出错: {str(e)}", level=1)
            continue

    elapsed = time.time() - start_time
    speed = total_tested / elapsed if elapsed > 0 else 0
    log(f"未找到密码。共测试 {total_tested} 个密码，速度 {speed:.2f} p/s", level=1)
    return None

def test_bitcoin_core_password(wallet_name, password):
    """使用Bitcoin Core RPC接口测试钱包密码"""
    try:
        # 使用subprocess调用bitcoin-cli
        unlock_cmd = ["bitcoin-cli", "-rpcwallet=" + wallet_name, "walletpassphrase", password, "2"]
        process = subprocess.run(unlock_cmd, capture_output=True, text=True)
        
        # 检查是否成功解锁
        if process.returncode == 0 and not "error" in process.stderr.lower():
            # 成功解锁了钱包，立即锁定
            subprocess.run(["bitcoin-cli", "-rpcwallet=" + wallet_name, "walletlock"], capture_output=True)
            return True, password
        
        # 确保钱包锁定（以防万一）
        subprocess.run(["bitcoin-cli", "-rpcwallet=" + wallet_name, "walletlock"], capture_output=True)
    except Exception as e:
        print(f"Bitcoin Core RPC错误: {e}")
    
    return False, None 