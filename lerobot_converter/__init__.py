"""LeRobot v2.1 Converter

一个用于将机器人数据转换为LeRobot v2.1格式的工具包。

主要功能：
- 本地数据转换
- Redis分布式任务处理
- BOS (Baidu Object Storage) 云存储集成
"""

__version__ = "2.1.0"

# 核心转换器
from .pipeline.converter import LeRobotConverter
from .core.task import ConversionTask, AlignmentStrategy

# BOS模块
try:
    from .bos import BosClient, BosDownloader, BosUploader, EpisodeScanner
except ImportError:
    BosClient = None
    BosDownloader = None
    BosUploader = None
    EpisodeScanner = None

# Redis模块
try:
    from .redis import RedisClient, TaskQueue, RedisWorker
except ImportError:
    RedisClient = None
    TaskQueue = None
    RedisWorker = None

# CLI入口
from .cli import cli

__all__ = [
    # 版本
    '__version__',

    # 核心类
    'LeRobotConverter',
    'ConversionTask',
    'AlignmentStrategy',

    # BOS模块
    'BosClient',
    'BosDownloader',
    'BosUploader',
    'EpisodeScanner',

    # Redis模块
    'RedisClient',
    'TaskQueue',
    'RedisWorker',

    # CLI
    'cli',
]
