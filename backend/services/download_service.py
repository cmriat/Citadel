"""
下载服务

封装mc命令执行，提供异步下载功能和进度回调。
复用 cli/utils/mc_executor.py 的核心逻辑。
"""

import asyncio
import subprocess
import re
import time
import os
from pathlib import Path
from typing import Optional, Callable, Tuple
from datetime import datetime
import threading

from backend.config import settings
from backend.models.task import (
    Task, TaskType, TaskStatus, TaskResult,
    CreateDownloadTaskRequest
)
from backend.services.database import get_database


class DownloadService:
    """下载服务"""

    def __init__(self, mc_path: str = None):
        # 使用统一配置获取 mc 路径
        if mc_path is None:
            mc_path = settings.get_mc_path()

        self.mc_path = Path(mc_path)
        self._running_tasks: dict[str, threading.Thread] = {}
        self._cancel_flags: dict[str, bool] = {}

    def check_mc(self) -> Tuple[bool, str]:
        """检查mc工具是否可用"""
        if not self.mc_path.exists():
            return False, f"mc命令未找到: {self.mc_path}"

        try:
            result = subprocess.run(
                [str(self.mc_path), "--version"],
                capture_output=True,
                text=True,
                timeout=settings.TIMEOUT_MC_CHECK
            )
            if result.returncode == 0:
                return True, result.stdout.strip()
            return False, result.stderr
        except Exception as e:
            return False, str(e)

    def check_connection(self) -> Tuple[bool, str]:
        """检查BOS连接"""
        try:
            # 使用统一配置的 BOS 测试路径
            test_path = f"{settings.BOS_ALIAS}/{settings.BOS_TEST_PATH}"
            result = subprocess.run(
                [str(self.mc_path), "ls", test_path],
                capture_output=True,
                text=True,
                timeout=settings.TIMEOUT_MC_CHECK
            )
            if result.returncode == 0:
                return True, ""
            return False, f"连接失败: {result.stderr}"
        except subprocess.TimeoutExpired:
            return False, "连接超时"
        except Exception as e:
            return False, f"连接异常: {str(e)}"

    def scan_bos(self, bos_path: str, file_pattern: str = "*.h5") -> dict:
        """扫描BOS路径下的文件

        Args:
            bos_path: BOS路径 (格式: bos:/bucket/path/ 或 bucket/path/)
            file_pattern: 文件匹配模式

        Returns:
            dict: {
                "ready": bool,
                "file_count": int,
                "files": list[str],
                "error": str | None
            }
        """
        try:
            # 标准化路径
            if bos_path.startswith("bos:/"):
                bos_path = bos_path[5:]  # 移除 "bos:/" 前缀
            bos_path = bos_path.rstrip("/")

            # 执行 mc ls 命令
            result = subprocess.run(
                [str(self.mc_path), "ls", f"{settings.BOS_ALIAS}/{bos_path}/"],
                capture_output=True,
                text=True,
                timeout=settings.TIMEOUT_BOS_SCAN
            )

            if result.returncode != 0:
                return {
                    "ready": False,
                    "file_count": 0,
                    "files": [],
                    "error": result.stderr.strip() or "Failed to list BOS path"
                }

            # 解析输出，提取 .h5 文件
            files = []
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                # mc ls 输出格式: [date] [time] [size] filename
                parts = line.split()
                if len(parts) >= 4:
                    filename = parts[-1]
                    if filename.endswith(".h5"):
                        files.append(filename)

            return {
                "ready": len(files) > 0,
                "file_count": len(files),
                "files": files[:20],  # 限制返回数量
                "error": None
            }

        except subprocess.TimeoutExpired:
            return {
                "ready": False,
                "file_count": 0,
                "files": [],
                "error": "Scan timeout"
            }
        except Exception as e:
            return {
                "ready": False,
                "file_count": 0,
                "files": [],
                "error": str(e)
            }

    def create_task(self, request: CreateDownloadTaskRequest) -> Task:
        """创建下载任务"""
        task = Task(
            type=TaskType.DOWNLOAD,
            config=request.model_dump()
        )

        # 保存到数据库
        db = get_database()
        db.create(task)

        return task

    def start_task(self, task_id: str) -> bool:
        """启动下载任务（异步执行）"""
        db = get_database()
        task = db.get(task_id)

        if not task:
            return False

        if task.status != TaskStatus.PENDING:
            return False

        # 标记任务开始
        task.start()
        db.update(task)

        # 启动后台线程执行下载
        self._cancel_flags[task_id] = False
        thread = threading.Thread(
            target=self._execute_download,
            args=(task_id,),
            daemon=True
        )
        self._running_tasks[task_id] = thread
        thread.start()

        return True

    def cancel_task(self, task_id: str) -> bool:
        """取消下载任务"""
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

    def _execute_download(self, task_id: str) -> None:
        """执行下载（在后台线程中运行）"""
        db = get_database()
        task = db.get(task_id)

        if not task:
            return

        config = task.config
        start_time = time.time()
        downloaded_files: list[str] = []

        try:
            # 创建本地目录
            local_path = Path(config['local_path'])
            local_path.mkdir(parents=True, exist_ok=True)

            # 构建mc命令
            mc_path = config.get('mc_path', str(self.mc_path))
            source = f"{settings.BOS_ALIAS}/{config['bos_path']}"
            concurrency = config.get('concurrency', settings.DEFAULT_CONCURRENCY)

            cmd = [
                mc_path,
                "mirror",
                f"--max-workers={concurrency}",
                source,
                str(local_path)
            ]

            # 启动进程
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            # 读取输出并更新进度
            for line in iter(process.stdout.readline, ''):
                # 检查取消标志
                if self._cancel_flags.get(task_id, False):
                    process.terminate()
                    break

                line = line.strip()
                if not line:
                    continue

                # 解析文件完成信息
                filename = self._parse_mc_output(line)
                if filename:
                    downloaded_files.append(filename)

                    # 更新进度
                    task.update_progress(
                        current_file=filename,
                        completed_files=len(downloaded_files),
                        message=f"已下载: {filename}"
                    )
                    db.update(task)

            # 等待进程结束
            return_code = process.wait()
            elapsed = time.time() - start_time

            # mc mirror 输出的是开始下载的文件，而非完成的文件
            # 等进程结束后，扫描目录获取实际下载的文件列表
            actual_files = [f.name for f in local_path.glob("*.h5") if f.is_file()]
            if actual_files:
                downloaded_files = actual_files  # 使用实际文件列表

            # 计算总大小
            total_size_mb = self._calculate_total_size(local_path, downloaded_files)

            # 更新结果
            # mc mirror 在文件已存在/跳过时可能返回非零码，但实际下载成功
            # 判断逻辑：有完成的文件 或 返回码为0 均视为成功
            if self._cancel_flags.get(task_id, False):
                task.cancel()
            elif return_code == 0 or len(downloaded_files) > 0:
                task.complete(TaskResult(
                    success=True,
                    total_files=len(downloaded_files),
                    completed_files=len(downloaded_files),
                    elapsed_seconds=elapsed,
                    details={
                        'total_size_mb': total_size_mb,
                        'speed_mbps': total_size_mb / elapsed if elapsed > 0 else 0,
                        'files': downloaded_files,
                        'mc_return_code': return_code  # 保留原始返回码用于调试
                    }
                ))
            else:
                task.complete(TaskResult(
                    success=False,
                    total_files=0,
                    completed_files=0,
                    elapsed_seconds=elapsed,
                    error_message=f"mc命令返回错误码: {return_code}，未下载任何文件"
                ))

            db.update(task)

        except Exception as e:
            elapsed = time.time() - start_time
            task.complete(TaskResult(
                success=False,
                elapsed_seconds=elapsed,
                error_message=f"下载异常: {str(e)}"
            ))
            db.update(task)

        finally:
            # 清理
            self._running_tasks.pop(task_id, None)
            self._cancel_flags.pop(task_id, None)

    def _parse_mc_output(self, line: str) -> Optional[str]:
        """解析mc输出，提取文件名"""
        # mc mirror格式: `source` -> `dest`
        pattern = r'`[^`]+/([\w\-\.]+\.h5)`\s*->\s*`([^`]+)`'
        match = re.search(pattern, line)
        if match:
            return match.group(1)
        return None

    def _calculate_total_size(self, local_path: Path, files: list[str]) -> float:
        """计算下载文件总大小（MB）"""
        total = 0.0
        for filename in files:
            file_path = local_path / filename
            if file_path.exists():
                total += file_path.stat().st_size / (1024 * 1024)
        return total


# 全局服务实例
_download_service: Optional[DownloadService] = None


def get_download_service() -> DownloadService:
    """获取下载服务单例"""
    global _download_service
    if _download_service is None:
        _download_service = DownloadService()
    return _download_service
