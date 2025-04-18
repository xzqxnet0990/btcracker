#!/usr/bin/env python3
"""
示例脚本：如何从旧版 wallet_cracker.py 迁移到新的模块化结构
"""

print("===== 从旧版 wallet_cracker.py 迁移到新版 btcracker 模块 =====")

print("\n1. 命令行使用示例")
print("==================")
print("旧版用法:")
print("  python wallet_cracker.py wallet.dat -D 字典目录")
print("  python wallet_cracker.py --bitcoin-core 钱包名 --hashcat -D 字典目录")
print("  python wallet_cracker.py wallet.dat -b -m 4 -M 8\n")

print("新版用法:")
print("  python btcracker_run.py wallet.dat -D 字典目录")
print("  python btcracker_run.py --bitcoin-core 钱包名 --hashcat -D 字典目录")
print("  python btcracker_run.py wallet.dat -b -m 4 -M 8")
print("  python -m btcracker.cli wallet.dat -D 字典目录")
print("  btcracker wallet.dat -D 字典目录 (安装后)")

print("\n2. 代码导入示例")
print("==================")
print("旧版代码:")
print('''
# 直接从脚本导入函数使用
from wallet_cracker import dictionary_attack, brute_force_attack, test_password

# 使用例子
success, password = test_password("wallet.dat", "my_password")
if success:
    print(f"密码是: {password}")
''')

print("\n新版代码:")
print('''
# 从模块导入函数使用
from btcracker.attacks.dictionary import dictionary_attack
from btcracker.attacks.brute_force import brute_force_attack
from btcracker.core.wallet import test_password

# 使用例子
success, password = test_password("wallet.dat", "my_password")
if success:
    print(f"密码是: {password}")
''')

print("\n3. 扩展功能示例")
print("==================")
print("旧版中扩展功能:")
print('''
# 需要直接修改 wallet_cracker.py 文件，添加新函数
def my_new_attack_method(wallet_file, ...):
    # 实现新的攻击方法
    pass
    
# 然后修改 main() 函数添加命令行支持
''')

print("\n新版中扩展功能:")
print('''
# 在适当的模块中添加新功能，例如创建新攻击方法
# 在 btcracker/attacks/my_attack.py
def my_new_attack_method(wallet_file, ...):
    # 实现新的攻击方法
    pass
    
# 然后在 btcracker/cli.py 中导入并添加命令行支持
''')

print("\n有关更多详细信息，请查看 README_REFACTOR.md 文件") 