"""
轻量级应用指标收集器 (无外部依赖)
在内存中追踪请求计数、错误计数、响应时间分布等关键运维指标。
"""

import time
import threading
from collections import defaultdict
from datetime import datetime


class MetricsCollector:
    """线程安全的内存指标收集器"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._data_lock = threading.Lock()
        
        # 请求计数
        self.request_count = 0
        self.error_count = defaultdict(int)  # {error_type: count}
        
        # 响应时间 (保留最近 500 条)
        self.response_times = []
        self._max_response_history = 500
        
        # 端点级别计数
        self.endpoint_counts = defaultdict(int)  # {path: count}
        
        # Agent 节点耗时
        self.node_times = defaultdict(list)  # {node_name: [ms, ...]}
        
        # 启动时间
        self.start_time = datetime.now()
    
    def record_request(self, path: str, duration_ms: float, success: bool = True):
        """记录一次 API 请求"""
        with self._data_lock:
            self.request_count += 1
            self.endpoint_counts[path] += 1
            self.response_times.append({
                "ts": datetime.now().isoformat(),
                "path": path,
                "ms": round(duration_ms, 1),
                "ok": success,
            })
            # 滑窗裁剪
            if len(self.response_times) > self._max_response_history:
                self.response_times = self.response_times[-self._max_response_history:]
    
    def record_error(self, error_type: str):
        """记录一次错误"""
        with self._data_lock:
            self.error_count[error_type] += 1
    
    def record_node_time(self, node_name: str, duration_ms: float):
        """记录 Agent 某节点耗时"""
        with self._data_lock:
            self.node_times[node_name].append(round(duration_ms, 1))
            # 每个节点最多保留 200 条
            if len(self.node_times[node_name]) > 200:
                self.node_times[node_name] = self.node_times[node_name][-200:]
    
    def get_snapshot(self) -> dict:
        """返回当前指标快照"""
        with self._data_lock:
            uptime = (datetime.now() - self.start_time).total_seconds()
            
            # 计算响应时间统计
            times = [r["ms"] for r in self.response_times]
            avg_ms = round(sum(times) / len(times), 1) if times else 0
            p95_ms = round(sorted(times)[int(len(times) * 0.95)] if times else 0, 1)
            max_ms = round(max(times) if times else 0, 1)
            
            total_errors = sum(self.error_count.values())
            error_rate = round(total_errors / self.request_count * 100, 2) if self.request_count > 0 else 0
            
            # 节点平均耗时
            node_avg = {}
            for name, durations in self.node_times.items():
                node_avg[name] = round(sum(durations) / len(durations), 1) if durations else 0
            
            return {
                "uptime_seconds": round(uptime, 1),
                "total_requests": self.request_count,
                "total_errors": total_errors,
                "error_rate_pct": error_rate,
                "errors_by_type": dict(self.error_count),
                "response_time": {
                    "avg_ms": avg_ms,
                    "p95_ms": p95_ms,
                    "max_ms": max_ms,
                },
                "endpoint_counts": dict(self.endpoint_counts),
                "node_avg_ms": node_avg,
                "recent_requests": self.response_times[-20:],  # 最近 20 条
            }


# 全局单例
metrics = MetricsCollector()
