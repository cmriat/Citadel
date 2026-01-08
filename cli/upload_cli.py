"""
BOS上传命令行工具

使用示例:
    pixi run upload
    pixi run upload --local-dir "./data/lerobot/episode_0001" --bos-path "srgdata/robot/lerobot_data/"
    pixi run upload --help
"""

import os
import json
import subprocess
import time
from pathlib import Path
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

import tyro
from termcolor import colored


@dataclass
class UploadProgress:
    """上传进度信息"""
    completed_files: int = 0
    total_files: int = 0
    current_file: str = ""
    start_time: float = 0.0


class UploadCLI:
    """上传命令行工具"""

    def __init__(self, mc_path: str = "/home/jovyan/mc"):
        self.mc_path = mc_path
        self.progress = UploadProgress()

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

    def check_connection(self) -> Tuple[bool, str]:
        """检查BOS连接"""
        try:
            result = subprocess.run(
                [self.mc_path, "ls", "bos/srgdata/"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return True, ""
            return False, result.stderr
        except subprocess.TimeoutExpired:
            return False, "连接超时"
        except Exception as e:
            return False, str(e)

    def scan_lerobot_dir(self, local_dir: str) -> Dict:
        """扫描LeRobot目录，返回统计信息"""
        local_path = Path(local_dir)
        if not local_path.exists():
            return {"exists": False, "error": f"目录不存在: {local_dir}"}

        # 检查是否为LeRobot格式（包含 meta/info.json）
        meta_file = local_path / "meta" / "info.json"
        is_lerobot = meta_file.exists()

        # 统计文件
        total_size = 0
        file_count = 0
        file_types: Dict[str, int] = {}

        for root, _, files in os.walk(local_path):
            for f in files:
                file_path = Path(root) / f
                try:
                    size = file_path.stat().st_size
                    total_size += size
                    file_count += 1

                    # 统计文件类型
                    ext = file_path.suffix.lower()
                    file_types[ext] = file_types.get(ext, 0) + 1
                except Exception:
                    pass

        # 读取元数据
        meta_info = {}
        if is_lerobot and meta_file.exists():
            try:
                with open(meta_file, 'r') as f:
                    meta_info = json.load(f)
            except Exception:
                pass

        return {
            "exists": True,
            "is_lerobot": is_lerobot,
            "path": str(local_path),
            "name": local_path.name,
            "total_size": total_size,
            "file_count": file_count,
            "file_types": file_types,
            "meta_info": meta_info
        }

    def upload(
        self,
        local_dir: str,
        bos_path: str,
        concurrency: int = 10
    ) -> Tuple[bool, str]:
        """执行上传"""
        # 确保 bos_path 有正确的前缀
        if not bos_path.startswith("bos/"):
            bos_path = f"bos/{bos_path}"

        # 统计文件数
        local_path = Path(local_dir)
        total_files = sum(1 for _ in local_path.rglob("*") if _.is_file())
        self.progress.total_files = total_files
        self.progress.start_time = time.time()

        # 构建命令，使用 --json 获取结构化输出
        cmd = [
            self.mc_path,
            "mirror",
            "--overwrite",
            "--json",
            f"--max-workers={concurrency}",
            str(local_dir),
            bos_path
        ]

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            # 读取 JSON 输出并更新进度
            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    status = data.get("status", "")
                    source = data.get("source", "")

                    # 成功上传一个文件（有 source 字段才是单文件）
                    if status == "success" and source:
                        self.progress.completed_files += 1
                        self.progress.current_file = Path(source).name

                        # 显示进度
                        percent = int(self.progress.completed_files / max(total_files, 1) * 100)
                        elapsed = time.time() - self.progress.start_time
                        speed = self.progress.completed_files / elapsed if elapsed > 0 else 0

                        # 清除当前行并打印进度
                        print(f"\r[{self.progress.completed_files}/{total_files}] "
                              f"{percent:3d}% | {speed:.1f} files/s | "
                              f"{self.progress.current_file[:40]:40s}", end="", flush=True)

                    elif status == "error":
                        error_msg = data.get("error", {}).get("message", "Unknown error")
                        print(f"\n⚠️  上传错误: {error_msg}")

                except json.JSONDecodeError:
                    # 非 JSON 行，忽略
                    pass

            process.wait()

            # 打印换行
            print()

            if process.returncode == 0:
                return True, ""
            else:
                return False, f"mc命令返回错误码: {process.returncode}"

        except Exception as e:
            return False, f"上传异常: {str(e)}"


def upload(
    local_dir: str = "./data/lerobot/",
    bos_path: str = "srgdata/robot/lerobot_data/",
    concurrency: int = 10,
    mc_path: str = "/home/jovyan/mc"
):
    """
    上传LeRobot数据到BOS

    Args:
        local_dir: 本地LeRobot目录路径
        bos_path: BOS目标路径（不需要bos/前缀）
        concurrency: 并发上传数（推荐10-15）
        mc_path: mc可执行文件路径
    """
    print("=" * 80)
    print(colored("📤 BOS上传工具 - Citadel Release", "cyan", attrs=["bold"]))
    print("=" * 80)
    print(f"本地路径: {local_dir}")
    print(f"BOS路径: bos/{bos_path}")
    print(f"并发数: {concurrency}")
    print(f"mc路径: {mc_path}")
    print("=" * 80)

    cli = UploadCLI(mc_path)

    # 1. 检查mc工具
    ok, msg = cli.check_mc()
    if not ok:
        print(colored(f"\n❌ mc工具不可用: {msg}", "red"))
        return
    print(f"\n✓ mc工具已找到: {msg}")

    # 2. 检查BOS连接
    print(f"\n🔗 检查BOS连接...")
    ok, error = cli.check_connection()
    if not ok:
        print(colored(f"❌ BOS连接失败: {error}", "red"))
        print("\n💡 提示: 请确认mc已配置BOS别名")
        return
    print(colored("✓ BOS连接成功", "green"))

    # 3. 扫描本地目录
    print(f"\n📁 扫描本地目录...")
    scan_result = cli.scan_lerobot_dir(local_dir)

    if not scan_result["exists"]:
        print(colored(f"❌ {scan_result['error']}", "red"))
        return

    # 显示扫描结果
    size_mb = scan_result["total_size"] / (1024 * 1024)
    print(f"   目录名: {scan_result['name']}")
    print(f"   文件数: {scan_result['file_count']}")
    print(f"   总大小: {size_mb:.2f} MB")
    print(f"   LeRobot格式: {'✓' if scan_result['is_lerobot'] else '✗'}")

    if scan_result["file_types"]:
        print(f"   文件类型:")
        for ext, count in sorted(scan_result["file_types"].items()):
            print(f"      {ext or '(无扩展名)'}: {count}")

    if scan_result["is_lerobot"] and scan_result["meta_info"]:
        meta = scan_result["meta_info"]
        print(f"   元数据:")
        if "total_frames" in meta:
            print(f"      总帧数: {meta['total_frames']}")
        if "robot_type" in meta:
            print(f"      机器人: {meta['robot_type']}")

    # 4. 开始上传
    print(f"\n🚀 开始上传...\n")
    start_time = time.time()

    success, error = cli.upload(local_dir, bos_path, concurrency)
    elapsed = time.time() - start_time

    # 5. 显示结果
    print("\n" + "=" * 80)
    if success:
        print(colored("✅ 上传成功完成！", "green", attrs=["bold"]))
        print("=" * 80)
        print(f"上传文件数: {cli.progress.completed_files}")
        print(f"总耗时: {elapsed:.1f}秒")
        if elapsed > 0:
            print(f"平均速度: {cli.progress.completed_files / elapsed:.1f} files/s")
            print(f"          {size_mb / elapsed:.2f} MB/s")
        print(f"\n目标位置: bos/{bos_path}")
    else:
        print(colored("❌ 上传失败", "red", attrs=["bold"]))
        print("=" * 80)
        print(f"错误信息: {error}")
        print(f"已上传: {cli.progress.completed_files}/{cli.progress.total_files}")
        print(f"耗时: {elapsed:.1f}秒")


if __name__ == "__main__":
    tyro.cli(upload)
