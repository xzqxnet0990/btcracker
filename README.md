# Bitcoin Core 安装与钱包密码恢复工具

<h4 align="center">
<p>
<a href="https://github.com/xzqxnet0990/btcracker/tree/main/README.md">简体中文</a> |
<a href="https://github.com/xzqxnet0990/btcracker/tree/main/README_EN.md">English</a> 
</p>
</h4>

这个项目提供了用于安装和管理 Bitcoin Core 的 Makefile，以及一个强大的钱包密码恢复工具 `wallet_cracker.py`。

## 功能特点

- 自动化安装和配置 Bitcoin Core
- 钱包创建、解锁和锁定功能
- 钱包信息和数据库文件查看功能
- 支持导入钱包文件功能（单个或批量导入）
- 支持多种密码恢复方法：
  - 字典攻击
  - 暴力破解
  - John the Ripper 集成
  - Hashcat 集成（GPU 加速）
- Hashcat 断点续传功能，可随时中断和恢复破解进度

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

# 查看钱包信息和数据库文件
make examine-wallet-db NAME=mywallet

# 停止 Bitcoin Core 守护进程
make stop
```

### 导入已有钱包

您可以导入现有的Bitcoin钱包文件到Bitcoin Core中，然后使用btcracker工具尝试恢复密码：

```bash
# 导入单个钱包文件
make import-wallet SRC=wallet/wallet1.001.dat NAME=wallet1_001

# 批量导入wallet目录下的所有钱包文件
make import-all-wallets
```

**导入钱包说明：**
- `import-wallet` 命令需要指定源文件路径(`SRC`)和目标钱包名称(`NAME`)
- `import-all-wallets` 命令会自动将wallet目录下所有.dat文件导入，并以"imported_文件名"方式命名
- 导入完成后，可以使用`make status`查看已导入的钱包列表
- 如果Bitcoin Core未运行，请先使用`make start`启动，然后再导入钱包
- 导入的钱包可以直接使用btcracker工具进行破解：
  ```bash
  python btcracker_run.py --bitcoin-core imported_wallet1.001 --hashcat -d wordlist.txt
  ```

### 创建和加密钱包

Bitcoin Core 钱包的创建和加密是保障资金安全的重要步骤。以下是详细的操作流程：

```bash
# 1. 创建新钱包
make create-wallet NAME=my_new_wallet

# 2. 加密钱包(设置密码)
make encrypt-wallet NAME=my_new_wallet PASS=my_secure_password

# 3. 更改钱包密码(如果需要)
make change-passphrase NAME=my_new_wallet PASS=old_password NEW_PASS=new_password

# 4. 临时解锁钱包(进行交易等操作)
make unlock NAME=my_new_wallet PASS=my_secure_password

# 5. 操作完成后锁定钱包
make lock NAME=my_new_wallet
```

**钱包安全建议：**
- 使用强密码 (至少16位，包含大小写字母、数字和特殊字符)
- 不要在多处使用相同的密码
- 安全备份密码，考虑使用密码管理器
- 定期更改密码增强安全性
- 完成操作后务必锁定钱包

**警告：** 一旦忘记密码，唯一恢复方式是使用本工具破解，但可能需要大量计算资源。保管好您的密码和钱包备份。

### 创建BDB格式钱包

较新版本的Bitcoin Core（v24及以上）默认使用SQLite格式创建钱包，而本项目中的密码恢复工具主要针对传统的BDB格式钱包。要创建BDB格式的钱包，请使用专门的命令：

```bash
# 创建BDB格式钱包
make create-bdb-wallet NAME=bdb_wallet

# 如果上述命令不支持，请先安装支持BDB的Bitcoin Core版本
make install-bdb

# 配置BDB钱包支持
make configure-bdb

# 然后创建钱包
make create-wallet NAME=bdb_wallet
```

**注意：** 
- 在v24及以上版本中，可能需要安装v22.0版本以获得完整的BDB钱包支持
- BDB格式钱包与密码恢复工具更加兼容
- 请使用`make examine-wallet-db NAME=钱包名称`命令验证钱包格式为"bdb"

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

### 使用 btcracker_run.py 启动器

为了简化操作，项目提供了 `btcracker_run.py` 启动脚本，可以在不安装 btcracker 的情况下直接使用：

```bash
# 使用启动脚本破解 Bitcoin Core 钱包
python btcracker_run.py --bitcoin-core "mywallet" --dictionary rockyou.txt

# 使用启动脚本搭配 Hashcat 加速
python btcracker_run.py --bitcoin-core "mywallet" --hashcat --dictionary rockyou.txt

# 使用启动脚本进行暴力破解
python btcracker_run.py --bitcoin-core "mywallet" --brute-force -m 4 -M 8
```

`btcracker_run.py` 启动器支持与 wallet_cracker.py 完全相同的命令行参数，这种方式无需安装，只需直接运行即可，更适合临时使用或测试场景。

### 区块链同步问题处理

当您首次设置Bitcoin Core时，节点需要下载并验证整个区块链。在这个过程中，您可能会遇到以下错误信息：

```
(standard_in) 1: syntax error
进度: 已同步 X/Y 个区块 (%)
(standard_in) 1: syntax error
/bin/sh: 7: [: Illegal number: 
同步已基本完成 (%)
```

**这些错误解释：**
- 这些只是进度显示脚本的错误，不影响区块链实际的同步过程
- `syntax error` 通常是由于脚本中使用 `bc` 命令计算百分比时出现问题
- `Illegal number` 错误发生在解析非数字内容时

**解决方案：**
1. 继续让区块链同步完成，这些错误不会影响同步过程
2. 使用以下命令查看真实的同步状态：
   ```bash
   bitcoin-cli getblockchaininfo | grep -E "blocks|headers|verificationprogress"
   ```
3. 完整的同步过程可能需要几天到几周时间，取决于您的网络和硬件性能

**优化同步速度的建议：**
- 使用高速互联网连接
- 确保有足够的磁盘空间（至少需要500GB）
- 考虑在bitcoin.conf中添加更多连接：
  ```
  maxconnections=16
  dbcache=4096  # 如果您有足够的RAM
  ```

请注意，在完成区块链同步之前，某些钱包功能可能无法正常工作。破解加密钱包不需要完整的区块链，但与钱包交互的功能可能会受到限制。

### Hashcat 断点续传功能

Hashcat 模式支持断点续传功能，可以在长时间破解过程中随时中断并在稍后恢复：

```bash
# 开始 Hashcat 破解
python3 wallet_cracker.py --bitcoin-core "mywallet" --hashcat --dictionary rockyou.txt

# 按 Ctrl+C 随时中断，进度会自动保存
# ...

# 自动恢复破解进度：只需再次运行完全相同的命令
python3 wallet_cracker.py --bitcoin-core "mywallet" --hashcat --dictionary rockyou.txt
# 系统会自动检测到之前的会话并从中断处继续

# 如果需要重新开始而不是恢复，可以使用 --no-resume 参数
python3 wallet_cracker.py --bitcoin-core "mywallet" --hashcat --dictionary rockyou.txt --no-resume
```

所有会话信息都保存在 `hashcat_sessions` 目录中，每个攻击会创建唯一的会话文件。无需手动管理断点，程序会自动处理恢复过程。

### 查看钱包信息和数据库文件

新增的`examine-wallet-db`命令可以查看钱包的详细信息和关联的数据库文件：

```bash
# 基本用法
make examine-wallet-db NAME=mywallet

# 指定钱包数据库路径(如果知道确切路径)
make examine-wallet-db NAME=mywallet DB_PATH=/path/to/wallet.dat

# 查看导入的钱包信息
make examine-wallet-db NAME=imported_wallet1.001
```

此命令会显示：
- 钱包基本信息（名称、版本、格式、余额等）
- 钱包格式（BDB、描述符或SQLite）
- 钱包加密状态（是否加密、是否锁定）
- 钱包相关文件的位置和信息
- 钱包中的地址信息

## 安装要求

- Python 3.9
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
- 断点续传功能让破解过程更加便捷，即使运行中断，只需重新运行相同命令即可自动继续，避免丢失进度