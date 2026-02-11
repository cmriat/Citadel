"""
HDF5转换命令行工具

使用示例:
    pixi run convert --input-dir "/path/to/hdf5/" --output-dir "/path/to/output/"
    pixi run convert --alignment-method linear ...  # 使用线性插值
    pixi run convert --help

环境变量:
    DEFAULT_ROBOT_TYPE: 默认机器人类型 (默认: airbot_play)
    DEFAULT_FPS: 默认帧率 (默认: 25)
    DEFAULT_TASK_NAME: 默认任务描述 (默认: Fold the laundry)
    DEFAULT_PARALLEL_JOBS: 默认并行任务数 (默认: 4)
    DEFAULT_FILE_PATTERN: 默认文件匹配模式 (默认: episode_*.h5)
    DEFAULT_ALIGNMENT_METHOD: 默认对齐方法 (默认: nearest)
    TIMEOUT_CONVERT: 单文件转换超时秒数 (默认: 300)
"""

import os
import tyro
from pathlib import Path
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple, List, Optional
from termcolor import colored

from backend.config import settings


def _get_env(key: str, default: str) -> str:
    """从环境变量获取字符串值"""
    return os.environ.get(key, default)


def _get_env_int(key: str, default: int) -> int:
    """从环境变量获取整数值"""
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def convert_single_file(
    hdf5_file: Path,
    output_base_dir: Path,
    robot_type: str,
    fps: int,
    task: str,
    alignment_method: str
) -> Tuple[bool, str, float]:
    """转换单个HDF5文件

    Args:
        hdf5_file: HDF5文件路径
        output_base_dir: 输出基础目录
        robot_type: 机器人类型
        fps: 帧率
        task: 任务描述
        alignment_method: 对齐方法 ('nearest' 或 'linear')

    Returns:
        (是否成功, 错误信息, 耗时秒数)
    """
    start_time = time.time()
    episode_name = hdf5_file.stem  # 例如: episode_0001
    output_episode_dir = output_base_dir / episode_name

    # 构建命令
    cmd = [
        "python", "scripts/convert.py",
        "--hdf5-path", str(hdf5_file),
        "--output-dir", str(output_episode_dir),
        "--robot-type", robot_type,
        "--fps", str(fps),
        "--task", task,
        "--alignment-method", alignment_method
    ]

    try:
        # 执行转换（重定向输出，避免混乱）
        # 使用项目根目录（相对于 cli/ 目录的上级目录）
        project_root = Path(__file__).parent.parent.resolve()
        result = subprocess.run(
            cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=settings.TIMEOUT_CONVERT
        )

        elapsed = time.time() - start_time

        if result.returncode == 0:
            return (True, "", elapsed)
        else:
            # 提取错误信息（最后10行）
            error_lines = result.stderr.split('\n')[-10:]
            error_msg = '\n'.join(error_lines)
            return (False, error_msg, elapsed)

    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        return (False, "转换超时（>5分钟）", elapsed)
    except Exception as e:
        elapsed = time.time() - start_time
        return (False, f"异常: {str(e)}", elapsed)


def convert(
    input_dir: str = "/pfs/pfs-uaDOJM/home/maozan/code/data/0203_qz2_pants/raw",
    output_dir: str = "/pfs/pfs-uaDOJM/home/maozan/code/data/0203_qz2_pants/lerobot",
    robot_type: Optional[str] = None,
    fps: Optional[int] = None,
    task: Optional[str] = None,
    parallel_jobs: Optional[int] = None,
    file_pattern: Optional[str] = None,
    alignment_method: Optional[str] = "linear"
):
    """
    批量转换HDF5文件为LeRobot v2.1格式

    Args:
        input_dir: 输入HDF5目录
        output_dir: 输出LeRobot目录
        robot_type: 机器人类型（默认从环境变量 DEFAULT_ROBOT_TYPE 读取，或使用 'airbot_play'）
        fps: 视频帧率（默认从环境变量 DEFAULT_FPS 读取，或使用 25）
        task: 任务描述（默认从环境变量 DEFAULT_TASK_NAME 读取，或使用 'Fold the laundry'）
        parallel_jobs: 并发任务数（默认从环境变量 DEFAULT_PARALLEL_JOBS 读取，或使用 4）
        file_pattern: 文件匹配模式（默认从环境变量 DEFAULT_FILE_PATTERN 读取，或使用 'episode_*.h5'）
        alignment_method: 关节对齐方法（默认从环境变量 DEFAULT_ALIGNMENT_METHOD 读取，或使用 'nearest'）
                         可选值: 'nearest' (最近邻) 或 'linear' (线性插值)
    """
    # 从环境变量获取默认值
    if robot_type is None:
        robot_type = _get_env("DEFAULT_ROBOT_TYPE", "airbot_play")
    if fps is None:
        fps = _get_env_int("DEFAULT_FPS", 25)
    if task is None:
        task = _get_env("DEFAULT_TASK_NAME", "Fold the laundry")
    if parallel_jobs is None:
        parallel_jobs = _get_env_int("DEFAULT_PARALLEL_JOBS", 4)
    if file_pattern is None:
        file_pattern = _get_env("DEFAULT_FILE_PATTERN", "episode_*.h5")
    if alignment_method is None:
        alignment_method = _get_env("DEFAULT_ALIGNMENT_METHOD", "linear")

    print("=" * 80)
    print(colored("🔄 HDF5批量转换工具 - Citadel Release", "cyan", attrs=["bold"]))
    print("=" * 80)
    print(f"输入目录: {input_dir}")
    print(f"输出目录: {output_dir}")
    print(f"机器人类型: {robot_type}")
    print(f"FPS: {fps}")
    print(f"任务: {task}")
    print(f"并发数: {parallel_jobs}")
    print(f"文件模式: {file_pattern}")
    print(f"对齐方法: {alignment_method}")
    print("=" * 80)

    # 1. 扫描HDF5文件
    input_path = Path(input_dir)
    output_path = Path(output_dir)

    if not input_path.exists():
        print(colored(f"\n❌ 错误: 输入目录不存在: {input_dir}", "red"))
        return

    hdf5_files = sorted(input_path.glob(file_pattern))

    if len(hdf5_files) == 0:
        print(colored(f"\n⚠️  警告: 未找到匹配 '{file_pattern}' 的HDF5文件", "yellow"))
        return

    print(f"\n📦 找到 {colored(str(len(hdf5_files)), 'green', attrs=['bold'])} 个HDF5文件:")
    for f in hdf5_files[:5]:
        print(f"  - {f.name}")
    if len(hdf5_files) > 5:
        print(f"  ... 还有 {len(hdf5_files) - 5} 个文件")

    # 2. 创建输出目录
    output_path.mkdir(parents=True, exist_ok=True)

    # 3. 批量转换（并发执行）
    print(f"\n🚀 开始批量转换（{parallel_jobs}个并发任务）...\n")

    start_time = time.time()
    results: List[Tuple[str, bool, str, float]] = []

    with ThreadPoolExecutor(max_workers=parallel_jobs) as executor:
        # 提交所有任务
        future_to_file = {
            executor.submit(
                convert_single_file,
                hdf5_file,
                output_path,
                robot_type,
                fps,
                task,
                alignment_method
            ): hdf5_file
            for hdf5_file in hdf5_files
        }

        # 处理完成的任务
        completed = 0
        for future in as_completed(future_to_file):
            hdf5_file = future_to_file[future]
            completed += 1

            try:
                success, error_msg, elapsed = future.result()
                results.append((hdf5_file.name, success, error_msg, elapsed))

                # 打印进度
                status_icon = "✓" if success else "✗"
                status_color = "green" if success else "red"

                print(
                    f"[{completed:2d}/{len(hdf5_files):2d}] "
                    f"{colored(status_icon, status_color)} "
                    f"{hdf5_file.name:30s} "
                    f"({elapsed:.1f}s)"
                )

                # 如果失败，打印错误信息
                if not success:
                    print(colored(f"      错误: {error_msg[:100]}", "red"))

            except Exception as e:
                results.append((hdf5_file.name, False, f"未知错误: {str(e)}", 0))
                print(
                    f"[{completed:2d}/{len(hdf5_files):2d}] "
                    f"{colored('✗', 'red')} "
                    f"{hdf5_file.name:30s} "
                    f"(异常)"
                )

    # 4. 统计结果
    total_time = time.time() - start_time
    success_count = sum(1 for _, success, _, _ in results if success)
    failed_count = len(results) - success_count

    print("\n" + "=" * 80)
    print(colored("📊 转换完成统计", "cyan", attrs=["bold"]))
    print("=" * 80)
    print(f"总文件数: {len(results)}")
    print(colored(f"✓ 成功: {success_count}", "green"))
    if failed_count > 0:
        print(colored(f"✗ 失败: {failed_count}", "red"))
    print(f"⏱️  总耗时: {total_time:.1f}秒 (平均 {total_time/len(results):.1f}秒/文件)")

    # 5. 显示失败文件详情
    if failed_count > 0:
        print(f"\n{colored('失败文件列表:', 'red', attrs=['bold'])}")
        for filename, success, error_msg, _ in results:
            if not success:
                print(f"  - {filename}")
                if error_msg:
                    print(f"    原因: {error_msg[:200]}")

    print("\n" + "=" * 80)
    if failed_count == 0:
        print(colored("✅ 所有文件转换成功！", "green", attrs=["bold"]))
    else:
        print(colored(f"⚠️  {failed_count} 个文件转换失败，请检查错误信息", "yellow", attrs=["bold"]))
    print("=" * 80)


if __name__ == "__main__":
    tyro.cli(convert)
