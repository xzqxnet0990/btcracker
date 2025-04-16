# Bitcoin Core 安装与钱包密码恢复工具

这个项目提供了用于安装和管理 Bitcoin Core 的 Makefile，以及一个强大的钱包密码恢复工具 `wallet_cracker.py`。

## 功能特点

- 自动化安装和配置 Bitcoin Core
- 钱包创建、解锁和锁定功能
- 支持多种密码恢复方法：
  - 字典攻击
  - 暴力破解
  - John the Ripper 集成
  - Hashcat 集成（GPU 加速）

## 使用方法

### Bitcoin Core 安装与管理

```bash
# 安装 Bitcoin Core
make install

# 配置 Bitcoin Core
make configure

# 启动 Bitcoin Core 守护进程
make start

# 检查 Bitcoin Core 状态
make status

# 创建新钱包
make create-wallet NAME=mywallet

# 解锁钱包（设置密码）
make unlock NAME=mywallet PASS=mypassword

# 锁定钱包
make lock NAME=mywallet

# 停止 Bitcoin Core 守护进程
make stop
```

### 钱包密码恢复

使用 `wallet_cracker.py` 工具可以恢复忘记的钱包密码：

```bash
# 使用 Makefile 集成的测试目标
make test NAME=mywallet

# 直接使用 wallet_cracker.py
python3 wallet_cracker.py --bitcoin-core "mywallet" --john --john-path ./john --dictionary rockyou.txt

# 使用 Hashcat 加速
python3 wallet_cracker.py --bitcoin-core "mywallet" --hashcat --dictionary rockyou.txt
```

## 安装要求

- Python 3.6+
- Bitcoin Core
- 可选：John the Ripper（密码恢复）
- 可选：Hashcat（GPU 加速密码恢复）

### 可选组件安装

#### John the Ripper

```bash
# 克隆仓库
git clone https://github.com/openwall/john.git

# 编译（Unix/Linux/MacOS）
cd john/src
./configure && make
```

#### Hashcat

```bash
# 从官网下载: https://hashcat.net/hashcat/
# 或使用包管理器安装
# macOS:
brew install hashcat

# Ubuntu/Debian:
sudo apt-get install hashcat
```

## 密码字典

工具默认使用 `rockyou.txt` 字典文件，这是一个常用的密码字典。你可以下载它：

```bash
# 下载 rockyou.txt
curl -L -o rockyou.txt.gz https://github.com/brannondorsey/naive-hashcat/releases/download/data/rockyou.txt.gz
gunzip rockyou.txt.gz
```

## 注意事项

- 该工具仅用于合法恢复自己的钱包密码
- 对于大型密码字典，恢复过程可能需要较长时间
- GPU 加速（Hashcat 模式）可以显著提高恢复速度