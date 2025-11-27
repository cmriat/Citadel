"""转换任务定义"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict
import time


class AlignmentStrategy(Enum):
    """对齐策略枚举"""
    NEAREST = "nearest"
    CHUNKING = "chunking"
    WINDOW = "window"


@dataclass
class ConversionTask:
    """统一的转换任务定义

    Attributes:
        episode_id: Episode ID（如 episode_0007）
        source: 数据源ID（如 robot_1）
        strategy: 对齐策略
        config_overrides: 配置覆盖项
        timestamp: 任务创建时间戳
    """
    episode_id: str
    source: str = "local"
    strategy: AlignmentStrategy = AlignmentStrategy.CHUNKING
    config_overrides: Optional[Dict] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        """序列化为字典（用于 JSON 传输）"""
        return {
            'episode_id': self.episode_id,
            'source': self.source,
            'strategy': self.strategy.value,
            'config_overrides': self.config_overrides or {},
            'timestamp': self.timestamp
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ConversionTask':
        """从字典反序列化"""
        return cls(
            episode_id=data['episode_id'],
            source=data.get('source', 'local'),
            strategy=AlignmentStrategy(data.get('strategy', 'chunking')),
            config_overrides=data.get('config_overrides'),
            timestamp=data.get('timestamp', time.time())
        )

    def __repr__(self) -> str:
        return f"ConversionTask({self.source}/{self.episode_id}, strategy={self.strategy.value})"
