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

# 确定操作系统和架构
ifeq ($(OS),Darwin)
    ifeq ($(ARCH),arm64)
        PLATFORM = osx-aarch64
    else
        PLATFORM = osx-unsigned
    endif
    INSTALL_CMD = tar -xzf bitcoin-$(BITCOIN_VERSION).tar.gz -C /tmp && cp -r /tmp/bitcoin-$(BITCOIN_VERSION)/bin/* /usr/local/bin/
else ifeq ($(OS),Linux)
    ifeq ($(ARCH),x86_64)
        PLATFORM = linux-x86_64
    else ifeq ($(ARCH),aarch64)
        PLATFORM = linux-aarch64
    else
        PLATFORM = linux
    endif
    INSTALL_CMD = tar -xzf bitcoin-$(BITCOIN_VERSION).tar.gz -C /tmp && sudo install -m 0755 -o root -g root -t /usr/local/bin /tmp/bitcoin-$(BITCOIN_VERSION)/bin/*
else
    $(error 不支持的操作系统: $(OS))
endif

# 目标
.PHONY: all install configure start stop status create-wallet unlock lock clean test

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

# 启动Bitcoin Core守护进程
start:
	@echo "启动Bitcoin Core守护进程..."
	@if $(BITCOIN_CLI) getblockcount 2>/dev/null; then \
		echo "Bitcoin Core已经在运行"; \
	else \
		$(BITCOIND) -daemon; \
		echo "启动命令已发送，正在等待响应..."; \
		sleep 5; \
		if $(BITCOIN_CLI) getblockcount 2>/dev/null; then \
			echo "Bitcoin Core成功启动!"; \
		else \
			echo "Bitcoin Core可能未成功启动，请检查日志: $(DATADIR)/debug.log"; \
		fi; \
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

# 创建新钱包
create-wallet:
	@echo "创建钱包: $(NAME)..."
	@$(BITCOIN_CLI) createwallet "$(NAME)" true
	@echo "钱包已创建，现在可以使用 make unlock NAME=$(NAME) PASS=your_password 来设置密码"

# 解锁钱包
unlock:
	@echo "解锁钱包: $(NAME) (超时: 36000秒)..."
	@$(BITCOIN_CLI) -rpcwallet=$(NAME) walletpassphrase "$(PASS)" 36000

# 锁定钱包
lock:
	@echo "锁定钱包: $(NAME)..."
	@$(BITCOIN_CLI) -rpcwallet=$(NAME) walletlock

# 测试钱包
test:
	@echo "测试钱包密码恢复..."
	@python3 wallet_cracker.py --bitcoin-core "$(NAME)" --john --john-path ./john --dictionary rockyou.txt

# 清理安装文件
clean:
	@echo "清理Bitcoin Core安装文件..."
	@rm -f bitcoin-$(BITCOIN_VERSION).tar.gz

# 帮助信息
help:
	@echo "Bitcoin Core 安装与管理 Makefile"
	@echo ""
	@echo "目标:"
	@echo "  install         安装Bitcoin Core $(BITCOIN_VERSION)"
	@echo "  configure       配置Bitcoin Core"
	@echo "  start           启动Bitcoin Core守护进程"
	@echo "  stop            停止Bitcoin Core守护进程"
	@echo "  status          检查Bitcoin Core状态"
	@echo "  create-wallet   创建新钱包 (参数: NAME=wallet_name)"
	@echo "  unlock          解锁钱包 (参数: NAME=wallet_name PASS=password)"
	@echo "  lock            锁定钱包 (参数: NAME=wallet_name)"
	@echo "  test            测试钱包密码恢复工具"
	@echo "  clean           清理安装文件"
	@echo ""
	@echo "示例:"
	@echo "  make create-wallet NAME=mywallet"
	@echo "  make unlock NAME=mywallet PASS=mypassword" 