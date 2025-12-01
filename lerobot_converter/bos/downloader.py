"""BOS 数据下载器

从 BOS 下载 episode 数据到本地。
"""

import os
import logging
from pathlib import Path
from typing import Optional
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

    def download_episode(self, episode_id: str) -> Optional[Path]:
        """下载 episode 数据到本地

        BOS 格式和本地格式一致：
        task_name/episode_XXXX/
        ├── images/
        │   ├── cam_*/...
        │   └── metadata.json
        └── joints/
            ├── *.parquet
            └── metadata.json

        Args:
            episode_id: Episode ID

        Returns:
            Optional[Path]: task_path (quad_arm_task 目录路径)，失败返回 None
        """
        logger.info(f"Downloading episode {episode_id} from BOS...")

        # 创建目标目录：temp_dir/quad_arm_task/episode_XXXX/
        task_name = self.bos.get_task_name()
        task_path = self.temp_dir / task_name
        episode_dir = task_path / episode_id
        episode_dir.mkdir(parents=True, exist_ok=True)

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

        # 并发下载到目标位置
        logger.info(f"Downloading to {episode_dir}")
        with ThreadPoolExecutor(max_workers=self.concurrent) as executor:
            futures = {
                executor.submit(self._download_file, key, episode_dir, prefix): key
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

        # 验证下载结果
        joints_dir = episode_dir / "joints"
        images_dir = episode_dir / "images"

        logger.info(f"✓ Download completed: {episode_dir}")

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

        return task_path

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
