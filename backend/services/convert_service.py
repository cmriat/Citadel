"""
转换服务

封装HDF5转换逻辑，提供异步批量转换功能。
复用 scripts/convert.py 和 cli/convert_cli.py 的核心逻辑。
"""

import subprocess
import time
from pathlib import Path
from typing import Optional, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from backend.models.task import (
    Task, TaskType, TaskStatus, TaskResult,
    CreateConvertTaskRequest
)
from backend.services.database import get_database


class ConvertService:
    """转换服务"""

    def __init__(self):
        self._running_tasks: dict[str, threading.Thread] = {}
        self._cancel_flags: dict[str, bool] = {}

    def create_task(self, request: CreateConvertTaskRequest) -> Task:
        """创建转换任务"""
        task = Task(
            type=TaskType.CONVERT,
            config=request.model_dump()
        )

        # 保存到数据库
        db = get_database()
        db.create(task)

        return task

    def start_task(self, task_id: str) -> bool:
        """启动转换任务（异步执行）"""
        db = get_database()
        task = db.get(task_id)

        if not task:
            return False

        if task.status != TaskStatus.PENDING:
            return False

        # 标记任务开始
        task.start()
        db.update(task)

        # 启动后台线程执行转换
        self._cancel_flags[task_id] = False
        thread = threading.Thread(
            target=self._execute_convert,
            args=(task_id,),
            daemon=True
        )
        self._running_tasks[task_id] = thread
        thread.start()

        return True

    def cancel_task(self, task_id: str) -> bool:
        """取消转换任务"""
        db = get_database()
        task = db.get(task_id)

        if not task:
            return False

        if task.status != TaskStatus.RUNNING:
            return False

        # 设置取消标志
        self._cancel_flags[task_id] = True

        # 更新任务状态
        task.cancel()
        db.update(task)

        return True

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务信息"""
        db = get_database()
        return db.get(task_id)

    def scan_files(self, input_dir: str, file_pattern: str = "episode_*.h5") -> List[str]:
        """扫描输入目录中的HDF5文件"""
        input_path = Path(input_dir)
        if not input_path.exists():
            return []

        files = sorted(input_path.glob(file_pattern))
        return [f.name for f in files]

    def _execute_convert(self, task_id: str) -> None:
        """执行转换（在后台线程中运行）"""
        db = get_database()
        task = db.get(task_id)

        if not task:
            return

        config = task.config
        start_time = time.time()

        results: List[Tuple[str, bool, str, float]] = []
        completed_count = 0
        failed_count = 0

        try:
            # 扫描文件
            input_path = Path(config['input_dir'])
            output_path = Path(config['output_dir'])
            file_pattern = config.get('file_pattern', 'episode_*.h5')

            hdf5_files = sorted(input_path.glob(file_pattern))

            if len(hdf5_files) == 0:
                task.complete(TaskResult(
                    success=False,
                    error_message=f"未找到匹配 '{file_pattern}' 的HDF5文件"
                ))
                db.update(task)
                return

            # 更新总文件数
            task.progress.total_files = len(hdf5_files)
            db.update(task)

            # 创建输出目录
            output_path.mkdir(parents=True, exist_ok=True)

            # 并发转换
            parallel_jobs = config.get('parallel_jobs', 4)

            with ThreadPoolExecutor(max_workers=parallel_jobs) as executor:
                # 提交所有任务
                future_to_file = {
                    executor.submit(
                        self._convert_single_file,
                        hdf5_file,
                        output_path,
                        config
                    ): hdf5_file
                    for hdf5_file in hdf5_files
                }

                # 处理完成的任务
                for future in as_completed(future_to_file):
                    # 检查取消标志
                    if self._cancel_flags.get(task_id, False):
                        executor.shutdown(wait=False, cancel_futures=True)
                        break

                    hdf5_file = future_to_file[future]

                    try:
                        success, error_msg, elapsed = future.result()
                        results.append((hdf5_file.name, success, error_msg, elapsed))

                        if success:
                            completed_count += 1
                        else:
                            failed_count += 1

                        # 更新进度
                        total_processed = completed_count + failed_count
                        percent = (total_processed / len(hdf5_files)) * 100

                        task.update_progress(
                            percent=percent,
                            current_file=hdf5_file.name,
                            completed_files=completed_count,
                            failed_files=failed_count,
                            message=f"{'成功' if success else '失败'}: {hdf5_file.name}"
                        )
                        db.update(task)

                    except Exception as e:
                        failed_count += 1
                        results.append((hdf5_file.name, False, str(e), 0))

            # 计算总耗时
            elapsed = time.time() - start_time

            # 更新结果
            if self._cancel_flags.get(task_id, False):
                task.cancel()
            else:
                success = failed_count == 0
                task.complete(TaskResult(
                    success=success,
                    total_files=len(hdf5_files),
                    completed_files=completed_count,
                    failed_files=failed_count,
                    elapsed_seconds=elapsed,
                    error_message=None if success else f"{failed_count}个文件转换失败",
                    details={
                        'results': [
                            {
                                'file': r[0],
                                'success': r[1],
                                'error': r[2] if not r[1] else None,
                                'elapsed': r[3]
                            }
                            for r in results
                        ]
                    }
                ))

            db.update(task)

        except Exception as e:
            elapsed = time.time() - start_time
            task.complete(TaskResult(
                success=False,
                elapsed_seconds=elapsed,
                error_message=f"转换异常: {str(e)}"
            ))
            db.update(task)

        finally:
            # 清理
            self._running_tasks.pop(task_id, None)
            self._cancel_flags.pop(task_id, None)

    def _convert_single_file(
        self,
        hdf5_file: Path,
        output_base_dir: Path,
        config: dict
    ) -> Tuple[bool, str, float]:
        """转换单个HDF5文件"""
        start_time = time.time()
        episode_name = hdf5_file.stem
        output_episode_dir = output_base_dir / episode_name

        # 使用pixi环境的Python绝对路径
        PYTHON_PATH = "/data/maozan/code/Citadel_release/.pixi/envs/default/bin/python3"

        # 构建命令
        cmd = [
            PYTHON_PATH, "scripts/convert.py",
            "--hdf5-path", str(hdf5_file),
            "--output-dir", str(output_episode_dir),
            "--robot-type", config.get('robot_type', 'airbot_play'),
            "--fps", str(config.get('fps', 25)),
            "--task", config.get('task', 'Fold the laundry')
        ]

        try:
            # 继承当前进程的环境变量（包含pixi环境PATH）
            import os
            env = os.environ.copy()

            result = subprocess.run(
                cmd,
                cwd="/home/maozan/code/Citadel_release",
                capture_output=True,
                text=True,
                timeout=300,  # 5分钟超时
                env=env
            )

            elapsed = time.time() - start_time

            if result.returncode == 0:
                return (True, "", elapsed)
            else:
                error_lines = result.stderr.split('\n')[-10:]
                error_msg = '\n'.join(error_lines)
                return (False, error_msg, elapsed)

        except subprocess.TimeoutExpired:
            elapsed = time.time() - start_time
            return (False, "转换超时（>5分钟）", elapsed)
        except Exception as e:
            elapsed = time.time() - start_time
            return (False, f"异常: {str(e)}", elapsed)


# 全局服务实例
_convert_service: Optional[ConvertService] = None


def get_convert_service() -> ConvertService:
    """获取转换服务单例"""
    global _convert_service
    if _convert_service is None:
        _convert_service = ConvertService()
    return _convert_service
