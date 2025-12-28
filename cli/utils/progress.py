"""
终端进度条显示工具

提供彩色进度条和友好的进度显示
"""

from termcolor import colored


class ProgressBar:
    """终端进度条显示"""

    def __init__(self):
        self.current_file = None
        self.total_files = 0
        self.completed_files = 0

    def update(self, filename: str, current: float, total: float, percent: float):
        """
        更新进度显示

        Args:
            filename: 当前文件名
            current: 当前已下载大小 (MiB)
            total: 总大小 (MiB)
            percent: 百分比 (0-100)
        """
        # 如果是新文件，换行显示文件名
        if self.current_file != filename:
            self.current_file = filename
            print(f"\n📥 {filename}")

        # 绘制进度条
        bar_length = 40
        filled = int(bar_length * percent / 100)
        bar = '█' * filled + '░' * (bar_length - filled)

        # 彩色状态显示
        if percent >= 100:
            status = colored(f"{percent:5.1f}%", "green")
        elif percent >= 50:
            status = colored(f"{percent:5.1f}%", "yellow")
        else:
            status = colored(f"{percent:5.1f}%", "cyan")

        # 打印进度（使用\r实现同行更新）
        print(
            f"\r  [{bar}] {status} {current:.1f}/{total:.1f} MiB",
            end='',
            flush=True
        )

    def finish(self):
        """完成所有下载，打印总结"""
        print("\n\n✅ 下载完成！")
