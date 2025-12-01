"""路径工具函数

提供跨模块共享的路径处理逻辑，消除代码重复。
"""

from pathlib import Path
from typing import Tuple, Optional


def detect_episode_format(
    episode_base_dir: Path,
    images_path: Optional[Path] = None
) -> Tuple[str, Path, Path]:
    """检测 episode 数据格式并返回对应路径

    自动识别新旧两种数据格式：
    - 新格式：episode_XXXX/joints/*.parquet, episode_XXXX/images/cam_*/
    - 旧格式：episode_XXXX/*.parquet, (images_path)/episode_XXXX/cam_*/

    Args:
        episode_base_dir: episode 基础目录 (data_path/episode_XXXX)
        images_path: 旧格式的 images 根目录（新格式下不需要）

    Returns:
        Tuple[format_type, data_dir, images_dir]:
        - format_type: 'new' or 'legacy'
        - data_dir: 关节数据目录（parquet 文件所在位置）
        - images_dir: 图像数据目录（cameras 子目录所在位置）

    Examples:
        >>> # 新格式
        >>> detect_episode_format(Path('data/episode_0001'))
        ('new', Path('data/episode_0001/joints'), Path('data/episode_0001/images'))

        >>> # 旧格式
        >>> detect_episode_format(Path('data/episode_0001'), Path('images'))
        ('legacy', Path('data/episode_0001'), Path('images/episode_0001'))
    """
    # 检查新格式特征：joints/ 子目录是否存在
    new_format_joints_dir = episode_base_dir / "joints"

    if new_format_joints_dir.exists() and new_format_joints_dir.is_dir():
        # 新格式
        return (
            'new',
            new_format_joints_dir,           # data_dir: episode_XXXX/joints/
            episode_base_dir / "images"      # images_dir: episode_XXXX/images/
        )
    else:
        # 旧格式
        if images_path is None:
            raise ValueError(
                f"Legacy format detected for {episode_base_dir}, "
                "but images_path not provided"
            )

        return (
            'legacy',
            episode_base_dir,                         # data_dir: episode_XXXX/
            images_path / episode_base_dir.name       # images_dir: (images_path)/episode_XXXX/
        )
