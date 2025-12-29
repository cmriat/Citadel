"""
上传服务

提供LeRobot数据上传到BOS的功能。
"""

import os
import subprocess
import threading
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime
from pathlib import Path

from backend.models.task import (
    Task, TaskType, TaskStatus, TaskResult,
    CreateUploadTaskRequest
)
from backend.services.database import get_database


class UploadService:
    """上传服务类"""

    def __init__(self, mc_path: str = "/home/maozan/mc"):
        self.mc_path = mc_path
        self.db = get_database()
        self._running_tasks: Dict[str, subprocess.Popen] = {}

    def check_mc(self) -> Tuple[bool, str]:
        """检查mc工具是否可用"""
        try:
            result = subprocess.run(
                [self.mc_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.strip().split('\n')[0]
                return True, version
            return False, result.stderr
        except FileNotFoundError:
            return False, f"mc not found at {self.mc_path}"
        except Exception as e:
            return False, str(e)

    def scan_dirs(self, base_dir: str) -> List[Dict[str, Any]]:
        """扫描可上传的LeRobot目录"""
        base_path = Path(base_dir)
        if not base_path.exists():
            return []

        dirs = []
        # 查找包含 meta/info.json 的目录（LeRobot格式标志）
        for item in base_path.iterdir():
            if item.is_dir():
                meta_file = item / "meta" / "info.json"
                if meta_file.exists():
                    # 计算目录大小和文件数
                    size = 0
                    file_count = 0
                    for root, _, files in os.walk(item):
                        for f in files:
                            file_path = Path(root) / f
                            size += file_path.stat().st_size
                            file_count += 1

                    dirs.append({
                        "path": str(item),
                        "name": item.name,
                        "size": size,
                        "file_count": file_count
                    })

        return dirs

    def create_task(self, request: CreateUploadTaskRequest) -> Task:
        """创建上传任务"""
        task = Task(
            type=TaskType.UPLOAD,
            config=request.model_dump()
        )
        self.db.create(task)
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self.db.get(task_id)

    def start_task(self, task_id: str) -> bool:
        """启动上传任务"""
        task = self.db.get(task_id)
        if not task or task.status != TaskStatus.PENDING:
            return False

        # 标记任务开始
        task.start()
        self.db.update(task)

        # 在后台线程中执行上传
        thread = threading.Thread(
            target=self._run_upload,
            args=(task_id,),
            daemon=True
        )
        thread.start()

        return True

    def _run_upload(self, task_id: str):
        """执行上传任务（后台线程）"""
        task = self.db.get(task_id)
        if not task:
            return

        config = task.config
        local_dir = config["local_dir"]
        bos_path = config["bos_path"]
        concurrency = config.get("concurrency", 10)
        mc_path = config.get("mc_path", self.mc_path)

        start_time = datetime.now()

        try:
            # 更新进度
            task.update_progress(percent=0, message="Starting upload...")
            self.db.update(task)

            # 构建mc mirror命令（上传是mirror的反向）
            # 确保 bos_path 有正确的前缀
            if not bos_path.startswith("bos/"):
                bos_path = f"bos/{bos_path}"

            cmd = [
                mc_path,
                "mirror",
                "--overwrite",
                f"--max-workers={concurrency}",
                local_dir,
                bos_path
            ]

            # 执行命令
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            self._running_tasks[task_id] = process

            # 读取输出并更新进度
            total_bytes = 0
            uploaded_bytes = 0

            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue

                # 解析mc mirror输出
                if "Total:" in line:
                    # 尝试解析总大小
                    pass
                elif "/" in line and ("B" in line or "KB" in line or "MB" in line or "GB" in line):
                    # 进度行
                    task.update_progress(message=line[:100])
                    self.db.update(task)

            process.wait()

            # 清理
            del self._running_tasks[task_id]

            elapsed = (datetime.now() - start_time).total_seconds()

            if process.returncode == 0:
                result = TaskResult(
                    success=True,
                    elapsed_seconds=elapsed,
                    details={"local_dir": local_dir, "bos_path": bos_path}
                )
                task.complete(result)
            else:
                result = TaskResult(
                    success=False,
                    elapsed_seconds=elapsed,
                    error_message=f"Upload failed with code {process.returncode}"
                )
                task.complete(result)

        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            result = TaskResult(
                success=False,
                elapsed_seconds=elapsed,
                error_message=str(e)
            )
            task.complete(result)

        finally:
            self.db.update(task)

    def cancel_task(self, task_id: str) -> bool:
        """取消上传任务"""
        task = self.db.get(task_id)
        if not task:
            return False

        if task.status not in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            return False

        # 如果正在运行，终止进程
        if task_id in self._running_tasks:
            process = self._running_tasks[task_id]
            process.terminate()
            del self._running_tasks[task_id]

        task.cancel()
        self.db.update(task)
        return True


# 单例
_upload_service: Optional[UploadService] = None


def get_upload_service() -> UploadService:
    """获取上传服务单例"""
    global _upload_service
    if _upload_service is None:
        _upload_service = UploadService()
    return _upload_service
