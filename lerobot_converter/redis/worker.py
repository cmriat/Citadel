"""Redis Worker 核心逻辑"""

from pathlib import Path

from ..core.task import ConversionTask
from ..pipeline.converter import LeRobotConverter
from ..pipeline.config import load_config
from .task_queue import TaskQueue


class RedisWorker:
    """Redis Worker 核心处理逻辑

    职责：
    - 处理单个转换任务（纯业务逻辑）
    - 不直接与 Redis 交互（由 TaskQueue 负责）
    """

    def __init__(self, output_pattern: str, config_template: str, default_strategy: str):
        """初始化 Worker

        Args:
            output_pattern: 输出路径模板
            config_template: 转换配置模板路径
            default_strategy: 默认对齐策略
        """
        self.output_pattern = output_pattern
        self.config_template = config_template
        self.default_strategy = default_strategy

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

        try:
            # 3. 生成输出路径
            output_path = self.output_pattern.format(
                source=source,
                episode_id=episode_id,
                strategy=strategy
            )

            # 4. 加载转换配置
            converter_config = load_config(self.config_template)

            # 5. 修改输出路径和数据集名称
            converter_config['output']['base_path'] = output_path
            converter_config['output']['dataset_name'] = f"{source}_{episode_id}"

            # 6. 应用策略覆盖
            if task.config_overrides:
                converter_config.update(task.config_overrides)

            # 7. 创建转换器并执行
            converter = LeRobotConverter(converter_config)
            converter.convert(episode_id=episode_id)

            # 8. 标记完成
            task_queue.mark_processed(source, episode_id)
            task_queue.record_stats(source, 'completed')
            task_queue.save_episode_info(source, episode_id, 'completed')

            print(f"✓ Completed: {source}/{episode_id}")
            return True

        except Exception as e:
            # 9. 记录失败
            error_msg = str(e)
            task_queue.record_stats(source, 'failed')
            task_queue.save_episode_info(source, episode_id, 'failed', error_msg)

            print(f"✗ Failed: {source}/{episode_id} - {error_msg}")

            # 10. 失败任务移到失败队列
            task_queue.move_to_failed(task_data)

            return False
