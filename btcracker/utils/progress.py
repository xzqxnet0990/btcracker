import time

# 添加进度条支持
try:
    from tqdm import tqdm
except ImportError:
    print("提示: 安装 tqdm 包可以显示进度条: pip install tqdm")
    # 使用简单的替代进度显示
    class tqdm:
        def __init__(self, iterable=None, total=None, desc=None, unit=None, **kwargs):
            self.iterable = iterable
            self.total = total or (len(iterable) if iterable is not None else None)
            self.desc = desc or ""
            self.n = 0
            self.last_print = 0
            
        def update(self, n=1):
            self.n += n
            current_time = time.time()
            # 每秒最多更新一次进度
            if current_time - self.last_print >= 1:
                if self.total:
                    print(f"\r{self.desc}: {self.n}/{self.total} ({self.n/self.total*100:.1f}%)", end="", flush=True)
                else:
                    print(f"\r{self.desc}: {self.n}", end="", flush=True)
                self.last_print = current_time
                
        def close(self):
            print("")
            
        def __iter__(self):
            self.iter = iter(self.iterable)
            return self
            
        def __next__(self):
            try:
                obj = next(self.iter)
                self.update(1)
                return obj
            except StopIteration:
                self.close()
                raise
                
        def __enter__(self):
            return self
            
        def __exit__(self, exc_type, exc_val, exc_tb):
            self.close()
            
        def set_description(self, desc):
            self.desc = desc 