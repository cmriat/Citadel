"""Worker 后台服务管理"""

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Callable
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class WorkerService:
    """Worker 后台服务

    管理 RedisWorker 的后台运行，支持多线程并发处理。
    """

    def __init__(self):
        self._running = False
        self._executor: Optional[ThreadPoolExecutor] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # 状态信息
        self._num_workers: int = 0
        self._active_workers: int = 0
        self._started_at: Optional[datetime] = None

        # 日志回调
        self._log_callbacks: List[Callable[[str], None]] = []

        # 配置
        self._config: Dict[str, Any] = {}

        # Worker 实例引用
        self._worker_instance = None

    def add_log_callback(self, callback: Callable[[str], None]):
        """添加日志回调"""
        self._log_callbacks.append(callback)

    def remove_log_callback(self, callback: Callable[[str], None]):
        """移除日志回调"""
        if callback in self._log_callbacks:
            self._log_callbacks.remove(callback)

    def _emit_log(self, message: str):
        """发送日志到所有回调"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"{timestamp} [Worker] {message}"
        logger.info(message)
        for callback in self._log_callbacks:
            try:
                callback(log_entry)
            except Exception as e:
                logger.error(f"Log callback error: {e}")

    def set_config(self, config: Dict[str, Any]):
        """设置配置"""
        self._config = config

    def start(self, num_workers: int = 4):
        """启动 Worker 服务

        Args:
            num_workers: Worker 数量
        """
        with self._lock:
            if self._running:
                self._emit_log("⚠ Workers already running")
                return False

            self._running = True
            self._num_workers = num_workers
            self._started_at = datetime.now(timezone.utc)
            self._stop_event.clear()

            # 创建线程池
            self._executor = ThreadPoolExecutor(max_workers=num_workers)

            # 启动 worker 线程
            for i in range(num_workers):
                self._executor.submit(self._worker_loop, i)
                self._active_workers += 1

            self._emit_log(f"▶ Started {num_workers} workers")
            return True

    def stop(self):
        """停止 Worker 服务"""
        with self._lock:
            if not self._running:
                return False

            self._emit_log("■ Stopping workers...")
            self._stop_event.set()
            self._running = False

            if self._executor:
                self._executor.shutdown(wait=True, cancel_futures=True)
                self._executor = None

            self._active_workers = 0
            self._emit_log("■ Workers stopped")
            return True

    def _worker_loop(self, worker_id: int):
        """单个 Worker 的工作循环"""
        self._emit_log(f"Worker-{worker_id} started")

        try:
            import tempfile
            import yaml
            import redis
            from lerobot_converter.redis.worker import RedisWorker
            from lerobot_converter.redis.task_queue import TaskQueue

            # 获取 strategy 并确保是字符串
            strategy = self._config.get("conversion", {}).get("strategy", "nearest")
            if hasattr(strategy, 'value'):
                strategy = strategy.value

            # 构建 storage config 格式 (与 storage.yaml 结构一致)
            storage_config = {
                "bos": {
                    "endpoint": str(self._config.get("bos", {}).get("endpoint", "")),
                    "bucket": str(self._config.get("bos", {}).get("bucket", "")),
                    "region": str(self._config.get("bos", {}).get("region", "bj")),
                    "access_key": str(self._config.get("bos", {}).get("access_key", "")),
                    "secret_key": str(self._config.get("bos", {}).get("secret_key", "")),
                    "paths": {
                        "raw_data": str(self._config.get("paths", {}).get("raw_data", "")),
                        "converted": str(self._config.get("paths", {}).get("converted", "")),
                    },
                    "task_name": str(self._config.get("paths", {}).get("task_name", "")),
                    "download": {
                        "temp_dir": "/tmp/lerobot_bos",
                        "concurrent": 4,
                        "retry": 3,
                        "retry_delay": 5,
                    },
                    "upload": {
                        "concurrent": 4,
                        "retry": 3,
                        "retry_delay": 5,
                        "cleanup_local": True,
                        "overwrite": False,
                    },
                },
                "redis": {
                    "host": str(self._config.get("redis", {}).get("host", "localhost")),
                    "port": int(self._config.get("redis", {}).get("port", 6379)),
                    "db": int(self._config.get("redis", {}).get("db", 0)),
                    "password": self._config.get("redis", {}).get("password"),
                    "queue_name": "lerobot:episodes",
                },
                "conversion": {
                    "strategy": str(strategy),
                    "output_fps": int(self._config.get("conversion", {}).get("fps", 30)),
                },
                "output": {
                    "pattern": "./lerobot_datasets/{source}/{episode_id}_{strategy}",
                    "bos_pattern": f"lerobot_dataset_{self._config.get('paths', {}).get('task_name', 'task')}_{strategy}",
                },
            }

            # 写入临时配置文件
            temp_config_file = tempfile.NamedTemporaryFile(
                mode='w', suffix='.yaml', delete=False
            )
            yaml.dump(storage_config, temp_config_file, default_flow_style=False)
            temp_config_file.close()

            # 初始化 Redis 客户端和 TaskQueue
            redis_config = storage_config.get("redis", {})
            redis_client = redis.Redis(
                host=redis_config.get("host", "localhost"),
                port=redis_config.get("port", 6379),
                db=redis_config.get("db", 0),
                password=redis_config.get("password"),
                decode_responses=True
            )
            task_queue = TaskQueue(redis_client, queue_name="lerobot:episodes")

            # 初始化 RedisWorker
            worker = RedisWorker(
                output_pattern=storage_config["output"]["pattern"],
                config_template=f"config/strategies/{strategy}.yaml",
                default_strategy=str(strategy),
                bos_config_path=temp_config_file.name
            )

            self._emit_log(f"Worker-{worker_id} initialized successfully")

            while not self._stop_event.is_set():
                try:
                    # 尝试获取任务
                    task_data = task_queue.get(timeout=2)

                    if task_data:
                        episode_id = task_data.get("episode_id", "unknown")
                        self._emit_log(f"Worker-{worker_id} processing {episode_id}")

                        try:
                            worker.process_task(task_data, task_queue)
                            self._emit_log(f"Worker-{worker_id} ✓ completed {episode_id}")
                        except Exception as e:
                            self._emit_log(f"Worker-{worker_id} ✗ failed {episode_id}: {e}")
                            logger.exception(f"Worker-{worker_id} task error")

                except Exception as e:
                    if not self._stop_event.is_set():
                        logger.error(f"Worker-{worker_id} loop error: {e}")
                        time.sleep(1)

        except Exception as e:
            self._emit_log(f"Worker-{worker_id} initialization error: {e}")
            logger.exception(f"Worker-{worker_id} error")

        finally:
            with self._lock:
                self._active_workers = max(0, self._active_workers - 1)
            self._emit_log(f"Worker-{worker_id} stopped")

    def get_status(self) -> Dict[str, Any]:
        """获取 Worker 状态"""
        return {
            "running": self._running,
            "num_workers": self._num_workers,
            "active_workers": self._active_workers,
            "started_at": self._started_at.isoformat() if self._started_at else None
        }


# 全局单例
worker_service = WorkerService()
