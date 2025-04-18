import os
import sys
from btcracker.utils.logging import log

# 添加BTCRecover子模块路径
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../btcrecover"))

try:
    from pywallet import wallet
except ImportError:
    print("Error: pywallet module not found")
    print("Please install it using: pip install pywallet")
    sys.exit(1)

try:
    import btcrecover.btcrpass
    BTCRECOVER_AVAILABLE = True
except ImportError:
    BTCRECOVER_AVAILABLE = False
    print("Warning: btcrecover module not found, some wallet types may not be supported")

def test_password(wallet_file, password):
    """Test if the password can decrypt the wallet file."""
    try:
        # Attempt to open the wallet with the given password
        wallet_data = wallet.WalletDat(wallet_file)
        result = wallet_data.read_wallet(password)
        if result:
            return True, password
    except ImportError as e:
        print(f"ImportError: {e} - 可能是加密库路径问题")
        print("建议: 运行 fix_crypto.py 修复脚本")
        return False, None
    except Exception as e:
        # macOS经常出现的加密库错误
        if "unsafe way" in str(e) or "libcrypto" in str(e):
            print(f"加密库错误: {e}")
            print("建议: 设置 export CRYPTOGRAPHY_OPENSSL_NO_LEGACY=1")
        # 其他常见错误
        elif "cannot import name" in str(e):
            print(f"模块导入错误: {e}") 
            print("建议: 使用虚拟环境并降级pycryptodome")
        # 静默处理其他错误
        pass
    
    # If pywallet fails, try btcrecover if available
    if BTCRECOVER_AVAILABLE:
        try:
            tokenlist = btcrecover.btcrpass.TokenList(password)
            wallet_obj = btcrecover.btcrpass.WalletBase.wallet_factory(wallet_file)
            if wallet_obj.return_verified_password_or_false(tokenlist) is not False:
                return True, password
        except Exception as e:
            # 仅在调试模式下打印btcrecover错误
            if os.environ.get("BTC_DEBUG") == "1":
                print(f"btcrecover 错误: {e}")
            pass
            
    return False, None

def detect_wallet_type(wallet_file):
    """根据文件特征检测钱包类型"""
    try:
        file_ext = os.path.splitext(wallet_file)[1].lower()
        
        # 根据扩展名判断
        if file_ext == '.dat':
            # 尝试以Bitcoin Core wallet.dat打开
            try:
                with open(wallet_file, 'rb') as f:
                    header = f.read(16)
                    if b'\x62\x31\x05\x00' in header or b'\x00\x05\x31\x62' in header:  # Berkeley DB magic header
                        return "Bitcoin Core wallet.dat"
            except:
                pass
            
        elif file_ext == '.wallet':
            # 检查是否是MultibitHD钱包
            try:
                with open(wallet_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(1000)
                    if "multibit" in content.lower() or "aes" in content.lower():
                        return "Multibit HD wallet"
            except:
                pass
                
        elif file_ext == '.json':
            # 检查是否是Electrum钱包
            try:
                with open(wallet_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(1000)
                    if "electrum" in content.lower():
                        return "Electrum wallet"
                    elif "ethers" in content.lower() or "ethereum" in content.lower():
                        return "Ethereum wallet"
            except:
                pass
                
        elif file_ext == '.keys':
            return "Electrum keys file"
            
        # 通过文件内容判断
        try:
            with open(wallet_file, 'rb') as f:
                header = f.read(1000)
                if b'wallet' in header and b'bitcoin' in header:
                    return "Bitcoin wallet"
                elif b'ethereum' in header or b'eth' in header:
                    return "Ethereum wallet"
                elif b'electrum' in header:
                    return "Electrum wallet"
        except:
            pass
            
    except Exception as e:
        print(f"检测钱包类型时出错: {str(e)}")
    
    return "未知"

def collect_wallet_files(wallet_dir):
    """收集指定目录下的所有钱包文件，支持多种钱包格式"""
    wallet_files = []
    if not os.path.exists(wallet_dir):
        print(f"错误：钱包目录 {wallet_dir} 不存在")
        return wallet_files

    # 支持的钱包文件扩展名和描述
    wallet_extensions = {
        '.dat': 'Bitcoin Core wallet.dat',
        '.wallet': 'Multibit/Multibit HD wallet',
        '.keys': 'Electrum wallet keys file',
        '.json': 'Possible JSON-format wallet (Electrum, MyEtherWallet, etc.)',
        '.db': 'Possible database-backed wallet',
        '.kdbx': 'KeePass wallet backup',
        '.bdb': 'Berkeley DB wallet'
    }

    found_wallets_by_type = {ext: 0 for ext in wallet_extensions}
    
    for root, dirs, files in os.walk(wallet_dir):
        for file in files:
            file_lower = file.lower()
            file_path = os.path.join(root, file)
            
            # 检查已知的钱包扩展名
            for ext, desc in wallet_extensions.items():
                if file_lower.endswith(ext):
                    wallet_files.append(file_path)
                    found_wallets_by_type[ext] += 1
                    break
                    
            # 特殊检查 - 某些钱包没有典型的扩展名
            if "wallet" in file_lower and os.path.getsize(file_path) > 1000:
                if not any(file_lower.endswith(ext) for ext in wallet_extensions):
                    wallet_files.append(file_path)
                    
    # 打印找到的钱包文件统计
    print("找到的钱包文件:")
    for ext, count in found_wallets_by_type.items():
        if count > 0:
            print(f"  {wallet_extensions[ext]}: {count}个")
    
    return wallet_files 