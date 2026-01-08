"""
上传服务

提供LeRobot数据上传到BOS的功能。
"""

import json
import logging
import os
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

from backend.models.task import (
    Task, TaskType, TaskStatus, TaskResult,
    CreateUploadTaskRequest
)
from backend.services.database import get_database


class UploadService:
    """上传服务类"""

    def __init__(self, mc_path: str = "/home/jovyan/mc"):
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

    def scan_episodes(self, base_dir: str, include_thumbnails: bool = True) -> List[Dict[str, Any]]:
        """扫描 LeRobot 目录，返回 episode 详情和缩略图预览

        Args:
            base_dir: LeRobot 数据目录
            include_thumbnails: 是否包含缩略图（为 False 时速度更快）
        """
        import json

        base_path = Path(base_dir)
        if not base_path.exists():
            return []

        # 第一步：快速收集 episode 元数据
        episodes_data = []
        for item in sorted(base_path.iterdir()):
            if not item.is_dir():
                continue

            meta_file = item / "meta" / "info.json"
            if not meta_file.exists():
                continue

            # 读取 meta/info.json 获取帧数和相机信息
            try:
                with open(meta_file, 'r') as f:
                    info = json.load(f)
            except Exception:
                continue

            frame_count = info.get("total_frames", 0)

            # 计算目录大小（简化：只统计视频文件）
            size = 0
            videos_dir = item / "videos"
            if videos_dir.exists():
                for video_file in videos_dir.rglob("*.mp4"):
                    try:
                        size += video_file.stat().st_size
                    except Exception:
                        pass

            # 查找 env 相机视频
            env_video = None
            chunk_dir = item / "videos" / "chunk-000"
            if chunk_dir.exists():
                for cam_dir in chunk_dir.iterdir():
                    if cam_dir.is_dir() and "cam_env" in cam_dir.name:
                        for video_file in cam_dir.glob("*.mp4"):
                            env_video = video_file
                            break
                        break

            episodes_data.append({
                "name": item.name,
                "path": str(item),
                "frame_count": frame_count,
                "size": size,
                "env_video": str(env_video) if env_video else None,
                "thumbnails": []
            })

        # 第二步：并行提取缩略图
        if include_thumbnails and episodes_data:
            # 使用线程池并行处理
            max_workers = min(8, len(episodes_data))  # 最多 8 个线程

            def extract_for_episode(ep_data: dict) -> dict:
                if ep_data.get("env_video"):
                    try:
                        ep_data["thumbnails"] = self.extract_thumbnails(ep_data["env_video"])
                    except Exception as e:
                        print(f"[UploadService] Thumbnail extraction failed for {ep_data['name']}: {e}")
                return ep_data

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(extract_for_episode, ep): ep for ep in episodes_data}
                for future in as_completed(futures):
                    try:
                        future.result()  # 结果已就地更新
                    except Exception as e:
                        print(f"[UploadService] Thread error: {e}")

        # 清理临时字段并返回
        for ep in episodes_data:
            ep.pop("env_video", None)

        return episodes_data

    def extract_thumbnails(self, video_path: str, size: tuple = (160, 120)) -> List[str]:
        """从视频提取 4 帧缩略图（第1帧、1/3帧、2/3帧、最后帧）"""
        import av
        import base64
        from io import BytesIO
        from PIL import Image

        try:
            container = av.open(video_path)
            stream = container.streams.video[0]

            # 获取总帧数
            total_frames = stream.frames
            if total_frames <= 0:
                # 如果无法获取帧数，尝试通过时长计算
                duration = stream.duration
                if duration and stream.time_base:
                    fps = float(stream.average_rate) if stream.average_rate else 25
                    total_frames = int(duration * stream.time_base * fps)

            if total_frames <= 0:
                total_frames = 100  # 默认假设 100 帧

            # 计算要提取的帧索引
            frame_indices = [
                0,
                max(0, total_frames // 3),
                max(0, total_frames * 2 // 3),
                max(0, total_frames - 1)
            ]

            thumbnails = []
            frames_collected = set()

            # 重置容器
            container.seek(0)

            frame_idx = 0
            for frame in container.decode(video=0):
                if frame_idx in frame_indices and frame_idx not in frames_collected:
                    img = frame.to_image()
                    img.thumbnail(size)

                    buffer = BytesIO()
                    img.save(buffer, format='JPEG', quality=70)
                    thumbnails.append(
                        f"data:image/jpeg;base64,{base64.b64encode(buffer.getvalue()).decode()}"
                    )
                    frames_collected.add(frame_idx)

                    if len(frames_collected) >= 4:
                        break

                frame_idx += 1

            container.close()

            # 如果没收集够 4 帧，用最后一帧填充
            while len(thumbnails) < 4 and thumbnails:
                thumbnails.append(thumbnails[-1])

            return thumbnails

        except Exception as e:
            print(f"[UploadService] Failed to extract thumbnails: {e}")
            return []

    def get_video_path(self, base_dir: str, episode_name: str, camera: str = "cam_env") -> Optional[str]:
        """获取 episode 的指定相机视频路径

        Args:
            base_dir: LeRobot 数据目录（包含多个 episode 子目录）
            episode_name: episode 名称，如 "episode_0001"
            camera: 相机名称，默认 "cam_env"

        Returns:
            视频文件路径，如果不存在则返回 None
        """
        base_path = Path(base_dir)
        episode_path = base_path / episode_name

        if not episode_path.exists():
            return None

        # 查找视频文件
        # 路径格式: videos/chunk-000/{camera_key}/episode_*.mp4
        chunk_dir = episode_path / "videos" / "chunk-000"
        if not chunk_dir.exists():
            return None

        for cam_dir in chunk_dir.iterdir():
            if cam_dir.is_dir() and camera in cam_dir.name:
                for video_file in cam_dir.glob("*.mp4"):
                    return str(video_file)

        return None

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
        exclude_episodes = config.get("exclude_episodes") or []

        start_time = datetime.now()

        try:
            # 更新进度
            task.update_progress(percent=0, message="Starting upload...")
            self.db.update(task)

            # 确保 bos_path 有正确的前缀
            if not bos_path.startswith("bos/"):
                bos_path = f"bos/{bos_path}"

            # 如果有排除列表，逐个上传选中的 episode
            if exclude_episodes:
                self._run_selective_upload(
                    task, local_dir, bos_path, concurrency, mc_path,
                    exclude_episodes, start_time
                )
                return

            # 无排除列表时，使用 mc mirror 上传整个目录

            # 先统计总文件数
            total_files = 0
            local_path = Path(local_dir)
            if local_path.exists():
                for _ in local_path.rglob("*"):
                    if _.is_file():
                        total_files += 1

            task.update_progress(
                percent=0,
                message=f"Preparing to upload {total_files} files...",
                total_files=total_files,
                completed_files=0
            )
            self.db.update(task)

            cmd = [
                mc_path,
                "mirror",
                "--overwrite",
                "--json",  # 使用 JSON 输出格式，便于解析进度
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

            # 读取 JSON 输出并更新进度
            completed_files = 0
            last_update_time = datetime.now()
            update_interval = 0.5  # 最小更新间隔（秒）

            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue

                # 解析 mc mirror JSON 输出
                # 文件格式: {"status":"success","source":"...","target":"...","size":...}
                # 摘要格式: {"status":"success","total":...,"transferred":...}
                try:
                    data = json.loads(line)
                    status = data.get("status", "")
                    source = data.get("source", "")

                    # 成功上传一个文件（有 source 字段才是单文件，没有则是摘要行）
                    if status == "success" and source:
                        completed_files += 1
                        percent = int(completed_files / max(total_files, 1) * 100)

                        # 提取文件名
                        file_name = Path(source).name if source else "..."

                        # 限制更新频率，避免数据库压力
                        now = datetime.now()
                        if (now - last_update_time).total_seconds() >= update_interval:
                            task.update_progress(
                                percent=min(percent, 99),
                                message=f"Uploaded: {file_name}",
                                completed_files=completed_files,
                                total_files=total_files
                            )
                            self.db.update(task)
                            last_update_time = now
                            logger.debug(f"Upload progress: {completed_files}/{total_files} ({percent}%)")

                    elif status == "error":
                        # 记录错误但继续
                        error_msg = data.get("error", {}).get("message", "Unknown error")
                        logger.warning(f"Upload error: {error_msg}")

                except json.JSONDecodeError:
                    # 非 JSON 行，忽略
                    pass

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

    def _run_selective_upload(
        self, task: Task, local_dir: str, bos_path: str,
        concurrency: int, mc_path: str, exclude_episodes: List[str],
        start_time: datetime
    ):
        """选择性上传（排除指定 episode）"""
        local_path = Path(local_dir)

        # 获取所有 episode 目录
        all_episodes = [
            d for d in local_path.iterdir()
            if d.is_dir() and (d / "meta" / "info.json").exists()
        ]

        # 过滤排除的 episode
        episodes_to_upload = [
            ep for ep in all_episodes
            if ep.name not in exclude_episodes
        ]

        if not episodes_to_upload:
            elapsed = (datetime.now() - start_time).total_seconds()
            result = TaskResult(
                success=True,
                elapsed_seconds=elapsed,
                details={"message": "No episodes to upload"}
            )
            task.complete(result)
            self.db.update(task)
            return

        # 逐个上传 episode
        uploaded = 0
        failed = []
        total = len(episodes_to_upload)

        for idx, ep_path in enumerate(episodes_to_upload):
            ep_name = ep_path.name

            # 开始上传前更新进度
            task.update_progress(
                percent=int(idx / total * 100),
                message=f"Uploading {ep_name} ({idx + 1}/{total})",
                completed_files=uploaded,
                total_files=total
            )
            self.db.update(task)

            # 使用 mc mirror 上传单个 episode
            target_path = f"{bos_path}/{ep_name}"
            cmd = [
                mc_path,
                "mirror",
                "--overwrite",
                f"--max-workers={concurrency}",
                str(ep_path),
                target_path
            ]

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=3600  # 1 小时超时
                )
                if result.returncode == 0:
                    uploaded += 1
                    # 上传成功后立即更新进度
                    task.update_progress(
                        percent=int((idx + 1) / total * 100),
                        message=f"Uploaded {ep_name} ({idx + 1}/{total})",
                        completed_files=uploaded,
                        total_files=total
                    )
                    self.db.update(task)
                else:
                    failed.append(ep_name)
                    # 上传失败也要更新进度
                    task.update_progress(
                        percent=int((idx + 1) / total * 100),
                        message=f"Failed {ep_name} ({idx + 1}/{total})",
                        completed_files=uploaded,
                        failed_files=len(failed),
                        total_files=total
                    )
                    self.db.update(task)
            except Exception as e:
                failed.append(f"{ep_name}: {str(e)}")
                task.update_progress(
                    percent=int((idx + 1) / total * 100),
                    message=f"Error {ep_name}: {str(e)[:50]}",
                    completed_files=uploaded,
                    failed_files=len(failed),
                    total_files=total
                )
                self.db.update(task)

        elapsed = (datetime.now() - start_time).total_seconds()

        if failed:
            result = TaskResult(
                success=False,
                elapsed_seconds=elapsed,
                error_message=f"Failed episodes: {', '.join(failed)}",
                details={
                    "uploaded": uploaded,
                    "failed": len(failed),
                    "excluded": len(exclude_episodes)
                }
            )
        else:
            result = TaskResult(
                success=True,
                elapsed_seconds=elapsed,
                details={
                    "uploaded": uploaded,
                    "excluded": len(exclude_episodes),
                    "total": len(all_episodes)
                }
            )

        task.complete(result)
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
