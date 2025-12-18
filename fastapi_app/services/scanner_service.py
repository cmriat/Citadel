"""Scanner 后台服务管理"""

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Callable

logger = logging.getLogger(__name__)


class ScannerService:
    """Scanner 后台服务

    管理 EpisodeScanner 的后台运行，支持持续扫描和单次扫描模式。
    """

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # 状态信息
        self._mode: Optional[str] = None
        self._interval: int = 120
        self._started_at: Optional[datetime] = None
        self._last_scan_at: Optional[datetime] = None
        self._next_scan_at: Optional[datetime] = None

        # 统计信息
        self._stats = {
            "found": 0,
            "ready": 0,
            "published": 0,
            "skipped": 0
        }

        # 日志回调
        self._log_callbacks: List[Callable[[str], None]] = []

        # BOS 和 Redis 客户端（延迟初始化）
        self._bos_client = None
        self._task_queue = None
        self._scanner = None
        self._config: Dict[str, Any] = {}

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
        log_entry = f"{timestamp} [Scanner] {message}"
        logger.info(message)
        for callback in self._log_callbacks:
            try:
                callback(log_entry)
            except Exception as e:
                logger.error(f"Log callback error: {e}")

    def set_config(self, config: Dict[str, Any]):
        """设置配置"""
        self._config = config

    def _init_clients(self):
        """初始化 BOS 和 Redis 客户端"""
        if not self._config:
            raise ValueError("Config not set")

        import tempfile
        import yaml
        from lerobot_converter.bos.client import BosClient
        from lerobot_converter.redis.task_queue import TaskQueue
        from lerobot_converter.bos.scanner import EpisodeScanner

        # 获取 strategy 并确保是字符串
        strategy = self._config.get("conversion", {}).get("strategy", "nearest")
        if hasattr(strategy, 'value'):
            strategy = strategy.value  # 处理枚举类型

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
                "scanner": {
                    "interval": int(self._config.get("scanner", {}).get("interval", 120)),
                    "max_keys": 1000,
                    "enable_incremental": True,
                },
                "validation": {
                    "required_dirs": ["images", "joints"],
                    "stable_time": int(self._config.get("scanner", {}).get("stable_time", 10)),
                    "min_file_count": int(self._config.get("scanner", {}).get("min_file_count", 1)),
                    "check_count_match": False,
                    "reference_camera": "cam_left_wrist",
                },
            },
            "redis": {
                "host": str(self._config.get("redis", {}).get("host", "localhost")),
                "port": int(self._config.get("redis", {}).get("port", 6379)),
                "db": int(self._config.get("redis", {}).get("db", 0)),
                "password": self._config.get("redis", {}).get("password"),
            },
            "conversion": {
                "strategy": str(strategy),
                "output_fps": int(self._config.get("conversion", {}).get("fps", 30)),
            },
        }

        # 写入临时配置文件（BosClient 需要文件路径）
        self._temp_config_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.yaml', delete=False
        )
        yaml.dump(storage_config, self._temp_config_file, default_flow_style=False)
        self._temp_config_file.close()

        # 初始化 Redis 客户端
        import redis
        redis_config = storage_config.get("redis", {})
        redis_client = redis.Redis(
            host=redis_config.get("host", "localhost"),
            port=redis_config.get("port", 6379),
            db=redis_config.get("db", 0),
            password=redis_config.get("password"),
            decode_responses=True
        )

        self._bos_client = BosClient(self._temp_config_file.name)
        self._task_queue = TaskQueue(redis_client, queue_name="lerobot:episodes")
        self._scanner = EpisodeScanner(self._bos_client, self._task_queue)

        # 保存 redis client 和 storage_config 供后续使用
        self._redis_client = redis_client
        self._storage_config = storage_config

        self._emit_log("✓ BOS and Redis clients initialized")

    def start(self, mode: str = "continuous", interval: int = 120, full_scan: bool = False):
        """启动扫描服务

        Args:
            mode: "continuous" 或 "once"
            interval: 扫描间隔（秒），仅 continuous 模式有效
            full_scan: 是否全量扫描（清除增量位置）
        """
        with self._lock:
            if self._running:
                self._emit_log("⚠ Scanner already running")
                return False

            self._running = True
            self._mode = mode
            self._interval = interval
            self._started_at = datetime.now(timezone.utc)
            self._stop_event.clear()

            # 重置统计
            self._stats = {"found": 0, "ready": 0, "published": 0, "skipped": 0}

            self._thread = threading.Thread(
                target=self._run_loop,
                args=(mode, interval, full_scan),
                daemon=True
            )
            self._thread.start()

            self._emit_log(f"▶ Scanner started ({mode} mode, interval={interval}s)")
            return True

    def stop(self):
        """停止扫描服务"""
        with self._lock:
            if not self._running:
                return False

            self._emit_log("■ Stopping scanner...")
            self._stop_event.set()
            self._running = False

            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=5)

            self._emit_log("■ Scanner stopped")
            return True

    def _run_loop(self, mode: str, interval: int, full_scan: bool):
        """扫描主循环"""
        try:
            # 初始化客户端
            self._init_clients()

            # 全量扫描：清除增量位置
            if full_scan:
                self._emit_log("🔄 Full scan: clearing incremental position")
                namespace = self._scanner.get_namespace()
                incremental_key = f"bos:last_scanned_key:{namespace}"
                self._redis_client.delete(incremental_key)

            cycle = 0
            while not self._stop_event.is_set():
                cycle += 1
                self._emit_log(f"⟳ Starting scan cycle #{cycle}...")
                self._last_scan_at = datetime.now(timezone.utc)

                try:
                    # 执行扫描
                    ready_episodes = self._scanner.scan_and_filter()

                    self._stats["found"] = len(self._scanner.scan_episodes())
                    self._stats["ready"] = len(ready_episodes)

                    # 发布任务
                    published = 0
                    skipped = 0
                    for ep_info in ready_episodes:
                        episode_id = ep_info["episode_id"]

                        from lerobot_converter.core.task import ConversionTask, AlignmentStrategy

                        # 获取 strategy 并转换为枚举类型
                        strategy_str = self._config.get("conversion", {}).get("strategy", "nearest")
                        if hasattr(strategy_str, 'value'):
                            strategy_str = strategy_str.value  # 处理枚举类型

                        try:
                            strategy_enum = AlignmentStrategy(strategy_str)
                        except ValueError:
                            strategy_enum = AlignmentStrategy.NEAREST

                        task = ConversionTask(
                            source="bos",
                            episode_id=episode_id,
                            strategy=strategy_enum,
                            config_overrides={"bos_config_path": self._temp_config_file.name}
                        )

                        if self._task_queue.publish(task):
                            published += 1
                            self._emit_log(f"✓ Published {episode_id}")
                        else:
                            skipped += 1

                    self._stats["published"] += published
                    self._stats["skipped"] += skipped

                    self._emit_log(
                        f"📊 Cycle #{cycle} done: "
                        f"found={self._stats['found']}, ready={self._stats['ready']}, "
                        f"published={published}, skipped={skipped}"
                    )

                except Exception as e:
                    self._emit_log(f"✗ Scan error: {e}")
                    logger.exception("Scan error")

                # 单次模式：完成后退出
                if mode == "once":
                    self._emit_log("✓ One-time scan completed")
                    break

                # 持续模式：等待下一次扫描
                self._next_scan_at = datetime.now(timezone.utc).replace(
                    second=0, microsecond=0
                )

                # 分段等待，以便能够响应停止信号
                for _ in range(interval):
                    if self._stop_event.is_set():
                        break
                    time.sleep(1)

        except Exception as e:
            self._emit_log(f"✗ Scanner error: {e}")
            logger.exception("Scanner error")

        finally:
            self._running = False
            self._mode = None

    def get_status(self) -> Dict[str, Any]:
        """获取扫描器状态"""
        return {
            "running": self._running,
            "mode": self._mode,
            "interval": self._interval,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "last_scan_at": self._last_scan_at.isoformat() if self._last_scan_at else None,
            "next_scan_at": self._next_scan_at.isoformat() if self._next_scan_at else None,
            "stats": self._stats.copy()
        }


# 全局单例
scanner_service = ScannerService()
