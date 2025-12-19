"""Pydantic models for API request/response"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class ScanMode(str, Enum):
    """扫描模式"""
    CONTINUOUS = "continuous"
    ONCE = "once"


class AlignmentStrategy(str, Enum):
    """对齐策略"""
    NEAREST = "nearest"
    CHUNKING = "chunking"
    WINDOW = "window"


# ============================================================
# 配置相关
# ============================================================

class BosConfig(BaseModel):
    """BOS 连接配置"""
    endpoint: str = "https://s3.bj.bcebos.com"
    bucket: str = "srgdata"
    region: str = "bj"
    access_key: str = ""
    secret_key: str = ""


class PathConfig(BaseModel):
    """数据路径配置"""
    raw_data: str = ""
    converted: str = ""
    task_name: str = ""


class ConversionConfig(BaseModel):
    """转换策略配置"""
    strategy: AlignmentStrategy = AlignmentStrategy.NEAREST
    tolerance_ms: int = 20
    chunk_size: int = 10
    fps: int = 25


class WorkerConfig(BaseModel):
    """Worker 配置"""
    num_workers: int = 4
    download_concurrent: int = 4
    upload_concurrent: int = 4


class ScannerConfig(BaseModel):
    """扫描器配置"""
    interval: int = 120
    stable_time: int = 10
    min_file_count: int = 1


class RedisConfig(BaseModel):
    """Redis 配置"""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None


class AppConfig(BaseModel):
    """完整应用配置"""
    bos: BosConfig = Field(default_factory=BosConfig)
    paths: PathConfig = Field(default_factory=PathConfig)
    conversion: ConversionConfig = Field(default_factory=ConversionConfig)
    scanner: ScannerConfig = Field(default_factory=ScannerConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    worker: WorkerConfig = Field(default_factory=WorkerConfig)


# ============================================================
# Scanner 相关
# ============================================================

class ScannerStartRequest(BaseModel):
    """启动扫描器请求"""
    mode: ScanMode = ScanMode.CONTINUOUS
    interval: int = 120


class ScanProgress(BaseModel):
    """扫描进度"""
    scanning: bool = False
    phase: str = ""  # "listing", "validating", "publishing", "done", "error"
    current: int = 0
    total: int = 0
    message: str = ""
    eta_seconds: Optional[int] = None  # 预估剩余时间（秒）


class ScannerStatus(BaseModel):
    """扫描器状态"""
    running: bool = False
    mode: Optional[ScanMode] = None
    interval: int = 120
    started_at: Optional[str] = None
    last_scan_at: Optional[str] = None
    next_scan_at: Optional[str] = None
    stats: Dict[str, int] = Field(default_factory=lambda: {
        "found": 0,
        "ready": 0,
        "published": 0,
        "skipped": 0
    })
    progress: ScanProgress = Field(default_factory=ScanProgress)


# ============================================================
# Worker 相关
# ============================================================

class WorkerStartRequest(BaseModel):
    """启动 Worker 请求"""
    num_workers: int = 4


class WorkerStatus(BaseModel):
    """Worker 状态"""
    running: bool = False
    num_workers: int = 0
    active_workers: int = 0
    started_at: Optional[str] = None


# ============================================================
# 监控相关
# ============================================================

class QueueStats(BaseModel):
    """队列统计"""
    pending: int = 0
    processing: int = 0
    completed: int = 0
    failed: int = 0


class EpisodeInfo(BaseModel):
    """Episode 信息"""
    episode_id: str
    status: str  # "completed", "failed", "processing"
    timestamp: str
    source: Optional[str] = None
    source_path: Optional[str] = None
    target_path: Optional[str] = None
    strategy: Optional[str] = None
    frames: Optional[int] = None
    error: Optional[str] = None


class EpisodeListResponse(BaseModel):
    """Episode 列表响应"""
    episodes: List[EpisodeInfo]
    total: int


# ============================================================
# 通用响应
# ============================================================

class ApiResponse(BaseModel):
    """通用 API 响应"""
    success: bool
    message: str = ""
    data: Optional[Any] = None


class TestBosResponse(BaseModel):
    """BOS 连接测试响应"""
    success: bool
    message: str
    bucket_exists: bool = False
    raw_data_exists: bool = False
    converted_exists: bool = False
