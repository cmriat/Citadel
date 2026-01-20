"""
Citadel 统一配置模块

集中管理所有配置项、默认值和环境变量。
支持通过 .env 文件或环境变量覆盖默认配置。

使用方式:
    from backend.config import settings

    port = settings.API_PORT
    fps = settings.DEFAULT_FPS
"""

import os
from pathlib import Path
from typing import Optional
from functools import lru_cache

# 加载 .env 文件（项目根目录）
from dotenv import load_dotenv

_project_root = Path(__file__).parent.parent.parent
_env_file = _project_root / ".env"
if _env_file.exists():
    load_dotenv(_env_file)
    print(f"✓ 已加载配置文件: {_env_file}")


def _get_env(key: str, default: str) -> str:
    """从环境变量获取字符串值"""
    return os.environ.get(key, default)


def _get_env_int(key: str, default: int) -> int:
    """从环境变量获取整数值"""
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_env_bool(key: str, default: bool) -> bool:
    """从环境变量获取布尔值"""
    value = os.environ.get(key)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes", "on")


def _get_env_optional(key: str) -> Optional[str]:
    """从环境变量获取可选字符串值"""
    value = os.environ.get(key)
    return value if value else None


class Settings:
    """
    Citadel 统一配置类

    所有配置项都可以通过对应的环境变量覆盖。
    环境变量命名规则: CITADEL_{配置项名} 或直接使用配置项名
    """

    # =========================================================================
    # 服务器配置
    # =========================================================================

    @property
    def API_HOST(self) -> str:
        """API 服务器监听地址"""
        return _get_env("API_HOST", "0.0.0.0")

    @property
    def API_PORT(self) -> int:
        """API 服务器端口"""
        return _get_env_int("API_PORT", 8000)

    @property
    def FRONTEND_PORT(self) -> int:
        """前端开发服务器端口"""
        return _get_env_int("FRONTEND_PORT", 5173)

    @property
    def CORS_ORIGINS(self) -> str:
        """CORS 允许的源，多个用逗号分隔，* 表示允许所有"""
        return _get_env("CORS_ORIGINS", "*")

    # =========================================================================
    # BOS 配置
    # =========================================================================

    @property
    def BOS_ALIAS(self) -> str:
        """BOS 别名 (mc alias name)"""
        return _get_env("BOS_ALIAS", "bos")

    @property
    def BOS_TEST_PATH(self) -> str:
        """BOS 连接测试路径"""
        return _get_env("BOS_TEST_PATH", "srgdata/")

    @property
    def BOS_DEFAULT_PREFIX(self) -> str:
        """BOS 默认路径前缀"""
        return _get_env("BOS_DEFAULT_PREFIX", "srgdata/robot/")

    # =========================================================================
    # MC 工具配置
    # =========================================================================

    @property
    def MC_PATH(self) -> Optional[str]:
        """mc 可执行文件路径，为空时自动检测"""
        return _get_env_optional("MC_PATH")

    # =========================================================================
    # 数据库配置
    # =========================================================================

    @property
    def DB_PATH(self) -> str:
        """SQLite 数据库文件路径"""
        return _get_env("DB_PATH", "backend/data/tasks.db")

    # =========================================================================
    # 业务默认值 - 并发和性能
    # =========================================================================

    @property
    def DEFAULT_CONCURRENCY(self) -> int:
        """默认并发数（下载/上传）"""
        return _get_env_int("DEFAULT_CONCURRENCY", 10)

    @property
    def DEFAULT_PARALLEL_JOBS(self) -> int:
        """默认并行任务数（转换）"""
        return _get_env_int("DEFAULT_PARALLEL_JOBS", 4)

    # =========================================================================
    # 业务默认值 - 数据格式
    # =========================================================================

    @property
    def DEFAULT_FPS(self) -> int:
        """默认视频帧率"""
        return _get_env_int("DEFAULT_FPS", 25)

    @property
    def DEFAULT_ROBOT_TYPE(self) -> str:
        """默认机器人类型"""
        return _get_env("DEFAULT_ROBOT_TYPE", "airbot_play")

    @property
    def DEFAULT_TASK_NAME(self) -> str:
        """默认任务描述"""
        return _get_env("DEFAULT_TASK_NAME", "Fold the laundry")

    @property
    def DEFAULT_FILE_PATTERN(self) -> str:
        """默认文件匹配模式"""
        return _get_env("DEFAULT_FILE_PATTERN", "episode_*.h5")

    @property
    def DEFAULT_ALIGNMENT_METHOD(self) -> str:
        """默认关节对齐方法 (nearest=最近邻, linear=线性插值)"""
        return _get_env("DEFAULT_ALIGNMENT_METHOD", "nearest")

    # =========================================================================
    # 业务默认值 - 向量维度
    # =========================================================================

    @property
    def STATE_MAX_DIM(self) -> int:
        """状态向量最大维度"""
        return _get_env_int("STATE_MAX_DIM", 14)

    @property
    def ACTION_MAX_DIM(self) -> int:
        """动作向量最大维度"""
        return _get_env_int("ACTION_MAX_DIM", 14)

    # =========================================================================
    # 超时配置（秒）
    # =========================================================================

    @property
    def TIMEOUT_MC_CHECK(self) -> int:
        """mc 工具检查超时（秒）"""
        return _get_env_int("TIMEOUT_MC_CHECK", 10)

    @property
    def TIMEOUT_BOS_SCAN(self) -> int:
        """BOS 扫描超时（秒）"""
        return _get_env_int("TIMEOUT_BOS_SCAN", 30)

    @property
    def TIMEOUT_CONVERT(self) -> int:
        """单文件转换超时（秒）"""
        return _get_env_int("TIMEOUT_CONVERT", 300)

    @property
    def TIMEOUT_UPLOAD(self) -> int:
        """上传任务超时（秒）"""
        return _get_env_int("TIMEOUT_UPLOAD", 3600)

    @property
    def TIMEOUT_API_DEFAULT(self) -> int:
        """API 请求默认超时（毫秒）"""
        return _get_env_int("TIMEOUT_API_DEFAULT", 30000)

    @property
    def TIMEOUT_PIPELINE(self) -> int:
        """Pipeline 操作超时（毫秒）"""
        return _get_env_int("TIMEOUT_PIPELINE", 120000)

    # =========================================================================
    # 其他配置
    # =========================================================================

    @property
    def TASK_CLEANUP_DAYS(self) -> int:
        """自动清理超过指定天数的已完成任务"""
        return _get_env_int("TASK_CLEANUP_DAYS", 30)

    @property
    def JPEG_QUALITY(self) -> int:
        """JPEG 图片压缩质量 (0-100)"""
        return _get_env_int("JPEG_QUALITY", 70)

    @property
    def THUMBNAIL_CACHE_DIR(self) -> str:
        """视频缩略图缓存目录（用于加速 scan-episodes/QC 打开）"""
        default = str(Path(self.DB_PATH).expanduser().parent / "cache" / "thumbnails")
        return _get_env("THUMBNAIL_CACHE_DIR", default)

    @property
    def THUMBNAIL_CACHE_MAX_ITEMS(self) -> int:
        """缩略图内存缓存最大条目数（LRU）"""
        return _get_env_int("THUMBNAIL_CACHE_MAX_ITEMS", 512)

    @property
    def DEBUG(self) -> bool:
        """调试模式"""
        return _get_env_bool("DEBUG", False)

    # =========================================================================
    # 辅助方法
    # =========================================================================

    def get_mc_path(self) -> str:
        """
        获取 mc 可执行文件路径

        优先级: MC_PATH 环境变量 > ~/bin/mc > 系统 PATH
        """
        import shutil

        # 1. 环境变量
        if self.MC_PATH:
            return self.MC_PATH

        # 2. ~/bin/mc
        home_mc = Path.home() / "bin" / "mc"
        if home_mc.exists():
            return str(home_mc)

        # 3. 系统 PATH
        which_mc = shutil.which("mc")
        if which_mc:
            return which_mc

        # 4. 默认值
        return "mc"

    def get_bos_full_path(self, path: str) -> str:
        """
        获取完整的 BOS 路径

        Args:
            path: 相对路径或完整路径

        Returns:
            格式化后的完整 BOS 路径 (bos/...)
        """
        # 移除可能的前缀
        if path.startswith("bos:/"):
            path = path[5:]
        elif path.startswith("bos/"):
            path = path[4:]

        return f"{self.BOS_ALIAS}/{path}"

    def get_cors_origins_list(self) -> list:
        """获取 CORS 允许的源列表"""
        origins = self.CORS_ORIGINS
        if origins == "*":
            return ["*"]
        return [o.strip() for o in origins.split(",") if o.strip()]

    def to_dict(self) -> dict:
        """导出所有配置为字典（用于调试）"""
        return {
            # 服务器
            "API_HOST": self.API_HOST,
            "API_PORT": self.API_PORT,
            "FRONTEND_PORT": self.FRONTEND_PORT,
            "CORS_ORIGINS": self.CORS_ORIGINS,
            # BOS
            "BOS_ALIAS": self.BOS_ALIAS,
            "BOS_TEST_PATH": self.BOS_TEST_PATH,
            "BOS_DEFAULT_PREFIX": self.BOS_DEFAULT_PREFIX,
            "MC_PATH": self.MC_PATH,
            # 数据库
            "DB_PATH": self.DB_PATH,
            # 业务默认值
            "DEFAULT_CONCURRENCY": self.DEFAULT_CONCURRENCY,
            "DEFAULT_PARALLEL_JOBS": self.DEFAULT_PARALLEL_JOBS,
            "DEFAULT_FPS": self.DEFAULT_FPS,
            "DEFAULT_ROBOT_TYPE": self.DEFAULT_ROBOT_TYPE,
            "DEFAULT_TASK_NAME": self.DEFAULT_TASK_NAME,
            "DEFAULT_FILE_PATTERN": self.DEFAULT_FILE_PATTERN,
            "DEFAULT_ALIGNMENT_METHOD": self.DEFAULT_ALIGNMENT_METHOD,
            "STATE_MAX_DIM": self.STATE_MAX_DIM,
            "ACTION_MAX_DIM": self.ACTION_MAX_DIM,
            # 超时
            "TIMEOUT_MC_CHECK": self.TIMEOUT_MC_CHECK,
            "TIMEOUT_BOS_SCAN": self.TIMEOUT_BOS_SCAN,
            "TIMEOUT_CONVERT": self.TIMEOUT_CONVERT,
            "TIMEOUT_UPLOAD": self.TIMEOUT_UPLOAD,
            "TIMEOUT_API_DEFAULT": self.TIMEOUT_API_DEFAULT,
            "TIMEOUT_PIPELINE": self.TIMEOUT_PIPELINE,
            # 其他
            "TASK_CLEANUP_DAYS": self.TASK_CLEANUP_DAYS,
            "JPEG_QUALITY": self.JPEG_QUALITY,
            "THUMBNAIL_CACHE_DIR": self.THUMBNAIL_CACHE_DIR,
            "THUMBNAIL_CACHE_MAX_ITEMS": self.THUMBNAIL_CACHE_MAX_ITEMS,
            "DEBUG": self.DEBUG,
        }


# 全局配置单例
settings = Settings()
