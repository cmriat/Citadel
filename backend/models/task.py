"""
任务数据模型

定义下载和转换任务的数据结构、状态机和序列化方法。
"""

from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import uuid


class TaskType(str, Enum):
    """任务类型"""
    DOWNLOAD = "download"
    CONVERT = "convert"
    UPLOAD = "upload"
    MERGE = "merge"


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"        # 等待执行
    RUNNING = "running"        # 执行中
    COMPLETED = "completed"    # 成功完成
    FAILED = "failed"          # 失败
    CANCELLED = "cancelled"    # 已取消


class DownloadConfig(BaseModel):
    """下载任务配置"""
    bos_path: str = Field(..., description="BOS远程路径")
    local_path: str = Field(..., description="本地保存路径")
    concurrency: int = Field(default=10, description="并发下载数")
    mc_path: str = Field(default="/home/jovyan/mc", description="mc可执行文件路径")


class ConvertConfig(BaseModel):
    """转换任务配置"""
    input_dir: str = Field(..., description="输入HDF5目录")
    output_dir: str = Field(..., description="输出LeRobot目录")
    robot_type: str = Field(default="airbot_play", description="机器人类型")
    fps: int = Field(default=25, description="视频帧率")
    task: str = Field(default="Fold the laundry", description="任务描述")
    parallel_jobs: int = Field(default=4, description="并发转换数")
    file_pattern: str = Field(default="episode_*.h5", description="文件匹配模式")


class UploadConfig(BaseModel):
    """上传任务配置"""
    local_dir: str = Field(..., description="本地LeRobot目录")
    bos_path: str = Field(..., description="BOS目标路径")
    concurrency: int = Field(default=10, description="并发上传数")
    include_videos: bool = Field(default=True, description="是否包含视频文件")
    delete_after: bool = Field(default=False, description="上传后是否删除本地文件")
    mc_path: str = Field(default="/home/jovyan/mc", description="mc可执行文件路径")


class MergeConfig(BaseModel):
    """合并任务配置"""
    source_dirs: List[str] = Field(..., description="源 episode 目录列表")
    output_dir: str = Field(..., description="输出合并数据集目录")
    state_max_dim: int = Field(default=14, description="状态向量最大维度")
    action_max_dim: int = Field(default=14, description="动作向量最大维度")
    fps: int = Field(default=25, description="视频帧率")
    copy_images: bool = Field(default=False, description="是否复制图像文件")


class TaskProgress(BaseModel):
    """任务进度信息"""
    percent: float = Field(default=0.0, description="完成百分比 0-100")
    current_file: Optional[str] = Field(default=None, description="当前处理的文件")
    total_files: int = Field(default=0, description="总文件数")
    completed_files: int = Field(default=0, description="已完成文件数")
    failed_files: int = Field(default=0, description="失败文件数")
    message: Optional[str] = Field(default=None, description="当前状态消息")
    # 字节传输统计
    bytes_total: int = Field(default=0, description="总字节数")
    bytes_transferred: int = Field(default=0, description="已传输字节数")
    # 速度和时间估算
    speed_bytes_per_sec: float = Field(default=0.0, description="传输速度 (字节/秒)")
    eta_seconds: int = Field(default=0, description="预计剩余秒数")


class TaskResult(BaseModel):
    """任务执行结果"""
    success: bool = Field(..., description="是否成功")
    total_files: int = Field(default=0, description="处理的文件总数")
    completed_files: int = Field(default=0, description="成功完成的文件数")
    failed_files: int = Field(default=0, description="失败的文件数")
    elapsed_seconds: float = Field(default=0.0, description="耗时秒数")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    details: Optional[Dict[str, Any]] = Field(default=None, description="详细结果")


class Task(BaseModel):
    """任务实体"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="任务唯一ID")
    type: TaskType = Field(..., description="任务类型")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="任务状态")

    # 配置（根据类型使用不同配置）
    config: Dict[str, Any] = Field(..., description="任务配置")

    # 进度信息
    progress: TaskProgress = Field(default_factory=TaskProgress, description="进度信息")

    # 时间信息
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    started_at: Optional[datetime] = Field(default=None, description="开始时间")
    finished_at: Optional[datetime] = Field(default=None, description="完成时间")

    # 结果
    result: Optional[TaskResult] = Field(default=None, description="执行结果")

    class Config:
        use_enum_values = True

    def start(self) -> None:
        """标记任务开始"""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now()

    def complete(self, result: TaskResult) -> None:
        """标记任务完成"""
        self.status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
        self.finished_at = datetime.now()
        self.result = result
        self.progress.percent = 100.0

    def cancel(self) -> None:
        """取消任务"""
        self.status = TaskStatus.CANCELLED
        self.finished_at = datetime.now()

    def update_progress(
        self,
        percent: Optional[float] = None,
        current_file: Optional[str] = None,
        completed_files: Optional[int] = None,
        failed_files: Optional[int] = None,
        message: Optional[str] = None,
        total_files: Optional[int] = None,
        bytes_total: Optional[int] = None,
        bytes_transferred: Optional[int] = None,
        speed_bytes_per_sec: Optional[float] = None,
        eta_seconds: Optional[int] = None
    ) -> None:
        """更新进度信息"""
        if percent is not None:
            self.progress.percent = percent
        if current_file is not None:
            self.progress.current_file = current_file
        if completed_files is not None:
            self.progress.completed_files = completed_files
        if failed_files is not None:
            self.progress.failed_files = failed_files
        if message is not None:
            self.progress.message = message
        if total_files is not None:
            self.progress.total_files = total_files
        if bytes_total is not None:
            self.progress.bytes_total = bytes_total
        if bytes_transferred is not None:
            self.progress.bytes_transferred = bytes_transferred
        if speed_bytes_per_sec is not None:
            self.progress.speed_bytes_per_sec = speed_bytes_per_sec
        if eta_seconds is not None:
            self.progress.eta_seconds = eta_seconds

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于存储）"""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """从字典创建任务"""
        return cls.model_validate(data)


# ============================================================================
# 请求/响应模型（用于API）
# ============================================================================

class CreateDownloadTaskRequest(BaseModel):
    """创建下载任务请求"""
    bos_path: str
    local_path: str
    concurrency: int = 10
    mc_path: str = "/home/jovyan/mc"


class CreateConvertTaskRequest(BaseModel):
    """创建转换任务请求"""
    input_dir: str
    output_dir: str
    robot_type: str = "airbot_play"
    fps: int = 25
    task: str = "Fold the laundry"
    parallel_jobs: int = 4
    file_pattern: str = "episode_*.h5"


class CreateUploadTaskRequest(BaseModel):
    """创建上传任务请求"""
    local_dir: str
    bos_path: str
    concurrency: int = 10
    include_videos: bool = True
    delete_after: bool = False
    mc_path: str = "/home/jovyan/mc"
    exclude_episodes: Optional[List[str]] = None  # 排除的 episode 名称列表


class CreateMergeTaskRequest(BaseModel):
    """创建合并任务请求"""
    source_dirs: List[str]
    output_dir: str
    state_max_dim: int = 14
    action_max_dim: int = 14
    fps: int = 25
    copy_images: bool = False


class TaskResponse(BaseModel):
    """任务响应"""
    id: str
    type: str
    status: str
    config: Dict[str, Any]
    progress: TaskProgress
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    result: Optional[TaskResult]


class TaskListResponse(BaseModel):
    """任务列表响应"""
    tasks: List[TaskResponse]
    total: int
