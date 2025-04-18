# Bitcoin Core Installation and Management Makefile
# 使用方法:
#   make install - 安装Bitcoin Core
#   make start - 启动Bitcoin Core守护进程
#   make stop - 停止Bitcoin Core守护进程
#   make status - 检查Bitcoin Core状态
#   make create-wallet NAME=wallet_name - 创建新钱包
#   make unlock NAME=wallet_name PASS=password - 解锁钱包
#   make lock NAME=wallet_name - 锁定钱包
#   make clean - 清理安装文件

# 配置变量
BITCOIND = bitcoind
BITCOIN_CLI = bitcoin-cli
BITCOIN_VERSION = 26.0
# BDB支持的最后一个主要版本
BITCOIN_BDB_VERSION = 22.0
DATADIR = $(HOME)/.bitcoin
CONF_FILE = $(DATADIR)/bitcoin.conf
OS := $(shell uname -s)
ARCH := $(shell uname -m)

# 默认RPC配置
RPC_USER ?= user
RPC_PASSWORD ?= pass
RPC_PORT ?= 8332

# 钱包配置
NAME ?= test
PASS ?= bitcoin
NEW_PASS ?= $(PASS)
DB_PATH ?= $(DATADIR)/wallets/$(NAME)/wallet.dat

# 确定操作系统和架构
ifeq ($(OS),Darwin)
    ifeq ($(ARCH),arm64)
        # macOS arm64 需要使用 x86_64 版本和 Rosetta 2
        PLATFORM = osx-aarch64
        # 对于 22.0 版本，没有 arm64 版本，使用 x86_64 版本
        BDB_PLATFORM = osx64
    else
        PLATFORM = osx-unsigned
        BDB_PLATFORM = osx64
    endif
    INSTALL_CMD = tar -xzf bitcoin-$(BITCOIN_VERSION).tar.gz -C /tmp && cp -r /tmp/bitcoin-$(BITCOIN_VERSION)/bin/* /usr/local/bin/
else ifeq ($(OS),Linux)
    ifeq ($(ARCH),x86_64)
        PLATFORM = linux-x86_64
        BDB_PLATFORM = x86_64-linux-gnu
    else ifeq ($(ARCH),aarch64)
        PLATFORM = linux-aarch64
        BDB_PLATFORM = aarch64-linux-gnu
    else
        PLATFORM = linux
        BDB_PLATFORM = x86_64-linux-gnu
    endif
    INSTALL_CMD = tar -xzf bitcoin-$(BITCOIN_VERSION).tar.gz -C /tmp && sudo install -m 0755 -o root -g root -t /usr/local/bin /tmp/bitcoin-$(BITCOIN_VERSION)/bin/*
else
    $(error 不支持的操作系统: $(OS))
endif

# 目标
.PHONY: all install configure start stop status create-wallet unlock lock clean test encrypt-wallet change-passphrase version install-bdb configure-bdb install-bdb-bin examine-wallet-db create-bdb-wallet uninstall start-debug reindex progress create-bdb-wallet unload-wallet delete-wallet

all: install configure

# 安装Bitcoin Core
install:
	@echo "正在安装Bitcoin Core $(BITCOIN_VERSION) ($(PLATFORM))..."
	@if [ ! -f bitcoin-$(BITCOIN_VERSION).tar.gz ]; then \
		echo "下载Bitcoin Core..."; \
		curl -O https://bitcoincore.org/bin/bitcoin-core-$(BITCOIN_VERSION)/bitcoin-$(BITCOIN_VERSION)-$(PLATFORM).tar.gz -o bitcoin-$(BITCOIN_VERSION).tar.gz; \
	fi
	@$(INSTALL_CMD)
	@which $(BITCOIND) || (echo "安装失败" && exit 1)
	@echo "Bitcoin Core 安装完成! 版本: $$($(BITCOIND) --version | head -n1)"

# 安装支持BDB的Bitcoin Core版本
install-bdb: 
	@echo "======================================================================================"
	@echo "🔍  正在安装支持Berkeley DB的Bitcoin Core $(BITCOIN_BDB_VERSION) 版本..."
	@echo "    操作系统: $(OS), 架构: $(ARCH)"
	@echo "    下载平台: $(BDB_PLATFORM)"
	@echo "======================================================================================"
	
	@# 检查是否已有本地安装包
	@if [ -f "bitcoin-$(BITCOIN_BDB_VERSION)-$(BDB_PLATFORM).tar.gz" ]; then \
		echo "找到本地安装包，跳过下载"; \
		filesize=$$(stat -f%z "bitcoin-$(BITCOIN_BDB_VERSION)-$(BDB_PLATFORM).tar.gz" 2>/dev/null || stat -c%s "bitcoin-$(BITCOIN_BDB_VERSION)-$(BDB_PLATFORM).tar.gz"); \
		if [ $$filesize -lt 20000000 ]; then \
			echo "⚠️ 警告：本地文件大小异常 ($$filesize 字节)，是否继续使用? (y/n)"; \
			read answer; \
			if [ "$$answer" != "y" ]; then \
				echo "将重新下载"; \
				rm -f bitcoin-$(BITCOIN_BDB_VERSION)-$(BDB_PLATFORM).tar.gz; \
			fi; \
		fi; \
	fi
	
	@# 下载文件 (如果需要)
	@if [ ! -f bitcoin-$(BITCOIN_BDB_VERSION)-$(BDB_PLATFORM).tar.gz ]; then \
		echo "下载Bitcoin Core v$(BITCOIN_BDB_VERSION)..."; \
		echo "使用断点续传下载，最多尝试3次..."; \
		for i in 1 2 3; do \
			echo "尝试 $$i/3..."; \
			curl -L -C - --connect-timeout 30 --max-time 600 --retry 3 --retry-delay 5 \
				-o bitcoin-$(BITCOIN_BDB_VERSION)-$(BDB_PLATFORM).tar.gz \
				https://bitcoincore.org/bin/bitcoin-core-$(BITCOIN_BDB_VERSION)/bitcoin-$(BITCOIN_BDB_VERSION)-$(BDB_PLATFORM).tar.gz && break; \
			echo "下载失败，等待5秒后重试..."; \
			sleep 5; \
		done; \
	fi
	
	@# 检查下载结果
	@if [ ! -f bitcoin-$(BITCOIN_BDB_VERSION)-$(BDB_PLATFORM).tar.gz ]; then \
		echo "❌ 下载失败，所有尝试均已失败"; \
		echo "请考虑以下选项:"; \
		echo "1. 检查网络连接并重试"; \
		echo "2. 手动下载: https://bitcoincore.org/bin/bitcoin-core-$(BITCOIN_BDB_VERSION)/bitcoin-$(BITCOIN_BDB_VERSION)-$(BDB_PLATFORM).tar.gz"; \
		echo "3. 使用浏览器下载，然后放到当前目录"; \
		echo "4. 使用 'make install-bdb-bin' 从本地二进制文件安装"; \
		exit 1; \
	fi
	
	@# 检查下载的文件大小
	@filesize=$$(stat -f%z "bitcoin-$(BITCOIN_BDB_VERSION)-$(BDB_PLATFORM).tar.gz" 2>/dev/null || stat -c%s "bitcoin-$(BITCOIN_BDB_VERSION)-$(BDB_PLATFORM).tar.gz")
	@echo "下载的文件大小: $$filesize 字节"
	@if [ $$filesize -lt 20000000 ]; then \
		echo "❌ 错误: 文件过小 ($$filesize 字节)，预期大小应超过20MB"; \
		echo "可能是下载不完整或服务器问题"; \
		echo ""; \
		echo "建议:"; \
		echo "1. 尝试手动下载: https://bitcoincore.org/bin/bitcoin-core-$(BITCOIN_BDB_VERSION)/bitcoin-$(BITCOIN_BDB_VERSION)-$(BDB_PLATFORM).tar.gz"; \
		echo "2. 或下载源码编译: https://bitcoincore.org/bin/bitcoin-core-$(BITCOIN_BDB_VERSION)/bitcoin-$(BITCOIN_BDB_VERSION).tar.gz"; \
		echo "3. 下载后放到当前目录，再执行 make install-bdb"; \
		echo "4. 或者使用 'make install-bdb-bin' 从本地二进制文件安装"; \
		exit 1; \
	fi
	
	@echo "📦 解压文件..."
	@tar -xzf bitcoin-$(BITCOIN_BDB_VERSION)-$(BDB_PLATFORM).tar.gz || { \
		echo "❌ 解压失败，文件可能损坏"; \
		echo "尝试重新下载..."; \
		rm -f bitcoin-$(BITCOIN_BDB_VERSION)-$(BDB_PLATFORM).tar.gz; \
		echo "请重新运行 make install-bdb"; \
		exit 1; \
	}
	
	@# 检查是否成功解压并查找目录
	@if [ ! -d "bitcoin-$(BITCOIN_BDB_VERSION)" ]; then \
		echo "寻找解压后的目录..."; \
		extracted_dir=$$(find . -maxdepth 1 -type d -name "bitcoin-$(BITCOIN_BDB_VERSION)*" | head -1); \
		if [ -z "$$extracted_dir" ]; then \
			echo "❌ 解压失败，未找到 bitcoin-$(BITCOIN_BDB_VERSION) 目录"; \
			echo "尝试查找所有解压的目录:"; \
			find . -maxdepth 1 -type d -name "bitcoin*" -ls; \
			exit 1; \
		else \
			echo "找到目录: $$extracted_dir"; \
			ln -sf $$extracted_dir bitcoin-$(BITCOIN_BDB_VERSION); \
		fi; \
	fi
	
	@echo "🔧 安装二进制文件..."
	@binary_dir=$$(find . -path "*/bitcoin-$(BITCOIN_BDB_VERSION)*/bin" -type d | head -1); \
	if [ -z "$$binary_dir" ]; then \
		echo "⚠️ 警告: 未找到标准的bin目录，尝试在解压目录中查找二进制文件..."; \
		binary_dir=$$(find . -name "bitcoind" -type f -path "*/bitcoin-$(BITCOIN_BDB_VERSION)*" -exec dirname {} \; | head -1); \
	fi; \
	\
	if [ -z "$$binary_dir" ]; then \
		echo "❌ 错误: 无法找到bitcoind二进制文件"; \
		echo "请考虑手动安装或使用 make install-bdb-bin"; \
		exit 1; \
	else \
		echo "📂 找到二进制目录: $$binary_dir"; \
		if [ "$(OS)" = "Darwin" ]; then \
			echo "复制文件到 /usr/local/bin/..."; \
			sudo cp -fv $$binary_dir/* /usr/local/bin/; \
			if [ "$(ARCH)" = "arm64" ]; then \
				echo "⚠️ 在 Apple Silicon Mac 上使用 x86_64 二进制文件，需要 Rosetta 2"; \
				echo "检查 Rosetta 2 是否已安装..."; \
				if ! pgrep -q oahd; then \
					echo "Rosetta 2 似乎未运行，尝试安装..."; \
					softwareupdate --install-rosetta --agree-to-license || echo "请手动安装 Rosetta 2"; \
				else \
					echo "✅ Rosetta 2 已安装"; \
				fi; \
			fi; \
		else \
			echo "安装文件到 /usr/local/bin/..."; \
			sudo install -m 0755 -o root -g root -t /usr/local/bin $$binary_dir/*; \
		fi; \
	fi
	
	@# 确认安装的版本
	@echo "验证安装的版本..."
	@installed_version=$$($(BITCOIND) --version | head -n1); \
	expected_version="Bitcoin Core version v$(BITCOIN_BDB_VERSION)"; \
	if echo "$$installed_version" | grep -q "$(BITCOIN_BDB_VERSION)"; then \
		echo "======================================================================================";\
		echo "✅ Bitcoin Core (BDB支持版本) v$(BITCOIN_BDB_VERSION) 安装成功!"; \
		echo "版本: $$installed_version"; \
		if [ "$(ARCH)" = "arm64" ]; then \
			echo "⚠️ 注意: 在 Apple Silicon (arm64) Mac 上，已安装 x86_64 版本通过 Rosetta 2 运行"; \
		fi; \
		echo ""; \
		echo "🔶 下一步: 请使用 'make configure-bdb' 进行配置，确保正确设置BDB钱包支持"; \
		echo "======================================================================================";\
	else \
		echo "⚠️ 警告: 安装的版本($$installed_version)与预期版本($$expected_version)不匹配"; \
		echo "可能是已有的Bitcoin Core版本没有被覆盖，或者安装过程中出现问题。"; \
		echo ""; \
		echo "尝试手动验证，启动daemon..."; \
		$(BITCOIND) -daemon -version | grep -i version; \
		sleep 2; \
		$(BITCOIN_CLI) stop; \
		echo ""; \
		echo "建议: 先卸载当前版本，然后重新安装"; \
		echo "1. 卸载当前版本: sudo rm /usr/local/bin/bitcoin*"; \
		echo "2. 重新运行: make install-bdb"; \
		exit 1; \
	fi
	
	@# 清理下载文件
	@echo "清理临时文件..."
	@rm -rf bitcoin-$(BITCOIN_BDB_VERSION)-$(BDB_PLATFORM).tar.gz

# 配置Bitcoin Core
configure:
	@echo "配置Bitcoin Core..."
	@mkdir -p $(DATADIR)
	@if [ ! -f $(CONF_FILE) ]; then \
		echo "创建配置文件 $(CONF_FILE)"; \
		echo "server=1" > $(CONF_FILE); \
		echo "rpcuser=$(RPC_USER)" >> $(CONF_FILE); \
		echo "rpcpassword=$(RPC_PASSWORD)" >> $(CONF_FILE); \
		echo "rpcport=$(RPC_PORT)" >> $(CONF_FILE); \
		echo "prune=2000" >> $(CONF_FILE); \
		echo "txindex=1" >> $(CONF_FILE); \
		echo "walletdir=$(DATADIR)/wallets" >> $(CONF_FILE); \
		echo "keypool=1000" >> $(CONF_FILE); \
		echo "fallbackfee=0.0002" >> $(CONF_FILE); \
	else \
		echo "配置文件已存在，跳过"; \
	fi
	@mkdir -p $(DATADIR)/wallets
	@echo "配置完成!"

# 配置支持BDB的Bitcoin Core
configure-bdb:
	@echo "配置支持Berkeley DB的Bitcoin Core..."
	@mkdir -p $(DATADIR)
	@if [ ! -f $(CONF_FILE) ]; then \
		echo "创建配置文件 $(CONF_FILE)"; \
		echo "server=1" > $(CONF_FILE); \
		echo "rpcuser=$(RPC_USER)" >> $(CONF_FILE); \
		echo "rpcpassword=$(RPC_PASSWORD)" >> $(CONF_FILE); \
		echo "rpcport=$(RPC_PORT)" >> $(CONF_FILE); \
		echo "prune=2000" >> $(CONF_FILE); \
		echo "txindex=1" >> $(CONF_FILE); \
		echo "walletdir=$(DATADIR)/wallets" >> $(CONF_FILE); \
		echo "keypool=1000" >> $(CONF_FILE); \
		echo "fallbackfee=0.0002" >> $(CONF_FILE); \
		echo "wallet=wallet.dat" >> $(CONF_FILE); \
		echo "walletrbf=1" >> $(CONF_FILE); \
		echo "# 强制使用BDB钱包" >> $(CONF_FILE); \
		echo "usebdbwallet=1" >> $(CONF_FILE); \
		echo "disablewallet=0" >> $(CONF_FILE); \
	else \
		echo "配置文件已存在，添加BDB钱包支持"; \
		grep -q "usebdbwallet" $(CONF_FILE) || echo "usebdbwallet=1" >> $(CONF_FILE); \
		grep -q "wallet=" $(CONF_FILE) || echo "wallet=wallet.dat" >> $(CONF_FILE); \
	fi
	@mkdir -p $(DATADIR)/wallets
	@echo "BDB钱包配置完成!"
	@echo "注意: 如果从不同版本切换，建议先停止Bitcoin Core再重新启动"

# 启动Bitcoin Core守护进程
start:
	@echo "启动Bitcoin Core守护进程..."
	@if $(BITCOIN_CLI) getblockcount 2>/dev/null; then \
		echo "Bitcoin Core已经在运行"; \
	else \
		echo "启动命令: $(BITCOIND) -daemon"; \
		$(BITCOIND) -daemon -printtoconsole; \
		echo "启动命令已发送，正在等待响应..."; \
		for i in 1 2 3 4 5; do \
			sleep 2; \
			echo "检查 ($$i/5)..."; \
			if $(BITCOIN_CLI) getblockcount 2>/dev/null; then \
				echo "Bitcoin Core成功启动!"; \
				exit 0; \
			fi; \
		done; \
		echo "Bitcoin Core启动可能需要更长时间..."; \
		echo "这是正常的，特别是第一次启动时需要初始化数据库。"; \
		echo "您可以使用以下命令检查日志:"; \
		mkdir -p $(DATADIR); \
		echo "  tail -f $(DATADIR)/debug.log  # 如果日志文件已创建"; \
		echo "或稍后使用以下命令检查状态:"; \
		echo "  make status"; \
	fi

# 停止Bitcoin Core守护进程
stop:
	@echo "停止Bitcoin Core守护进程..."
	@if ! $(BITCOIN_CLI) getblockcount 2>/dev/null; then \
		echo "Bitcoin Core未在运行"; \
	else \
		$(BITCOIN_CLI) stop; \
		echo "停止命令已发送"; \
	fi

# 检查Bitcoin Core状态
status:
	@if $(BITCOIN_CLI) getblockcount 2>/dev/null; then \
		echo "Bitcoin Core正在运行"; \
		echo "区块高度: $$($(BITCOIN_CLI) getblockcount)"; \
		echo "连接数: $$($(BITCOIN_CLI) getconnectioncount)"; \
		echo "======== 钱包列表 ========"; \
		$(BITCOIN_CLI) listwallets; \
	else \
		echo "Bitcoin Core未在运行"; \
	fi

# 查看Bitcoin Core版本信息
version:
	@echo "======== Bitcoin Core 版本信息 ========"
	@if which $(BITCOIND) >/dev/null; then \
		echo "bitcoind 版本:"; \
		$(BITCOIND) --version; \
		echo ""; \
		echo "bitcoin-cli 版本:"; \
		$(BITCOIN_CLI) --version; \
		echo ""; \
		if $(BITCOIN_CLI) getnetworkinfo 2>/dev/null; then \
			echo "========= 网络信息 ========="; \
			$(BITCOIN_CLI) getnetworkinfo | grep -E 'version|subversion|protocolversion'; \
		fi; \
	else \
		echo "Bitcoin Core 未安装或未找到在PATH中"; \
		echo "请先运行 'make install' 安装 Bitcoin Core"; \
	fi

# 创建新钱包
create-wallet:
	@echo "创建钱包: $(NAME)..."
	@$(BITCOIN_CLI) createwallet "$(NAME)" true
	@echo "钱包已创建，现在可以使用 make encrypt-wallet NAME=$(NAME) PASS=your_password 来加密钱包"

# 创建BDB格式钱包
create-bdb-wallet:
	@echo "创建BDB格式钱包: $(NAME)..."
	@# 先删除已存在的钱包
	@$(MAKE) delete-wallet NAME=$(NAME) > /dev/null 2>&1 || true
	@sleep 1
	@# 根据Bitcoin Core版本创建钱包
	@bitcoin_version=$$($(BITCOIN_CLI) --version | grep -o "v[0-9]*\.[0-9]*\.[0-9]*" | head -1 | sed 's/v//'); \
	major_version=$$(echo $$bitcoin_version | cut -d '.' -f 1); \
	echo "检测到Bitcoin Core v$$bitcoin_version (主版本: $$major_version)"; \
	\
	if [ $$major_version -ge 24 ]; then \
		echo "使用v24+兼容命令: $(BITCOIN_CLI) createwallet \"$(NAME)\" false true false \"\" false false false \"bdb\""; \
		$(BITCOIN_CLI) createwallet "$(NAME)" false true false "" false false false "bdb" 2>/dev/null || \
		$(BITCOIN_CLI) createwallet "$(NAME)" false true; \
	else \
		echo "使用v22-v23兼容命令: $(BITCOIN_CLI) createwallet \"$(NAME)\" false true"; \
		$(BITCOIN_CLI) createwallet "$(NAME)" false true; \
	fi
	
	@echo "验证钱包格式和私钥支持..."
	@sleep 2
	@wallet_info=$$($(BITCOIN_CLI) -rpcwallet=$(NAME) getwalletinfo 2>/dev/null); \
	if echo "$$wallet_info" | grep -q "\"format\": \"bdb\""; then \
		echo "✅ 成功创建BDB格式钱包: $(NAME)"; \
		echo "钱包信息:"; \
		echo "$$wallet_info" | grep -E "walletname|format|private_keys_enabled"; \
		echo ""; \
		if echo "$$wallet_info" | grep -q "\"private_keys_enabled\": false"; then \
			echo "⚠️ 警告: 钱包未启用私钥支持，无法加密。"; \
			echo ""; \
			echo "请尝试直接使用bitcoin-cli命令创建钱包:"; \
			echo "  $(BITCOIN_CLI) unloadwallet \"$(NAME)\""; \
			echo "  rm -rf \"$(HOME)/Library/Application Support/Bitcoin/wallets/$(NAME)\""; \
			echo "  $(BITCOIN_CLI) createwallet \"$(NAME)\" false true"; \
		else \
			echo "✅ 私钥支持已启用"; \
			echo "现在可以使用 make encrypt-wallet NAME=$(NAME) PASS=your_password 来加密钱包"; \
		fi; \
	else \
		echo "⚠️ 钱包已创建，但不是BDB格式。"; \
		echo "要创建BDB格式钱包，请参考以下方法:"; \
		echo "1. 使用 make install-bdb 安装v22.0版本"; \
		echo "2. 然后使用 make create-wallet NAME=$(NAME) 创建钱包"; \
	fi

# 加密钱包
encrypt-wallet:
	@echo "加密钱包: $(NAME) 使用密码: $(PASS)..."
	@if $(BITCOIN_CLI) -rpcwallet=$(NAME) encryptwallet "$(PASS)" 2>/dev/null; then \
		echo "成功加密钱包: $(NAME)"; \
		echo "请注意重新启动 Bitcoin Core 以使加密完全生效"; \
		echo "之后可以使用 make unlock NAME=$(NAME) PASS=$(PASS) 来解锁钱包"; \
	else \
		echo "钱包加密失败，可能钱包已加密或不存在"; \
		$(BITCOIN_CLI) -rpcwallet=$(NAME) getwalletinfo 2>/dev/null || echo "钱包 $(NAME) 不存在"; \
	fi

# 更改钱包密码
change-passphrase:
	@echo "更改钱包: $(NAME) 的密码..."
	@if $(BITCOIN_CLI) -rpcwallet=$(NAME) walletpassphrasechange "$(PASS)" "$(NEW_PASS)" 2>/dev/null; then \
		echo "成功更改钱包密码"; \
		echo "新密码为: $(NEW_PASS)"; \
	else \
		echo "更改钱包密码失败，请确认当前密码是否正确"; \
	fi

# 解锁钱包
unlock:
	@echo "解锁钱包: $(NAME) (超时: 36000秒)..."
	@$(BITCOIN_CLI) -rpcwallet=$(NAME) walletpassphrase "$(PASS)" 36000

# 锁定钱包
lock:
	@echo "锁定钱包: $(NAME)..."
	@$(BITCOIN_CLI) -rpcwallet=$(NAME) walletlock

# 查看钱包数据库
examine-wallet-db:
	@echo "查看钱包: $(NAME)..."
	@# 首先检查钱包是否存在和加载
	@if ! $(BITCOIN_CLI) listwallets 2>/dev/null | grep -q "\"$(NAME)\""; then \
		echo "⚠️ 警告: 钱包 $(NAME) 未在Bitcoin Core中加载"; \
		echo "请确保钱包已创建并加载。您可以运行 'make status' 查看已加载的钱包"; \
		exit 1; \
	fi
	
	@# 获取钱包信息
	@echo ""
	@echo "======== 钱包信息 ($(NAME)) ========"
	@if wallet_info=$$($(BITCOIN_CLI) -rpcwallet=$(NAME) getwalletinfo 2>/dev/null); then \
		echo "$$wallet_info" | grep -E "walletname|walletversion|format|balance|txcount|keypoolsize|unlocked_until"; \
		echo ""; \
		echo "钱包格式: $$(echo "$$wallet_info" | grep "format" | sed 's/.*: "\(.*\)",/\1/')"; \
		if echo "$$wallet_info" | grep -q "\"format\": \"bdb\""; then \
			echo "此钱包使用Berkeley DB (BDB)格式"; \
		elif echo "$$wallet_info" | grep -q "\"descriptors\": true"; then \
			echo "此钱包使用描述符(descriptor)格式"; \
		else \
			echo "此钱包使用SQLite格式"; \
		fi; \
		echo ""; \
		echo "钱包是否加密: $$(if echo "$$wallet_info" | grep -q "\"unlocked_until\": 0"; then echo "是 (已锁定)"; \
			elif echo "$$wallet_info" | grep -q "\"unlocked_until\":"; then echo "是 (已解锁)"; else echo "否"; fi)"; \
		echo ""; \
	else \
		echo "无法获取钱包信息"; \
		exit 1; \
	fi
	
	@# 尝试定位钱包文件
	@echo ""
	@echo "======== 尝试定位钱包文件 ========"
	@# 首先尝试默认路径
	@db_files=0; \
	if [ -f "$(DB_PATH)" ]; then \
		echo "找到钱包数据库文件: $(DB_PATH)"; \
		echo "文件大小: $$(stat -f%z "$(DB_PATH)" 2>/dev/null || stat -c%s "$(DB_PATH)") 字节"; \
		file "$(DB_PATH)"; \
		db_files=$$((db_files+1)); \
	fi; \
	\
	# 查找其他可能的路径 \
	wallet_dat_files=$$(find "$(DATADIR)" -name "wallet.dat" -o -name "*$(NAME)*" 2>/dev/null | grep -v "/blocks/"); \
	if [ "$$wallet_dat_files" != "" ]; then \
		echo ""; \
		echo "找到以下与钱包相关的文件:"; \
		for file in $$wallet_dat_files; do \
			echo "$$file"; \
			echo "  - 大小: $$(stat -f%z "$$file" 2>/dev/null || stat -c%s "$$file") 字节"; \
			file "$$file" | sed 's/^/  - /'; \
			db_files=$$((db_files+1)); \
		done; \
	fi; \
	\
	# 在descriptor钱包目录中查找 \
	desc_dir="$(DATADIR)/wallets/$(NAME)"; \
	if [ -d "$$desc_dir" ]; then \
		echo ""; \
		echo "找到钱包目录: $$desc_dir"; \
		echo "包含以下文件:"; \
		ls -la "$$desc_dir" | sed '1d;s/^/  /'; \
		db_files=$$((db_files+1)); \
	fi; \
	\
	# 总结 \
	if [ $$db_files -eq 0 ]; then \
		echo ""; \
		echo "⚠️ 未找到任何钱包文件"; \
		echo "可能的原因:"; \
		echo "1. 钱包仅在内存中存在 (未持久化)"; \
		echo "2. 钱包文件存储在非标准位置"; \
		echo "3. 钱包使用了不同的存储格式"; \
		echo ""; \
		echo "您可以使用 DB_PATH 参数指定钱包文件的具体路径:"; \
		echo "  make examine-wallet-db NAME=$(NAME) DB_PATH=/path/to/wallet.dat"; \
	fi
	
	@# 显示更多钱包信息
	@echo ""
	@echo "======== 钱包地址信息 ========"
	@# 获取最多10个地址
	@$(BITCOIN_CLI) -rpcwallet=$(NAME) listreceivedbyaddress 0 true false | grep -o '"address": "[^"]*"' | head -10 || echo "无法获取地址信息"
	
	@echo ""
	@echo "注意: 若要完整分析钱包文件结构，需要使用专门的工具。本命令仅提供基本信息。"

# 测试钱包
test:
	@echo "测试钱包密码恢复..."
	@python3 wallet_cracker.py --bitcoin-core "$(NAME)" --john --john-path ./john --dictionary rockyou.txt

# 清理安装文件
clean:
	@echo "清理Bitcoin Core安装文件..."
	@rm -f bitcoin-$(BITCOIN_VERSION).tar.gz

# 卸载Bitcoin Core
uninstall:
	@echo "卸载Bitcoin Core..."
	@# 先停止服务
	@if $(BITCOIN_CLI) stop 2>/dev/null; then \
		echo "已停止Bitcoin Core服务"; \
		echo "等待服务完全停止..."; \
		sleep 5; \
	else \
		echo "Bitcoin Core服务未运行"; \
	fi
	
	@# 卸载二进制文件
	@echo "卸载二进制文件..."
	@if [ "$(OS)" = "Darwin" ]; then \
		sudo rm -vf /usr/local/bin/bitcoin* && echo "已移除Bitcoin Core二进制文件"; \
	else \
		sudo rm -vf /usr/local/bin/bitcoin* && echo "已移除Bitcoin Core二进制文件"; \
	fi
	
	@# 检查卸载结果
	@if ! which bitcoind 2>/dev/null; then \
		echo "✅ Bitcoin Core已成功卸载"; \
	else \
		echo "⚠️ 卸载不完全，请手动删除: $(shell which bitcoind)"; \
	fi
	
	@echo ""
	@echo "注意：数据目录 $(DATADIR) 未被删除。"
	@echo "如需彻底卸载包括钱包和配置，请手动删除该目录。"

# 直接从预编译二进制文件安装支持BDB的Bitcoin Core
install-bdb-bin:
	@echo "从本地二进制文件安装支持BDB的Bitcoin Core..."
	@echo "此命令适用于下载安装包失败时的备选方案"
	
	@# 检查二进制文件目录
	@if [ ! -d "bitcoin-bin" ]; then \
		echo "请创建 bitcoin-bin 目录并放入 bitcoind 和 bitcoin-cli 可执行文件"; \
		mkdir -p bitcoin-bin; \
		echo "目录已创建: $(PWD)/bitcoin-bin"; \
		echo "请放入以下文件:"; \
		echo " - bitcoind"; \
		echo " - bitcoin-cli"; \
		echo "然后重新运行 make install-bdb-bin"; \
		exit 1; \
	fi
	
	@# 检查二进制文件是否存在
	@if [ ! -f "bitcoin-bin/bitcoind" ] || [ ! -f "bitcoin-bin/bitcoin-cli" ]; then \
		echo "缺少必要的二进制文件"; \
		[ ! -f "bitcoin-bin/bitcoind" ] && echo "- 缺少 bitcoind"; \
		[ ! -f "bitcoin-bin/bitcoin-cli" ] && echo "- 缺少 bitcoin-cli"; \
		echo "请下载或编译Bitcoin Core v$(BITCOIN_BDB_VERSION)，并将文件放入 bitcoin-bin 目录"; \
		exit 1; \
	fi
	
	@# 检查文件权限
	@chmod +x bitcoin-bin/bitcoind bitcoin-bin/bitcoin-cli
	
	@# 安装文件
	@echo "安装二进制文件..."
	@if [ "$(OS)" = "Darwin" ]; then \
		cp -f bitcoin-bin/bitcoind bitcoin-bin/bitcoin-cli /usr/local/bin/; \
		echo "文件已复制到 /usr/local/bin/"; \
		if [ "$(ARCH)" = "arm64" ]; then \
			echo "⚠️ 在 Apple Silicon Mac 上使用 x86_64 二进制文件，需要 Rosetta 2"; \
			echo "检查 Rosetta 2 是否已安装..."; \
			if ! pgrep -q oahd; then \
				echo "Rosetta 2 似乎未运行，尝试安装..."; \
				softwareupdate --install-rosetta --agree-to-license || echo "请手动安装 Rosetta 2"; \
			else \
				echo "Rosetta 2 已安装"; \
			fi; \
		fi; \
	else \
		sudo install -m 0755 -o root -g root -t /usr/local/bin bitcoin-bin/bitcoind bitcoin-bin/bitcoin-cli; \
		echo "文件已安装到 /usr/local/bin/"; \
	fi
	
	@# 检查安装结果
	@if which $(BITCOIND) >/dev/null; then \
		echo "✅ Bitcoin Core (BDB支持版本) 安装完成!"; \
		echo "版本: $$($(BITCOIND) --version | head -n1)"; \
		if [ "$(ARCH)" = "arm64" ]; then \
			echo "注意: 在 Apple Silicon Mac 上，可能需要通过 Rosetta 2 运行"; \
		fi; \
		echo "请使用 'make configure-bdb' 进行配置，确保正确设置BDB钱包支持"; \
	else \
		echo "❌ 安装失败，未能找到 $(BITCOIND)"; \
		echo "请检查安装路径和权限"; \
		exit 1; \
	fi

# 启动Bitcoin Core守护进程并监视日志
start-debug:
	@echo "启动Bitcoin Core守护进程并实时显示日志..."
	@if $(BITCOIN_CLI) getblockcount 2>/dev/null; then \
		echo "Bitcoin Core已经在运行，直接显示日志:"; \
		tail -f $(DATADIR)/debug.log 2>/dev/null || echo "日志文件还未创建"; \
	else \
		echo "启动Bitcoin Core..."; \
		$(BITCOIND) -daemon; \
		echo "等待启动..."; \
		sleep 3; \
		echo "显示日志输出 (按Ctrl+C退出日志查看，不会停止Bitcoin Core):"; \
		mkdir -p $(DATADIR); \
		(tail -f $(DATADIR)/debug.log 2>/dev/null || \
		 (echo "等待日志文件创建..." && while [ ! -f $(DATADIR)/debug.log ]; do sleep 1; done && tail -f $(DATADIR)/debug.log)); \
	fi

# 重建区块链索引
reindex:
	@echo "启动Bitcoin Core并在后台重建区块链索引..."
	@if $(BITCOIN_CLI) getblockcount 2>/dev/null; then \
		echo "Bitcoin Core已经在运行，请先停止:"; \
		echo "  make stop"; \
		exit 1; \
	else \
		echo "启动Bitcoin Core并重建索引 (这可能需要几个小时到几天时间)..."; \
		$(BITCOIND) -daemon -reindex -prune=2000; \
		echo "等待启动..."; \
		sleep 5; \
		echo "重建索引已在后台开始，您可以使用以下命令检查进度:"; \
		echo "  make progress"; \
		echo ""; \
		echo "重建完成后，您可以创建BDB格式钱包:"; \
		echo "  make create-bdb-wallet NAME=bdb_wallet"; \
	fi

# 查看区块链同步进度
progress:
	@echo "查看Bitcoin Core同步状态..."
	@if ! $(BITCOIN_CLI) getblockchaininfo 2>/dev/null; then \
		echo "Bitcoin Core未在运行"; \
		exit 1; \
	fi
	@echo ""
	@echo "========== 区块链同步状态 =========="
	@$(BITCOIN_CLI) getblockchaininfo | grep -E '("blocks"|"headers"|"verificationprogress"|"initialblockdownload"|"pruned"|"size_on_disk")' | sed 's/,//g'
	@progress=$$($(BITCOIN_CLI) getblockchaininfo | grep "verificationprogress" | awk '{print $$2}' | sed 's/,//g'); \
	max_height=$$($(BITCOIN_CLI) getblockchaininfo | grep "headers" | awk '{print $$2}' | sed 's/,//g'); \
	current_height=$$($(BITCOIN_CLI) getblockchaininfo | grep "blocks" | awk '{print $$2}' | sed 's/,//g'); \
	percentage=$$(echo "$$progress * 100" | bc -l | awk '{printf "%.2f", $$1}'); \
	echo "进度: 已同步 $$current_height/$$max_height 个区块 ($$percentage%)"; \
	remaining=$$(echo "(1 - $$progress) * 100" | bc -l | awk '{printf "%.2f", $$1}'); \
	if [ "$$(echo "$$progress < 0.9999" | bc -l)" -eq 1 ]; then \
		echo "预计剩余时间: 无法准确估计，取决于硬件性能和网络状况"; \
		echo "目前仍需同步约 $$remaining% 的区块链数据"; \
		echo ""; \
		echo "提示: 这个过程可能需要几个小时甚至几天。您可以定期使用 'make progress' 检查进度。"; \
		echo "重建完成后，可以使用 'make status' 确认Bitcoin Core正常运行。"; \
	else \
		echo "同步已基本完成 ($$percentage%)"; \
		echo ""; \
		echo "Bitcoin Core已准备就绪，可以开始创建和使用钱包。"; \
	fi

# 创建与卸载钱包辅助命令
unload-wallet:
	@echo "卸载钱包: $(NAME)..."
	@$(BITCOIN_CLI) unloadwallet "$(NAME)" 2>/dev/null && echo "钱包已卸载" || echo "卸载失败或钱包不存在"

delete-wallet:
	@echo "删除钱包: $(NAME)..."
	@echo "尝试卸载钱包..."
	@$(BITCOIN_CLI) unloadwallet "$(NAME)" 2>/dev/null || true
	@sleep 1
	@# 检查不同可能的路径
	@echo "尝试删除钱包文件..."
	@std_path="$(DATADIR)/wallets/$(NAME)"; \
	alt_path="$(HOME)/Library/Application Support/Bitcoin/wallets/$(NAME)"; \
	\
	if [ -d "$$std_path" ]; then \
		echo "标准路径: $$std_path"; \
		rm -rf "$$std_path" && echo "已删除标准路径下的钱包文件" || echo "无法删除钱包文件"; \
	elif [ -d "$$alt_path" ]; then \
		echo "备用路径: $$alt_path"; \
		rm -rf "$$alt_path" && echo "已删除备用路径下的钱包文件" || echo "无法删除钱包文件"; \
	else \
		echo "找不到钱包目录"; \
		find $(HOME) -name "$(NAME)" -type d -path "*/Bitcoin/wallets/*" 2>/dev/null | \
		while read dir; do \
			echo "找到潜在钱包目录: $$dir"; \
			rm -rf "$$dir" && echo "已删除" || echo "无法删除"; \
		done; \
	fi
	@echo "钱包删除操作完成。现在可以使用 'make create-bdb-wallet NAME=$(NAME)' 重新创建钱包。"

# 帮助信息
help:
	@echo "Bitcoin Core 安装与管理 Makefile"
	@echo ""
	@echo "目标:"
	@echo "  install         安装最新版Bitcoin Core $(BITCOIN_VERSION)"
	@echo "  install-bdb     安装支持Berkeley DB的Bitcoin Core v$(BITCOIN_BDB_VERSION)"
	@echo "  install-bdb-bin 从本地二进制文件安装支持BDB的Bitcoin Core"
	@echo "  uninstall       卸载Bitcoin Core"
	@echo "  configure       配置最新版Bitcoin Core"
	@echo "  configure-bdb   配置支持BDB钱包的Bitcoin Core"
	@echo "  start           启动Bitcoin Core守护进程"
	@echo "  start-debug     启动Bitcoin Core并实时显示日志输出"
	@echo "  reindex         启动Bitcoin Core并重建区块链索引(修复损坏的区块数据库)"
	@echo "  progress        显示区块链同步进度"
	@echo "  stop            停止Bitcoin Core守护进程"
	@echo "  status          检查Bitcoin Core状态"
	@echo "  version         显示Bitcoin Core版本信息"
	@echo "  create-wallet   创建新钱包 (参数: NAME=wallet_name)"
	@echo "  create-bdb-wallet 创建BDB格式钱包 (参数: NAME=wallet_name) - 密码恢复工具需要此格式"
	@echo "  encrypt-wallet  加密钱包 (参数: NAME=wallet_name PASS=password)"
	@echo "  unlock          解锁钱包 (参数: NAME=wallet_name PASS=password)"
	@echo "  lock            锁定钱包 (参数: NAME=wallet_name)"
	@echo "  examine-wallet-db 查看钱包信息和数据库文件 (参数: NAME=wallet_name [DB_PATH=路径])"
	@echo "  change-passphrase 更改钱包密码 (参数: NAME=wallet_name PASS=old_password NEW_PASS=new_password)"
	@echo "  test            测试钱包密码恢复工具"
	@echo "  clean           清理安装文件"
	@echo "  unload-wallet    卸载钱包 (参数: NAME=wallet_name)"
	@echo "  delete-wallet    删除钱包 (参数: NAME=wallet_name)"
	@echo ""
	@echo "BDB钱包使用示例:"
	@echo "  make install-bdb        # 安装支持BDB的Bitcoin Core v$(BITCOIN_BDB_VERSION)"
	@echo "    或者"
	@echo "  make install-bdb-bin    # 从本地二进制文件安装"
	@echo "  make configure-bdb      # 配置使用BDB钱包"
	@echo "  make start              # 启动Bitcoin Core"
	@echo "  make create-bdb-wallet NAME=bdb_wallet  # 创建BDB格式钱包"
	@echo "  make encrypt-wallet NAME=bdb_wallet PASS=password  # 加密BDB钱包"
	@echo "  make unload-wallet NAME=bdb_wallet  # 卸载BDB钱包"
	@echo "  make delete-wallet NAME=bdb_wallet  # 删除BDB钱包" 