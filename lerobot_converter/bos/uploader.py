"""BOS 数据上传器

将转换后的数据上传到 BOS。
"""

import os
import logging
from pathlib import Path
from typing import Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from botocore.exceptions import ClientError

from .client import BosClient

logger = logging.getLogger(__name__)


class BosUploader:
    """BOS 数据上传器"""

    def __init__(self, bos_client: BosClient):
        """初始化上传器

        Args:
            bos_client: BOS 客户端
        """
        self.bos = bos_client
        self.upload_config = bos_client.get_upload_config()
        self.concurrent = self.upload_config.get('concurrent', 4)
        self.retry = self.upload_config.get('retry', 3)
        self.retry_delay = self.upload_config.get('retry_delay', 5)
        self.cleanup_local = self.upload_config.get('cleanup_local', True)
        self.overwrite = self.upload_config.get('overwrite', False)

    def upload_episode(
        self,
        local_dir: Path,
        episode_id: str,
        task_name: Optional[str] = None
    ) -> bool:
        """上传转换后的 episode 数据到 BOS

        Args:
            local_dir: 本地数据目录
            episode_id: Episode ID
            task_name: 任务名称（可选，用于组织 BOS 路径）

        Returns:
            bool: 是否成功上传
        """
        logger.info(f"Uploading episode {episode_id} to BOS...")

        if not local_dir.exists():
            logger.error(f"Local directory {local_dir} does not exist")
            return False

        # 构建 BOS 目标前缀
        converted_prefix = self.bos.get_converted_prefix()
        if task_name:
            bos_prefix = f"{converted_prefix}{task_name}/{episode_id}/"
        else:
            bos_prefix = f"{converted_prefix}{episode_id}/"

        # 获取所有需要上传的文件
        files_to_upload = self._get_files_to_upload(local_dir)
        logger.info(f"Found {len(files_to_upload)} files to upload")

        if len(files_to_upload) == 0:
            logger.warning(f"No files found in {local_dir}")
            return False

        # 并发上传
        # 单文件上传超时时间（秒）
        file_timeout = self.upload_config.get('file_timeout', 300)
        failed_files = []

        with ThreadPoolExecutor(max_workers=self.concurrent) as executor:
            futures = {
                executor.submit(
                    self._upload_file,
                    file_path,
                    bos_prefix,
                    local_dir
                ): file_path
                for file_path in files_to_upload
            }

            success_count = 0
            for future in as_completed(futures, timeout=file_timeout * len(files_to_upload)):
                file_path = futures[future]
                try:
                    if future.result(timeout=file_timeout):
                        success_count += 1
                    else:
                        failed_files.append(file_path)
                except TimeoutError:
                    logger.error(f"Upload timeout for {file_path}")
                    failed_files.append(file_path)
                except Exception as e:
                    logger.error(f"Failed to upload {file_path}: {e}")
                    failed_files.append(file_path)

        logger.info(f"Uploaded {success_count}/{len(files_to_upload)} files")
        if failed_files:
            logger.error(f"Failed files: {[str(f) for f in failed_files[:10]]}")

        upload_success = success_count == len(files_to_upload)

        # 清理本地文件（如果配置启用）
        if upload_success and self.cleanup_local:
            self._cleanup_local(local_dir)

        return upload_success

    def _get_files_to_upload(self, local_dir: Path) -> List[Path]:
        """获取所有需要上传的文件

        Args:
            local_dir: 本地目录

        Returns:
            List[Path]: 文件路径列表
        """
        files = []
        for root, dirs, filenames in os.walk(local_dir):
            for filename in filenames:
                file_path = Path(root) / filename
                files.append(file_path)
        return files

    def _upload_file(
        self,
        local_path: Path,
        bos_prefix: str,
        local_base_dir: Path
    ) -> bool:
        """上传单个文件

        Args:
            local_path: 本地文件路径
            bos_prefix: BOS 目标前缀
            local_base_dir: 本地基础目录（用于计算相对路径）

        Returns:
            bool: 是否成功上传
        """
        # 计算 BOS key
        relative_path = local_path.relative_to(local_base_dir)
        bos_key = f"{bos_prefix}{relative_path}"

        # 检查文件是否已存在（如果不覆盖）
        if not self.overwrite and self.bos.object_exists(bos_key):
            logger.debug(f"File already exists, skipping: {bos_key}")
            return True

        # 重试上传
        for attempt in range(self.retry):
            try:
                self.bos.client.upload_file(
                    Filename=str(local_path),
                    Bucket=self.bos.bucket,
                    Key=bos_key
                )
                logger.debug(f"Uploaded: {local_path} -> {bos_key}")
                return True
            except ClientError as e:
                logger.warning(f"Upload attempt {attempt + 1}/{self.retry} failed for {local_path}: {e}")
                if attempt < self.retry - 1:
                    import time
                    time.sleep(self.retry_delay)
            except Exception as e:
                logger.error(f"Unexpected error uploading {local_path}: {e}")
                return False

        return False

    def _cleanup_local(self, local_dir: Path):
        """清理本地文件

        Args:
            local_dir: 本地目录
        """
        if local_dir.exists():
            import shutil
            shutil.rmtree(local_dir)
            logger.info(f"Cleaned up local directory: {local_dir}")
