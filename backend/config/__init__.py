"""
Citadel 统一配置模块

所有硬编码配置、魔法数字和默认值都集中在这里管理。
支持通过环境变量和 .env 文件覆盖默认值。
"""

from backend.config.settings import settings, Settings

__all__ = ["settings", "Settings"]
