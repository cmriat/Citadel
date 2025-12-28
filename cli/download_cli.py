"""
BOS下载命令行工具

使用示例:
    pixi run download
    pixi run download --bos-path "srgdata/..." --local-path "/home/maozan/data/..."
    pixi run download --help
"""

import tyro
import time
from pathlib import Path
from typing import Dict
from termcolor import colored
from cli.utils.mc_executor import MCExecutor


class ProgressTracker:
    """进度跟踪器"""

    def __init__(self):
        self.files: Dict[str, dict] = {}
        self.start_time = time.time()
        self.last_update = 0
        self.update_interval = 0.5  # 更新间隔（秒）

    def update(self, filename: str, current_mb: float, total_mb: float, percent: float):
        """更新进度信息"""
        current_time = time.time()

        # 更新文件信息
        if filename not in self.files:
            # 新文件，打印一行
            elapsed = current_time - self.start_time
            file_count = len(self.files) + 1
            print(f"[{file_count:2d}] ✓ {filename}")

        self.files[filename] = {
            'current_mb': current_mb,
            'total_mb': total_mb,
            'percent': percent,
            'last_update': current_time
        }

        self.last_update = current_time

    def summary(self, local_path: str = None):
        """打印摘要"""
        elapsed = time.time() - self.start_time

        # 如果提供了本地路径，计算实际文件大小
        total_size_mb = 0.0
        if local_path:
            from pathlib import Path
            local_dir = Path(local_path)
            for filename in self.files.keys():
                file_path = local_dir / filename
                if file_path.exists():
                    total_size_mb += file_path.stat().st_size / (1024 * 1024)

        print("\n\n" + "=" * 80)
        print(colored("📊 下载完成统计", "cyan", attrs=["bold"]))
        print("=" * 80)
        print(f"下载文件数: {len(self.files)}")
        print(f"总大小: {total_size_mb:.2f} MB")
        print(f"总耗时: {elapsed:.1f}秒")
        if elapsed > 0 and total_size_mb > 0:
            print(f"平均速度: {total_size_mb / elapsed:.2f} MB/s")

        # 列出所有文件
        if self.files:
            print(f"\n下载的文件:")
            for filename in sorted(self.files.keys()):
                # 获取实际文件大小
                file_size = 0.0
                if local_path:
                    file_path = Path(local_path) / filename
                    if file_path.exists():
                        file_size = file_path.stat().st_size / (1024 * 1024)

                print(f"  {colored('✓', 'green')} {filename:30s} {file_size:>8.2f} MB")


def download(
    bos_path: str = "srgdata/robot/raw_data/upload_test/online_test_hdf5_v1/fold_laundry/",
    local_path: str = "/home/maozan/code/Citadel_release/test_data/download_test/",
    concurrency: int = 10,
    mc_path: str = "/home/maozan/mc"
):
    """
    从BOS下载HDF5文件

    Args:
        bos_path: BOS远程路径（不包含bos:前缀）
        local_path: 本地保存路径
        concurrency: 并发数（推荐10-15）
        mc_path: mc可执行文件路径
    """
    print("=" * 80)
    print(colored("📥 BOS下载工具 - Citadel Release", "cyan", attrs=["bold"]))
    print("=" * 80)
    print(f"BOS路径: bos/{bos_path}")
    print(f"本地路径: {local_path}")
    print(f"并发数: {concurrency}")
    print(f"mc路径: {mc_path}")
    print("=" * 80)

    # 1. 初始化MCExecutor
    try:
        executor = MCExecutor(mc_path)
        print(f"\n✓ mc工具已找到: {mc_path}")
    except FileNotFoundError as e:
        print(colored(f"\n❌ 错误: {e}", "red"))
        return

    # 2. 检查连接
    print(f"\n🔗 检查BOS连接...")
    success, error = executor.check_connection()
    if not success:
        print(colored(f"❌ BOS连接失败: {error}", "red"))
        print("\n💡 提示: 请确认mc已配置BOS别名")
        print("   配置命令: mc alias set bos <endpoint> <access-key> <secret-key>")
        return

    print(colored("✓ BOS连接成功", "green"))

    # 3. 创建本地目录
    local_path_obj = Path(local_path)
    local_path_obj.mkdir(parents=True, exist_ok=True)
    print(f"✓ 本地目录已创建: {local_path}")

    # 4. 开始下载
    print(f"\n🚀 开始下载...\n")

    tracker = ProgressTracker()
    start_time = time.time()

    success, error = executor.mirror(
        source=f"bos/{bos_path}",
        dest=local_path,
        concurrency=concurrency,
        progress_callback=tracker.update
    )

    elapsed = time.time() - start_time

    # 5. 显示结果
    if success:
        tracker.summary(local_path)
        print("\n" + "=" * 80)
        print(colored("✅ 下载成功完成！", "green", attrs=["bold"]))
        print("=" * 80)
        print(f"\n文件保存位置: {local_path}")
    else:
        print(f"\n" + "=" * 80)
        print(colored("❌ 下载失败", "red", attrs=["bold"]))
        print("=" * 80)
        print(f"错误信息: {error}")
        print(f"耗时: {elapsed:.1f}秒")

        # 显示已下载的文件
        if tracker.files:
            print(f"\n部分文件可能已下载:")
            for filename, info in tracker.files.items():
                if info['percent'] >= 100:
                    print(f"  ✓ {filename}")


if __name__ == "__main__":
    tyro.cli(download)
