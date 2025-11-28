"""BOS 数据下载器

从 BOS 下载 episode 数据到本地临时目录，并重组织为 converter 期望的格式。
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from botocore.exceptions import ClientError

from .client import BosClient

logger = logging.getLogger(__name__)


class BosDownloader:
    """BOS 数据下载器"""

    def __init__(self, bos_client: BosClient):
        """初始化下载器

        Args:
            bos_client: BOS 客户端
        """
        self.bos = bos_client
        self.download_config = bos_client.get_download_config()

        # 获取临时目录：支持环境变量，使用系统默认temp作为fallback
        temp_dir_config = self.download_config.get('temp_dir')
        if temp_dir_config and temp_dir_config.startswith('${') and temp_dir_config.endswith('}'):
            # 处理环境变量：${VAR_NAME}
            env_var = temp_dir_config[2:-1]
            temp_dir_str = os.environ.get(env_var)
            if not temp_dir_str:
                # 环境变量未设置，使用系统默认temp
                import tempfile
                temp_dir_str = os.path.join(tempfile.gettempdir(), 'lerobot_bos')
                logger.info(f"Environment variable {env_var} not set, using default: {temp_dir_str}")
        elif temp_dir_config:
            temp_dir_str = temp_dir_config
        else:
            # 配置未设置，使用系统默认temp
            import tempfile
            temp_dir_str = os.path.join(tempfile.gettempdir(), 'lerobot_bos')
            logger.info(f"temp_dir not configured, using default: {temp_dir_str}")

        self.temp_dir = Path(temp_dir_str).resolve()  # 转换为绝对路径
        self.concurrent = self.download_config.get('concurrent', 4)
        self.retry = self.download_config.get('retry', 3)
        self.retry_delay = self.download_config.get('retry_delay', 5)

    def download_episode(self, episode_id: str) -> Optional[Tuple[Path, Path]]:
        """下载 episode 数据到本地并重组织为 converter 期望的格式

        BOS 格式：episode_XXXX/images/ 和 episode_XXXX/joints/
        本地格式：joints/quad_arm_task/episode_XXXX/ 和 images/quad_arm_task/episode_XXXX/

        Args:
            episode_id: Episode ID

        Returns:
            Optional[Tuple[Path, Path]]: (joints_base_path, images_base_path)，失败返回 None
                - joints_base_path: joints/quad_arm_task (converter的data_path)
                - images_base_path: images/quad_arm_task (converter的images_path)
        """
        logger.info(f"Downloading episode {episode_id} from BOS...")

        # 创建临时目录
        # raw/ 保存原始下载的数据（BOS 格式）
        # converted/ 保存重组织后的数据（converter 格式）
        base_dir = self.temp_dir / episode_id
        raw_dir = base_dir / "raw"
        converted_dir = base_dir / "converted"

        raw_dir.mkdir(parents=True, exist_ok=True)
        converted_dir.mkdir(parents=True, exist_ok=True)

        # 获取 BOS 上的所有文件（支持分页）
        prefix = f"{self.bos.get_raw_data_prefix()}{episode_id}/"
        logger.info(f"Listing objects with prefix: {prefix}")

        files_to_download = []
        continuation_token = None
        page_count = 0

        while True:
            page_count += 1
            if continuation_token:
                response = self.bos.client.list_objects_v2(
                    Bucket=self.bos.bucket,
                    Prefix=prefix,
                    MaxKeys=1000,
                    ContinuationToken=continuation_token
                )
            else:
                response = self.bos.list_objects(prefix=prefix, max_keys=1000)

            if 'Contents' not in response:
                if page_count == 1:
                    logger.error(f"No files found for episode {episode_id}")
                    logger.error(f"Response keys: {response.keys()}")
                    return None
                break

            page_files = [obj['Key'] for obj in response['Contents']]
            files_to_download.extend(page_files)
            logger.info(f"Page {page_count}: found {len(page_files)} files")

            if not response.get('IsTruncated'):
                break

            continuation_token = response.get('NextContinuationToken')

        logger.info(f"Total files to download: {len(files_to_download)}")

        # 显示前几个文件
        if files_to_download:
            logger.info(f"Sample files: {files_to_download[:3]}")

        # 并发下载到 raw/ 目录
        logger.info(f"Starting concurrent download to {raw_dir}")
        with ThreadPoolExecutor(max_workers=self.concurrent) as executor:
            futures = {
                executor.submit(self._download_file, key, raw_dir, prefix): key
                for key in files_to_download
            }

            success_count = 0
            failed_files = []
            for future in as_completed(futures):
                key = futures[future]
                try:
                    if future.result():
                        success_count += 1
                    else:
                        failed_files.append(key)
                except Exception as e:
                    logger.error(f"Failed to download {key}: {e}")
                    failed_files.append(key)

        logger.info(f"Downloaded {success_count}/{len(files_to_download)} files")

        if failed_files:
            logger.error(f"Failed to download {len(failed_files)} files:")
            for f in failed_files[:10]:  # 只显示前10个
                logger.error(f"  - {f}")
            if len(failed_files) > 10:
                logger.error(f"  ... and {len(failed_files) - 10} more")

        if success_count < len(files_to_download):
            logger.warning(f"Some files failed to download for episode {episode_id}")
            return None

        # 重组织目录结构
        try:
            logger.info("Reorganizing directory structure...")
            task_path, _ = self._reorganize_directory(
                raw_dir,  # 使用 raw_dir，不是 raw_dir / episode_id
                converted_dir,
                episode_id
            )
            logger.info(f"✓ Reorganized directory structure")

            # 验证重组织结果
            episode_dir = task_path / episode_id
            joints_dir = episode_dir / "joints"
            images_dir = episode_dir / "images"

            logger.info(f"  Episode: {episode_dir}")

            if joints_dir.exists():
                joints_files = list(joints_dir.iterdir())
                logger.info(f"  - joints/: {len(joints_files)} files")
                has_joints_meta = (joints_dir / "metadata.json").exists()
                if has_joints_meta:
                    logger.info(f"    ✓ metadata.json exists")
                else:
                    logger.warning(f"    ⚠️  metadata.json missing!")

            if images_dir.exists():
                cam_dirs = [d for d in images_dir.iterdir() if d.is_dir()]
                logger.info(f"  - images/: {len(cam_dirs)} cameras")
                has_images_meta = (images_dir / "metadata.json").exists()
                if has_images_meta:
                    logger.info(f"    ✓ metadata.json exists")
                else:
                    logger.warning(f"    ⚠️  metadata.json missing!")

            return task_path, task_path  # 新格式：两个路径相同
        except Exception as e:
            logger.error(f"Failed to reorganize directory: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _reorganize_directory(
        self,
        raw_episode_dir: Path,
        converted_base: Path,
        episode_id: str
    ) -> Tuple[Path, Path]:
        """重组织目录结构：从 BOS 格式转换为 converter 新格式

        BOS 格式（输入）：
            raw_episode_dir/
            ├── images/
            │   ├── cam_head/*.jpg
            │   ├── cam_left/*.jpg
            │   ├── cam_right/*.jpg
            │   └── metadata.json
            └── joints/
                ├── *.parquet
                └── metadata.json

        Converter 新格式（输出）：
            converted_base/quad_arm_task/
            └── episode_XXXX/
                ├── images/
                │   ├── cam_head/*.jpg
                │   ├── cam_left/*.jpg
                │   ├── cam_right/*.jpg
                │   └── metadata.json
                └── joints/
                    ├── *.parquet
                    └── metadata.json

        Args:
            raw_episode_dir: 原始 episode 目录（BOS 格式）
            converted_base: 转换后的基础目录
            episode_id: Episode ID

        Returns:
            Tuple[Path, Path]: (task_dir, task_dir) - 两个都返回 task_dir，因为新格式下 images 和 joints 在同一目录下
        """
        task_name = self.bos.get_task_name()

        # 创建目标目录结构：converted_base/quad_arm_task/episode_XXXX/
        task_dir = converted_base / task_name
        episode_dir = task_dir / episode_id

        joints_dir = episode_dir / "joints"
        images_dir = episode_dir / "images"

        joints_dir.mkdir(parents=True, exist_ok=True)
        images_dir.mkdir(parents=True, exist_ok=True)

        # 复制 joints 数据
        raw_joints_dir = raw_episode_dir / "joints"
        if raw_joints_dir.exists():
            joints_count = 0
            for item in raw_joints_dir.iterdir():
                shutil.copy2(item, joints_dir / item.name)
                logger.debug(f"  Copied: {item.name}")
                joints_count += 1
            logger.info(f"Copied {joints_count} files to {joints_dir}")

        # 复制 images 数据
        raw_images_dir = raw_episode_dir / "images"
        if raw_images_dir.exists():
            cam_count = 0
            has_metadata = False
            for item in raw_images_dir.iterdir():
                if item.is_dir():
                    # 复制相机目录
                    target_cam_dir = images_dir / item.name
                    if target_cam_dir.exists():
                        shutil.rmtree(target_cam_dir)
                    shutil.copytree(item, target_cam_dir)
                    file_count = len(list(target_cam_dir.iterdir()))
                    logger.info(f"  Copied camera: {item.name} ({file_count} files)")
                    cam_count += 1
                elif item.name == 'metadata.json':
                    # 复制 metadata.json
                    shutil.copy2(item, images_dir / item.name)
                    logger.info(f"  Copied: metadata.json")
                    has_metadata = True
                else:
                    # 未知文件类型，记录警告
                    logger.warning(f"  Unknown item in images/: {item.name}")

            logger.info(f"Copied {cam_count} cameras to {images_dir}")
            if not has_metadata:
                logger.warning(f"⚠️  metadata.json not found in {raw_images_dir}")

        # 返回 task_dir（新格式下 data_path 和 images_path 都指向同一个目录）
        return task_dir, task_dir

    def _download_file(self, key: str, local_base_dir: Path, prefix: str) -> bool:
        """下载单个文件

        Args:
            key: BOS 对象 key
            local_base_dir: 本地基础目录
            prefix: BOS 前缀（用于计算相对路径）

        Returns:
            bool: 是否成功下载
        """
        # 计算本地文件路径
        relative_path = key[len(prefix):]
        local_path = local_base_dir / relative_path
        local_path.parent.mkdir(parents=True, exist_ok=True)

        # 重试下载
        for attempt in range(self.retry):
            try:
                logger.debug(f"Downloading {key} (attempt {attempt + 1}/{self.retry})...")
                self.bos.client.download_file(
                    Bucket=self.bos.bucket,
                    Key=key,
                    Filename=str(local_path)
                )

                # 验证文件是否真的下载了
                if not local_path.exists():
                    logger.error(f"File not found after download: {local_path}")
                    return False

                file_size = local_path.stat().st_size
                logger.debug(f"✓ Downloaded: {key} -> {local_path} ({file_size} bytes)")
                return True

            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                logger.warning(f"Download attempt {attempt + 1}/{self.retry} failed for {key}: {error_code} - {e}")
                if attempt < self.retry - 1:
                    import time
                    time.sleep(self.retry_delay)
            except Exception as e:
                logger.error(f"Unexpected error downloading {key}: {type(e).__name__}: {e}")
                return False

        logger.error(f"Failed to download {key} after {self.retry} attempts")
        return False

    def cleanup(self, episode_id: str):
        """清理下载的临时文件

        Args:
            episode_id: Episode ID
        """
        local_dir = self.temp_dir / episode_id

        if local_dir.exists():
            import shutil
            shutil.rmtree(local_dir)
            logger.info(f"Cleaned up temporary files for episode {episode_id}")
