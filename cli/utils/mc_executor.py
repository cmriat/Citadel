"""
mc命令执行器 - 封装MinIO Client (mc)命令操作

提供进度回调功能，用于实时监控下载进度
"""

import subprocess
import re
import sys
import time
from typing import Callable, Optional, Tuple
from pathlib import Path

from backend.config import settings


class MCExecutor:
    """mc命令执行器，带进度回调"""

    def __init__(self, mc_path: str = None):
        # 自动检测 mc 路径：环境变量 > ~/bin/mc > 系统 PATH
        if mc_path is None:
            import os
            import shutil
            mc_path = os.environ.get("MC_PATH")
            if not mc_path:
                home_mc = Path.home() / "bin" / "mc"
                if home_mc.exists():
                    mc_path = str(home_mc)
                else:
                    mc_path = shutil.which("mc") or "mc"

        self.mc_path = Path(mc_path)

        if not self.mc_path.exists():
            raise FileNotFoundError(
                f"mc命令未找到: {mc_path}\n"
                f"请确认mc已安装并路径正确"
            )

    def mirror(
        self,
        source: str,
        dest: str,
        concurrency: int = 10,
        progress_callback: Optional[Callable] = None
    ) -> Tuple[bool, str]:
        """
        执行mc mirror下载

        Args:
            source: 源路径 (例如: bos/bucket/path/)
            dest: 目标路径 (本地路径)
            concurrency: 并发数
            progress_callback: 进度回调函数，签名: callback(filename, current_mb, total_mb, percent)

        Returns:
            (成功状态, 错误信息)
        """
        # 创建目标目录
        dest_path = Path(dest)
        dest_path.mkdir(parents=True, exist_ok=True)

        # 构建命令
        cmd = [
            str(self.mc_path),
            "mirror",
            f"--max-workers={concurrency}",
            source,
            str(dest_path)
        ]

        try:
            # 启动进程（实时输出）
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # 读取实时输出
            current_file = None
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break

                line = line.strip()
                if not line:
                    continue

                # 解析进度信息
                progress_info = self._parse_progress(line)
                if progress_info:
                    filename, current_mb, total_mb, percent = progress_info
                    current_file = filename

                    # 调用回调函数
                    if progress_callback:
                        progress_callback(filename, current_mb, total_mb, percent)
                else:
                    # 打印其他输出（如错误信息）
                    if "error" in line.lower() or "failed" in line.lower():
                        print(f"⚠️  {line}", file=sys.stderr)
                    elif line and not line.startswith(' '):
                        # 文件名或状态信息
                        pass

            # 等待进程结束
            return_code = process.wait()

            if return_code == 0:
                return (True, "")
            else:
                return (False, f"mc命令返回错误码: {return_code}")

        except subprocess.TimeoutExpired:
            process.kill()
            return (False, "下载超时")
        except Exception as e:
            return (False, f"下载异常: {str(e)}")

    def _parse_progress(self, line: str) -> Optional[Tuple[str, float, float, float]]:
        """
        解析mc输出行，提取进度信息

        mc mirror输出格式:
        `bos/path/episode_0001.h5` -> `/local/path/episode_0001.h5`

        Returns:
            tuple: (filename, current_mb, total_mb, percent) 或 None
        """
        # mc mirror格式: `source` -> `dest`
        pattern = r'`[^`]+/([\w\-\.]+\.h5)`\s*->\s*`([^`]+)`'
        match = re.search(pattern, line)

        if match:
            filename = match.group(1)
            # 下载完成的文件，返回100%
            # 注意：mc mirror不显示实时进度，只显示完成的文件
            return (filename, 0.0, 0.0, 100.0)

        return None

    def check_connection(self) -> Tuple[bool, str]:
        """
        检查mc连接状态

        Returns:
            (是否连接成功, 错误信息)
        """
        try:
            test_path = f"{settings.BOS_ALIAS}/{settings.BOS_TEST_PATH}"
            cmd = [str(self.mc_path), "ls", test_path]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=settings.TIMEOUT_MC_CHECK
            )

            if result.returncode == 0:
                return (True, "")
            else:
                return (False, f"连接失败: {result.stderr}")

        except subprocess.TimeoutExpired:
            return (False, "连接超时")
        except Exception as e:
            return (False, f"连接异常: {str(e)}")
