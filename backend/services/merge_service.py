"""
合并服务

封装 LeRobot 数据集合并逻辑，复用 scripts/merge_lerobot.py 的核心功能。
"""

import subprocess
import time
import threading
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from backend.models.task import (
    Task, TaskType, TaskStatus, TaskResult,
    CreateMergeTaskRequest
)
from backend.services.database import get_database

logger = logging.getLogger(__name__)


class MergeService:
    """合并服务类"""

    def __init__(self):
        self._running_tasks: Dict[str, threading.Thread] = {}
        self._cancel_flags: Dict[str, bool] = {}
        self.db = get_database()

        # 自动检测项目根目录
        current_file = Path(__file__).resolve()
        self.project_root = current_file.parent.parent.parent

        # 验证项目根目录
        if not (self.project_root / ".pixi").exists():
            # 如果找不到，尝试使用当前工作目录
            cwd = Path.cwd()
            if (cwd / ".pixi").exists():
                self.project_root = cwd
            else:
                logger.warning(
                    f"无法找到项目根目录（.pixi目录）。当前文件: {current_file}, 当前工作目录: {cwd}"
                )
                self.project_root = cwd  # 使用当前工作目录作为后备

    def create_task(self, request: CreateMergeTaskRequest) -> Task:
        """创建合并任务"""
        task = Task(
            type=TaskType.MERGE,
            config=request.model_dump()
        )
        self.db.create(task)
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务信息"""
        return self.db.get(task_id)

    def start_task(self, task_id: str) -> bool:
        """启动合并任务（异步执行）"""
        task = self.db.get(task_id)

        if not task or task.status != TaskStatus.PENDING:
            return False

        task.start()
        self.db.update(task)

        self._cancel_flags[task_id] = False
        thread = threading.Thread(
            target=self._execute_merge,
            args=(task_id,),
            daemon=True
        )
        self._running_tasks[task_id] = thread
        thread.start()

        return True

    def cancel_task(self, task_id: str) -> bool:
        """取消合并任务"""
        task = self.db.get(task_id)

        if not task or task.status != TaskStatus.RUNNING:
            return False

        self._cancel_flags[task_id] = True
        task.cancel()
        self.db.update(task)
        return True

    def _execute_merge(self, task_id: str) -> None:
        """执行合并（在后台线程中运行）"""
        task = self.db.get(task_id)

        if not task:
            return

        config = task.config
        start_time = time.time()

        try:
            task.update_progress(percent=0, message="准备合并...")
            self.db.update(task)

            source_dirs = config['source_dirs']
            output_dir = config['output_dir']

            # 验证源目录
            task.update_progress(percent=5, message=f"验证 {len(source_dirs)} 个源目录...")
            self.db.update(task)

            invalid_sources = []
            for src in source_dirs:
                src_path = Path(src)
                if not src_path.exists():
                    invalid_sources.append(f"{src} (不存在)")
                elif not (src_path / "meta" / "info.json").exists():
                    invalid_sources.append(f"{src} (非LeRobot格式)")

            if invalid_sources:
                raise ValueError(f"无效的源目录: {', '.join(invalid_sources[:3])}{'...' if len(invalid_sources) > 3 else ''}")

            # 检查输出目录
            output_path = Path(output_dir)
            if output_path.exists():
                task.update_progress(percent=10, message="清理现有输出目录...")
                self.db.update(task)
                import shutil
                try:
                    shutil.rmtree(output_path)
                except Exception as e:
                    raise ValueError(f"无法清理输出目录 {output_dir}: {e}")

            # 调用 pixi run merge
            task.update_progress(percent=15, message="开始合并数据集...")
            self.db.update(task)

            cmd = [
                "pixi", "run", "merge",
                "--sources", *source_dirs,
                "--output", output_dir,
                "--state-max-dim", str(config.get('state_max_dim', 14)),
                "--action-max-dim", str(config.get('action_max_dim', 14)),
                "--fps", str(config.get('fps', 25))
            ]

            if config.get('copy_images', False):
                cmd.append("--copy-images")

            logger.info(f"[MergeService] 执行命令: {' '.join(cmd)}")

            process = subprocess.Popen(
                cmd,
                cwd=str(self.project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            # 读取输出并更新进度
            output_lines = []
            for line in process.stdout:
                if self._cancel_flags.get(task_id, False):
                    process.terminate()
                    break

                line = line.strip()
                output_lines.append(line)
                logger.debug(f"[MergeService] {line}")

                # 解析进度信息
                if "验证" in line or "Validating" in line:
                    task.update_progress(percent=20, message=line[:80])
                elif "复制视频" in line or "Copying videos" in line:
                    task.update_progress(percent=40, message=line[:80])
                elif "处理数据" in line or "Processing data" in line or "copy_data" in line:
                    task.update_progress(percent=60, message=line[:80])
                elif "保存元数据" in line or "Saving metadata" in line:
                    task.update_progress(percent=80, message=line[:80])
                elif "完成" in line or "Complete" in line or "Success" in line:
                    task.update_progress(percent=95, message=line[:80])

                self.db.update(task)

            process.wait()
            elapsed = time.time() - start_time

            if self._cancel_flags.get(task_id, False):
                task.cancel()
            elif process.returncode == 0:
                # 读取合并后的统计信息
                details = {
                    "source_count": len(source_dirs),
                    "output_dir": output_dir
                }
                info_path = Path(output_dir) / "meta" / "info.json"
                if info_path.exists():
                    with open(info_path) as f:
                        info = json.load(f)
                        details.update({
                            "total_episodes": info.get("total_episodes", 0),
                            "total_frames": info.get("total_frames", 0),
                            "total_videos": info.get("total_videos", 0)
                        })

                result = TaskResult(
                    success=True,
                    elapsed_seconds=elapsed,
                    details=details
                )
                task.complete(result)
                logger.info(f"[MergeService] 合并完成: {details}")
            else:
                error_output = '\n'.join(output_lines[-10:])  # 最后10行
                result = TaskResult(
                    success=False,
                    elapsed_seconds=elapsed,
                    error_message=f"合并失败 (返回码: {process.returncode})\n{error_output}"
                )
                task.complete(result)
                logger.error(f"[MergeService] 合并失败: {error_output}")

        except Exception as e:
            elapsed = time.time() - start_time
            result = TaskResult(
                success=False,
                elapsed_seconds=elapsed,
                error_message=str(e)
            )
            task.complete(result)
            logger.exception(f"[MergeService] 合并异常: {e}")

        finally:
            self.db.update(task)
            self._running_tasks.pop(task_id, None)
            self._cancel_flags.pop(task_id, None)


# 单例
_merge_service: Optional[MergeService] = None


def get_merge_service() -> MergeService:
    """获取合并服务单例"""
    global _merge_service
    if _merge_service is None:
        _merge_service = MergeService()
    return _merge_service
