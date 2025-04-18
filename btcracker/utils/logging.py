# 设置日志级别 (0=最少日志, 1=标准日志, 2=详细日志)
LOG_LEVEL = 1

def log(message, level=1):
    """根据设置的日志级别打印消息"""
    if level <= LOG_LEVEL:
        print(message, flush=True)

def set_log_level(level):
    """设置全局日志级别"""
    global LOG_LEVEL
    LOG_LEVEL = level 