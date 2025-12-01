"""Redis Worker 核心逻辑"""

import os
import logging
import tempfile
from pathlib import Path
from typing import Optional

from ..core.task import ConversionTask
from ..pipeline.converter import LeRobotConverter
from ..pipeline.config import load_config
from .task_queue import TaskQueue

logger = logging.getLogger(__name__)


class RedisWorker:
    """Redis Worker 核心处理逻辑

    职责：
    - 处理单个转换任务（纯业务逻辑）
    - 不直接与 Redis 交互（由 TaskQueue 负责）
    - 支持本地和 BOS 数据源
    """

    def __init__(
        self,
        output_pattern: str,
        config_template: str,
        default_strategy: str,
        bos_config_path: Optional[str] = None
    ):
        """初始化 Worker

        Args:
            output_pattern: 输出路径模板
            config_template: 转换配置模板路径
            default_strategy: 默认对齐策略
            bos_config_path: BOS 配置文件路径（可选，如果需要处理 BOS 数据源）
        """
        self.output_pattern = output_pattern
        self.config_template = config_template
        self.default_strategy = default_strategy
        self.bos_config_path = bos_config_path

        # 延迟加载 BOS 模块（只在需要时加载）
        self._bos_client = None
        self._bos_downloader = None
        self._bos_uploader = None

        # 获取临时目录配置（用于BOS转换）
        self._temp_dir = None
        if bos_config_path:
            self._temp_dir = self._get_temp_dir_from_config()

    def _get_temp_dir_from_config(self) -> Path:
        """从BOS配置文件读取临时目录配置

        Returns:
            Path: 临时目录路径
        """
        import yaml

        try:
            with open(self.bos_config_path, 'r') as f:
                config = yaml.safe_load(f)

            # 读取temp_dir配置
            temp_dir_config = config.get('bos', {}).get('download', {}).get('temp_dir')

            if temp_dir_config and temp_dir_config.startswith('${') and temp_dir_config.endswith('}'):
                # 处理环境变量：${VAR_NAME}
                env_var = temp_dir_config[2:-1]
                temp_dir_str = os.environ.get(env_var)
                if not temp_dir_str:
                    # 环境变量未设置，使用系统默认temp
                    temp_dir_str = os.path.join(tempfile.gettempdir(), 'lerobot_bos')
            elif temp_dir_config:
                temp_dir_str = temp_dir_config
            else:
                # 配置未设置，使用系统默认temp
                temp_dir_str = os.path.join(tempfile.gettempdir(), 'lerobot_bos')

            return Path(temp_dir_str).resolve()
        except Exception as e:
            print(f"⚠️  Failed to read temp_dir from config: {e}, using default")
            return Path(tempfile.gettempdir()) / 'lerobot_bos'

    def _init_bos_modules(self):
        """初始化 BOS 模块（延迟加载）"""
        if self._bos_client is None and self.bos_config_path:
            from ..bos import BosClient, BosDownloader, BosUploader

            self._bos_client = BosClient(self.bos_config_path)
            self._bos_downloader = BosDownloader(self._bos_client)
            self._bos_uploader = BosUploader(self._bos_client)

            print("✓ BOS modules initialized")

    def process_task(self, task_data: dict, task_queue: TaskQueue) -> bool:
        """处理单个转换任务

        Args:
            task_data: 任务字典
            task_queue: TaskQueue 实例（用于记录状态）

        Returns:
            是否成功处理
        """
        # 1. 解析任务
        task = ConversionTask.from_dict(task_data)
        episode_id = task.episode_id
        source = task.source
        strategy = task.strategy.value

        # 2. 检查是否已处理
        if task_queue.is_processed(source, episode_id):
            print(f"⊘ Already processed: {source}/{episode_id}")
            return True

        print(f"🔄 Processing: {source}/{episode_id} (strategy: {strategy})")

        # 3. 判断数据源类型
        is_bos_source = (source == 'bos')

        local_joints_path = None
        local_images_path = None
        temp_output_dir = None

        try:
            # 4. 如果是 BOS 数据源，先下载数据
            if is_bos_source:
                print(f"📥 Downloading from BOS: {episode_id}")
                self._init_bos_modules()

                task_path = self._bos_downloader.download_episode(episode_id)
                if not task_path:
                    raise Exception("Failed to download episode from BOS")

                # 新格式下 data_path 和 images_path 相同
                local_joints_path = local_images_path = task_path

                print(f"✓ Downloaded:")
                print(f"  Task directory: {task_path}")
                print(f"  Episode directory: {task_path / episode_id}")

                # 使用配置的临时输出目录
                if self._temp_dir:
                    temp_output_dir = self._temp_dir / f"converted_{episode_id}"
                else:
                    # Fallback：使用系统默认temp
                    temp_output_dir = Path(tempfile.gettempdir()) / 'lerobot_bos' / f"converted_{episode_id}"

                # 生成临时输出路径
                output_path = str(temp_output_dir)
            else:
                # 本地数据源，使用正常输出路径
                output_path = self.output_pattern.format(
                    source=source,
                    episode_id=episode_id,
                    strategy=strategy
                )

            # 5. 加载转换配置
            converter_config = load_config(self.config_template)

            # 6. 修改输出路径和数据集名称
            converter_config['output']['base_path'] = output_path
            converter_config['output']['dataset_name'] = f"{source}_{episode_id}"

            # 7. 如果是 BOS 数据源，修改输入路径
            if is_bos_source and local_joints_path and local_images_path:
                # 设置 converter 的输入路径
                if 'input' not in converter_config:
                    converter_config['input'] = {}
                converter_config['input']['data_path'] = str(local_joints_path)
                converter_config['input']['images_path'] = str(local_images_path)

            # 8. 应用策略覆盖
            if task.config_overrides:
                converter_config.update(task.config_overrides)

            # 9. 创建转换器并执行
            print(f"🔧 Converting episode {episode_id}...")
            converter = LeRobotConverter(converter_config)
            converter.convert(episode_id=episode_id)

            # 10. 如果是 BOS 数据源，上传结果
            if is_bos_source and temp_output_dir:
                print(f"📤 Uploading results to BOS...")
                upload_success = self._bos_uploader.upload_episode(
                    local_dir=temp_output_dir,
                    episode_id=episode_id,
                    task_name=None  # 可以从配置中获取
                )

                if not upload_success:
                    raise Exception("Failed to upload results to BOS")

                print(f"✓ Uploaded to BOS")

            # 11. 标记完成
            task_queue.mark_processed(source, episode_id)
            task_queue.record_stats(source, 'completed')
            task_queue.save_episode_info(source, episode_id, 'completed')

            print(f"✓ Completed: {source}/{episode_id}")
            return True

        except KeyboardInterrupt:
            # 用户中断：向上传播，不记录为失败
            logger.info(f"⊘ User interrupted while processing {source}/{episode_id}")
            raise

        except Exception as e:
            # 其他异常：记录完整堆栈并标记为失败
            logger.exception(f"✗ Failed: {source}/{episode_id}")
            task_queue.record_stats(source, 'failed')
            task_queue.save_episode_info(source, episode_id, 'failed', str(e))
            task_queue.move_to_failed(task_data)

            print(f"✗ Failed: {source}/{episode_id} - {e}")
            return False

        finally:
            # 14. 清理临时文件（如果是 BOS 数据源）
            if is_bos_source:
                if local_joints_path or local_images_path:
                    print(f"🧹 Cleaning up downloaded files...")
                    self._bos_downloader.cleanup(episode_id)

                if temp_output_dir and temp_output_dir.exists():
                    print(f"🧹 Cleaning up temporary output...")
                    import shutil
                    shutil.rmtree(temp_output_dir)
