#!/usr/bin/env python3
# macOS加密库修复脚本
# 用于解决pycryptodome和libcrypto在macOS上的问题

import os
import sys
import site
import subprocess
import shutil
from pathlib import Path

def fix_crypto_path():
    """修复Crypto模块的导入路径问题"""
    print("修复macOS上的加密库路径...")
    
    # 获取site-packages目录
    site_packages = site.getsitepackages()[0]
    
    # 查找Crypto目录
    crypto_path = Path(site_packages) / "Crypto"
    crypto_lower_path = Path(site_packages) / "crypto"
    
    # 检查并创建必要的符号链接
    if crypto_path.exists() and not crypto_lower_path.exists():
        print(f"创建crypto -> Crypto的符号链接")
        os.symlink(crypto_path, crypto_lower_path)
    elif crypto_lower_path.exists() and not crypto_path.exists():
        print(f"创建Crypto -> crypto的符号链接")
        os.symlink(crypto_lower_path, crypto_path)
    elif crypto_path.exists() and crypto_lower_path.exists():
        print("Crypto和crypto都存在，无需创建符号链接")
    else:
        print("警告: 未找到Crypto或crypto目录，pycryptodome可能未正确安装")

def install_compatible_versions():
    """安装兼容的加密库版本"""
    print("正在安装macOS兼容的加密库版本...")
    
    # 卸载可能冲突的包
    subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "pycryptodome", "pycrypto"])
    
    # 安装兼容版本
    subprocess.run([sys.executable, "-m", "pip", "install", "pycryptodome==3.19.0"])
    subprocess.run([sys.executable, "-m", "pip", "install", "cryptography==41.0.3"])
    subprocess.run([sys.executable, "-m", "pip", "install", "pyOpenSSL==23.2.0"])
    
    print("兼容版本已安装")

def set_environment_variables():
    """设置环境变量并提供用户指导"""
    print("\n===== 环境变量设置指南 =====")
    print("在终端中运行以下命令:")
    print("export CRYPTOGRAPHY_OPENSSL_NO_LEGACY=1")
    print("export DYLD_LIBRARY_PATH=/usr/local/opt/openssl/lib:$DYLD_LIBRARY_PATH")
    
    # 尝试添加到shell配置文件
    home = Path.home()
    zshrc = home / ".zshrc"
    bashrc = home / ".bashrc"
    
    shell_file = None
    if zshrc.exists():
        shell_file = zshrc
    elif bashrc.exists():
        shell_file = bashrc
        
    if shell_file:
        response = input(f"是否自动将环境变量添加到{shell_file}? (y/n): ")
        if response.lower() == 'y':
            with open(shell_file, 'a') as f:
                f.write("\n# 添加的加密库环境变量\n")
                f.write("export CRYPTOGRAPHY_OPENSSL_NO_LEGACY=1\n")
                f.write("export DYLD_LIBRARY_PATH=/usr/local/opt/openssl/lib:$DYLD_LIBRARY_PATH\n")
            print(f"环境变量已添加到{shell_file}")
            print(f"请运行 'source {shell_file}' 使其立即生效")

def run_diag_checks():
    """运行诊断检查"""
    print("\n===== 系统诊断检查 =====")
    
    # 检查Python版本
    print(f"Python版本: {sys.version}")
    
    # 检查操作系统
    print(f"操作系统: {sys.platform}")
    
    # 检查SSL库
    try:
        import ssl
        print(f"SSL版本: {ssl.OPENSSL_VERSION}")
    except ImportError:
        print("无法导入SSL模块")
    
    # 检查加密库
    try:
        import Crypto
        print(f"pycryptodome版本: {Crypto.__version__}")
        print(f"pycryptodome路径: {Crypto.__file__}")
    except ImportError:
        try:
            import crypto
            print(f"crypto版本: {crypto.__version__}")
            print(f"crypto路径: {crypto.__file__}")
        except ImportError:
            print("未找到pycryptodome/crypto模块")

def main():
    print("==== macOS加密库修复工具 ====")
    print("该工具将修复wallet_cracker.py在macOS上的加密库问题")
    
    # 运行诊断
    run_diag_checks()
    
    # 修复选项
    print("\n选择要执行的修复操作:")
    print("1. 全面修复 (推荐)")
    print("2. 仅安装兼容版本库")
    print("3. 仅修复模块路径")
    print("4. 仅显示环境变量设置")
    print("q. 退出")
    
    choice = input("请选择 [1-4/q]: ")
    
    if choice == "1":
        install_compatible_versions()
        fix_crypto_path()
        set_environment_variables()
        print("\n全面修复完成！请尝试重新运行wallet_cracker.py")
    elif choice == "2":
        install_compatible_versions()
    elif choice == "3":
        fix_crypto_path()
    elif choice == "4":
        set_environment_variables()
    elif choice.lower() == "q":
        print("退出")
        return
    else:
        print("无效选择")
        return
    
    print("\n操作完成！")
    print("如果问题仍然存在，请尝试在虚拟环境中运行程序:")
    print("python3 -m venv btc_venv")
    print("source btc_venv/bin/activate")
    print("pip install -r requirements.txt")

if __name__ == "__main__":
    main() 