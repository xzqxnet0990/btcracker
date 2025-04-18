# BTCracker - 重构版本

这是对原始钱包密码破解工具的重构版本，将单一的大型脚本分解为更易维护的模块化结构。

## 主要变更

* 将单个大型文件 (wallet_cracker.py) 分解为模块化结构
* 创建了清晰的包目录结构，使代码更易于维护和扩展
* 提供了相同的功能，但代码组织更好
* 添加了可安装的包格式

## 目录结构

```
btcracker/                # 主包目录
├── __init__.py           # 包初始化文件
├── cli.py                # 命令行界面
├── core/                 # 核心功能
│   ├── __init__.py
│   ├── hash_extraction.py # 哈希提取功能
│   ├── processor.py      # 钱包处理逻辑
│   └── wallet.py         # 钱包相关功能
├── utils/                # 实用工具
│   ├── __init__.py
│   ├── file_handling.py  # 文件处理功能
│   ├── logging.py        # 日志功能
│   └── progress.py       # 进度条功能
├── attacks/              # 攻击方法
│   ├── __init__.py
│   ├── brute_force.py    # 暴力破解功能
│   ├── dictionary.py     # 字典攻击功能
│   ├── hashcat.py        # Hashcat集成
│   └── john.py           # John the Ripper集成
└── wallet_types/         # 钱包类型处理（未来扩展）
    └── __init__.py
```

## 使用方法

### 1. 直接运行

可以使用包含的运行脚本直接运行程序，无需安装：

```
python btcracker_run.py --help
```

### 2. 安装包

可以将程序安装为Python包，然后使用命令行工具：

```
pip install -e .
btcracker --help
```

### 3. 作为模块运行

也可以直接作为Python模块运行：

```
python -m btcracker.cli --help
```

## 命令示例

使用方法与原版相同：

1. 直接破解钱包文件:
```
python btcracker_run.py wallet.dat -D 字典目录
```

2. Bitcoin Core模式:
```
python btcracker_run.py --bitcoin-core 钱包名 -D 字典目录
```

3. 使用Hashcat加速:
```
python btcracker_run.py --bitcoin-core 钱包名 --hashcat -D 字典目录
```

4. 暴力破解:
```
python btcracker_run.py wallet.dat -b -m 4 -M 8
```

5. 列出支持的钱包类型:
```
python btcracker_run.py --list-wallet-types
```

## 维护说明

* 每个文件都有清晰的功能范围，使代码更易于维护
* 添加新功能时，可以在适当的模块中进行扩展
* 不同类型的钱包支持可以在wallet_types目录中进行扩展 