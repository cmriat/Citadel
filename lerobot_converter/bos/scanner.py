"""Episode 扫描器

扫描 BOS 上的新 episode，进行完整性检查，并发布到 Redis Stream。
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from .client import BosClient

logger = logging.getLogger(__name__)


class EpisodeScanner:
    """Episode 扫描器，负责发现和验证新的 episode"""

    # BOS 数据源标识符
    SOURCE = 'bos'

    def __init__(
        self,
        bos_client: BosClient,
        task_queue  # TaskQueue instance (避免循环导入，使用类型注释)
    ):
        """初始化扫描器

        Args:
            bos_client: BOS 客户端
            task_queue: TaskQueue 实例（用于统一的去重检查）
        """
        self.bos = bos_client
        self.task_queue = task_queue
        self.scanner_config = bos_client.get_scanner_config()
        self.validation_config = bos_client.get_validation_config()
        self.raw_data_prefix = bos_client.get_raw_data_prefix()
        self.converted_prefix = bos_client.get_converted_prefix()

        # 生成基于路径的命名空间，用于 Redis 键隔离
        # 使用 raw_data 路径的 hash 作为命名空间，避免不同目录的记录冲突
        self._namespace = self._generate_namespace()

    def _generate_namespace(self) -> str:
        """生成基于 BOS 路径的命名空间

        使用 raw_data 和 converted 路径生成唯一标识，
        确保不同配置目录的 Redis 记录相互隔离。

        Returns:
            str: 命名空间字符串（路径的简短 hash）
        """
        import hashlib
        # 组合 raw_data 和 converted 路径
        path_str = f"{self.raw_data_prefix}|{self.converted_prefix}"
        # 生成短 hash（取前8位）
        hash_value = hashlib.md5(path_str.encode()).hexdigest()[:8]
        return hash_value

    def get_namespace(self) -> str:
        """获取当前命名空间

        Returns:
            str: 命名空间字符串
        """
        return self._namespace

    def scan_episodes(self) -> List[str]:
        """扫描 BOS 获取所有 episode ID

        Returns:
            List[str]: Episode ID 列表
        """
        logger.info(f"Scanning BOS prefix: {self.raw_data_prefix}")

        episodes = set()
        start_after = None

        # 如果启用增量扫描，从上次位置开始
        if self.scanner_config.get('enable_incremental', True):
            # 使用带命名空间的增量扫描 key，确保不同目录配置相互隔离
            base_incremental_key = self.scanner_config.get('incremental_key', 'bos:last_scanned_key')
            incremental_key = f"{base_incremental_key}:{self._namespace}"
            start_after_bytes = self.task_queue.redis.get(incremental_key)
            if start_after_bytes:
                # 兼容 bytes 和 str 两种情况
                start_after = start_after_bytes.decode('utf-8') if isinstance(start_after_bytes, bytes) else start_after_bytes
                logger.info(f"Resuming scan from: {start_after}")

        max_keys = self.scanner_config.get('max_keys', 1000)
        last_key = start_after
        scan_completed = False  # 标记是否扫描完成

        while True:
            response = self.bos.list_objects(
                prefix=self.raw_data_prefix,
                max_keys=max_keys,
                start_after=last_key
            )

            if 'Contents' not in response or len(response['Contents']) == 0:
                scan_completed = True
                break

            for obj in response['Contents']:
                key = obj['Key']
                episode_id = self._extract_episode_id(key)
                if episode_id:
                    episodes.add(episode_id)

                last_key = key  # 更新最后一个 key

            # 如果没有更多结果，退出循环
            if not response.get('IsTruncated', False):
                scan_completed = True
                break

        # 处理增量扫描位置
        if self.scanner_config.get('enable_incremental', True):
            base_incremental_key = self.scanner_config.get('incremental_key', 'bos:last_scanned_key')
            incremental_key = f"{base_incremental_key}:{self._namespace}"

            if scan_completed:
                # 扫描完成，删除增量位置标记以便下次从头扫描
                # 这样新添加的 episode 不会被永久跳过
                self.task_queue.redis.delete(incremental_key)
                logger.info("Scan completed, reset incremental position for next full scan")
            elif last_key:
                # 扫描未完成（被中断），保存位置以便下次继续
                self.task_queue.redis.set(incremental_key, last_key)
                logger.info(f"Updated scan position to: {last_key}")

        logger.info(f"Found {len(episodes)} episodes")
        return list(episodes)

    def _extract_episode_id(self, key: str) -> Optional[str]:
        """从对象 key 中提取 episode ID

        Args:
            key: BOS 对象 key，例如 "robot/raw_data/quad_arm/episode_0007/images/frame_0001.jpg"

        Returns:
            Optional[str]: Episode ID，如果无法提取返回 None
        """
        # 移除 raw_data_prefix
        if not key.startswith(self.raw_data_prefix):
            return None

        relative_path = key[len(self.raw_data_prefix):]
        parts = relative_path.split('/')

        # 寻找 episode_xxxx 部分
        for part in parts:
            if part.startswith('episode_'):
                return part

        return None

    def check_episode_complete(self, episode_id: str) -> Dict[str, Any]:
        """检查 episode 数据完整性

        适配 BOS 新格式：episode_XXXX/images/ 和 episode_XXXX/joints/

        Args:
            episode_id: Episode ID

        Returns:
            Dict: 检查结果
                - complete: bool, 是否完整
                - reason: str, 如果不完整，原因说明
                - metadata: Dict, episode 元数据
        """
        result = {
            'complete': False,
            'reason': '',
            'metadata': {}
        }

        required_dirs = self.validation_config.get('required_dirs', ['images', 'joints'])
        check_count_match = self.validation_config.get('check_count_match', True)
        stable_time = self.validation_config.get('stable_time', 180)  # 3 分钟
        min_file_count = self.validation_config.get('min_file_count', 1)

        # 1. 检查必需的目录是否存在且非空
        # BOS 新格式：episode_XXXX/images/ 和 episode_XXXX/joints/
        dir_file_counts = {}
        latest_modified_time = None

        for dir_name in required_dirs:
            prefix = f"{self.raw_data_prefix}{episode_id}/{dir_name}/"

            # List 该目录下的所有文件（递归）
            response = self.bos.list_objects(prefix=prefix, max_keys=10000)

            if 'Contents' not in response or len(response['Contents']) == 0:
                result['reason'] = f"Directory '{dir_name}' is missing or empty"
                return result

            # 过滤掉 metadata.json 只计算实际数据文件
            data_files = [
                obj for obj in response['Contents']
                if not obj['Key'].endswith('metadata.json')
            ]

            file_count = len(data_files)

            # 对于 images 目录，需要统计所有子目录下的图片文件
            if dir_name == 'images':
                # 统计图片数量（所有相机的图片总和）
                dir_file_counts[dir_name] = file_count
            else:
                # joints 目录，统计 parquet 文件数量
                dir_file_counts[dir_name] = file_count

            if file_count < min_file_count:
                result['reason'] = f"Directory '{dir_name}' has only {file_count} files (min: {min_file_count})"
                return result

            # 获取最新修改时间
            for obj in response['Contents']:
                last_modified = obj['LastModified']
                if latest_modified_time is None or last_modified > latest_modified_time:
                    latest_modified_time = last_modified

        # 2. 检查文件数量是否匹配（如果启用）
        # 注意：BOS 新格式中，images 包含多个相机的图片，joints 包含 parquet 文件
        # 不能直接比较文件数量，需要更智能的检查
        if check_count_match:
            # 从配置获取参考相机名称，默认为 cam_left
            reference_camera = self.validation_config.get('reference_camera', 'cam_left')

            # 统计 images 目录中参考相机的图片数量
            cam_prefix = f"{self.raw_data_prefix}{episode_id}/images/{reference_camera}/"
            cam_response = self.bos.list_objects(prefix=cam_prefix, max_keys=10000)

            if 'Contents' in cam_response:
                cam_image_count = len([
                    obj for obj in cam_response['Contents']
                    if obj['Key'].endswith('.jpg') or obj['Key'].endswith('.png')
                ])

                # 检查是否有足够的图片
                if cam_image_count < min_file_count:
                    result['reason'] = f"Camera '{reference_camera}' has only {cam_image_count} images (min: {min_file_count})"
                    return result

                # 存储相机图片数量用于元数据
                dir_file_counts[f'{reference_camera}_images'] = cam_image_count
            else:
                result['reason'] = f"Camera '{reference_camera}' directory is missing"
                return result

        # 3. 检查上传是否稳定（最后修改时间超过阈值）
        if latest_modified_time:
            # 确保 latest_modified_time 是 timezone-aware
            # BOS 返回的可能是 naive datetime，需要转换
            if latest_modified_time.tzinfo is None:
                latest_modified_time = latest_modified_time.replace(tzinfo=timezone.utc)

            now = datetime.now(timezone.utc)
            time_diff = (now - latest_modified_time).total_seconds()

            if time_diff < stable_time:
                result['reason'] = f"Still uploading (last modified {time_diff:.0f}s ago, need {stable_time}s)"
                return result

        # 所有检查通过
        result['complete'] = True
        result['metadata'] = {
            'episode_id': episode_id,
            'file_counts': dir_file_counts,
            'last_modified': latest_modified_time.isoformat() if latest_modified_time else None,
            'total_files': sum(dir_file_counts.values())
        }

        return result

    def is_processed(self, episode_id: str) -> bool:
        """检查 episode 是否已处理或正在处理

        检查逻辑（满足任一条件即视为已处理/处理中）：
        1. BOS converted 目录中存在该 episode 的转换结果
        2. Redis 中有该 episode 的处理记录（带命名空间）
        3. 任务已发布到队列但尚未完成（pending 状态）

        Args:
            episode_id: Episode ID

        Returns:
            bool: 是否已处理或正在处理
        """
        # 1. 首先检查 BOS converted 目录是否存在转换结果（最可靠的判断）
        if self.is_converted_on_bos(episode_id):
            return True

        # 2. 检查是否在 pending 集合中（已发布但未完成）
        if self.task_queue.is_pending(self.SOURCE, episode_id):
            logger.debug(f"Episode {episode_id} is pending (already published)")
            return True

        # 3. 检查 Redis 处理完成记录（带命名空间隔离）
        return self.task_queue.is_processed(self.SOURCE, episode_id, namespace=self._namespace)

    def is_converted_on_bos(self, episode_id: str) -> bool:
        """检查 BOS converted 目录中是否存在该 episode 的转换结果

        Args:
            episode_id: Episode ID

        Returns:
            bool: 是否已转换
        """
        # 检查 converted/{episode_id}/ 目录是否存在文件
        converted_episode_prefix = f"{self.converted_prefix}{episode_id}/"
        try:
            response = self.bos.list_objects(prefix=converted_episode_prefix, max_keys=1)
            exists = 'Contents' in response and len(response['Contents']) > 0
            if exists:
                logger.debug(f"Episode {episode_id} already converted on BOS: {converted_episode_prefix}")
            return exists
        except Exception as e:
            logger.warning(f"Failed to check converted status for {episode_id}: {e}")
            return False

    def scan_and_filter(self) -> List[Dict[str, Any]]:
        """扫描并过滤出需要处理的 episode

        Returns:
            List[Dict]: 需要处理的 episode 列表，每个元素包含 episode_id 和 metadata
        """
        all_episodes = self.scan_episodes()
        ready_episodes = []

        logger.info(f"Checking {len(all_episodes)} episodes for completeness...")

        for episode_id in all_episodes:
            # 跳过已处理的
            if self.is_processed(episode_id):
                logger.debug(f"Episode {episode_id} already processed, skipping")
                continue

            # 检查完整性
            check_result = self.check_episode_complete(episode_id)

            if check_result['complete']:
                logger.info(f"✓ Episode {episode_id} is ready: {check_result['metadata']['file_counts']}")
                ready_episodes.append({
                    'episode_id': episode_id,
                    'metadata': check_result['metadata']
                })
            else:
                logger.debug(f"Episode {episode_id} not ready: {check_result['reason']}")

        logger.info(f"Found {len(ready_episodes)} episodes ready for processing")
        return ready_episodes
