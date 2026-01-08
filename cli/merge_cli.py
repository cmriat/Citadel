"""
LeRobot数据集合并命令行工具

使用示例:
    # 合并指定的几个数据集
    pixi run merge --sources "./output1/" "./output2/" --output "./merged/"

    # 合并多个数据集，指定维度和帧率
    pixi run merge --sources "./data1/" "./data2/" "./data3/" --output "./combined/" --state-max-dim 14 --action-max-dim 14 --fps 25

    # 使用通配符合并目录下所有episode（推荐方式）
    pixi run merge --sources /path/to/lerobot/episode_* --output /path/to/merged

    # 实际示例：合并1229_qz2数据集的所有episode
    pixi run merge \\
        --sources /home/jovyan/code/vla/temp_datas/1229_qz2/lerobot/episode_* \\
        --output /home/jovyan/code/vla/temp_datas/1229_qz2/merged

    # 查看帮助
    pixi run merge --help

注意:
    - 所有源数据集必须是LeRobot v2.1格式（包含meta/info.json）
    - 使用通配符时，shell会自动展开为所有匹配的目录
    - 合并后的数据集会重新编号episode（从0开始）
"""

import tyro
from pathlib import Path
from termcolor import colored
import sys
import os

# 添加项目根目录到路径，以便导入scripts模块
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.merge_lerobot import merge_datasets


def merge(
    sources: list[str],
    output: str,
    state_max_dim: int = 14,
    action_max_dim: int = 14,
    fps: int = 25,
    copy_images: bool = False,
):
    """
    合并多个LeRobot数据集为一个整体数据集

    Args:
        sources: 源数据集文件夹路径列表（必须是LeRobot v2.1格式）
        output: 输出合并数据集的文件夹路径
        state_max_dim: 状态向量的最大维度（默认32）
        action_max_dim: 动作向量的最大维度（默认32）
        fps: 视频帧率（默认25）
        copy_images: 是否复制图像文件（默认False，仅复制视频）
    """
    print("=" * 80)
    print(colored("🔀 LeRobot数据集合并工具 - Citadel Release", "cyan", attrs=["bold"]))
    print("=" * 80)
    print(f"源数据集数量: {len(sources)}")
    for i, src in enumerate(sources, 1):
        print(f"  {i}. {src}")
    print(f"输出路径: {output}")
    print(f"状态向量最大维度: {state_max_dim}")
    print(f"动作向量最大维度: {action_max_dim}")
    print(f"视频帧率: {fps}")
    print(f"复制图像: {'是' if copy_images else '否'}")
    print("=" * 80)

    # 验证源路径
    print("\n📁 验证源数据集...")
    invalid_sources = []
    for src in sources:
        src_path = Path(src)
        if not src_path.exists():
            print(colored(f"  ✗ {src} - 路径不存在", "red"))
            invalid_sources.append(src)
        elif not (src_path / "meta" / "info.json").exists():
            print(colored(f"  ✗ {src} - 不是有效的LeRobot数据集（缺少meta/info.json）", "red"))
            invalid_sources.append(src)
        else:
            print(colored(f"  ✓ {src}", "green"))

    if invalid_sources:
        print(colored(f"\n❌ {len(invalid_sources)} 个源数据集无效，无法继续", "red", attrs=["bold"]))
        return

    # 检查输出路径
    output_path = Path(output)
    if output_path.exists():
        print(colored(f"\n⚠️  警告: 输出路径已存在: {output}", "yellow"))
        response = input("是否覆盖？(y/N): ")
        if response.lower() != 'y':
            print("已取消操作")
            return

    # 开始合并
    print(f"\n🚀 开始合并数据集...\n")

    try:
        # 调用合并函数
        # 需要设置全局参数以传递给merge_datasets
        class Args:
            pass

        args = Args()
        args.copy_images = copy_images

        # 临时设置全局args（merge_lerobot.py中使用）
        import scripts.merge_lerobot as merge_module
        merge_module.args = args

        merge_datasets(
            source_folders=sources,
            output_folder=output,
            validate_ts=False,
            tolerance_s=1e-4,
            state_max_dim=state_max_dim,
            action_max_dim=action_max_dim,
            default_fps=fps,
        )

        print("\n" + "=" * 80)
        print(colored("✅ 数据集合并完成！", "green", attrs=["bold"]))
        print("=" * 80)
        print(f"输出位置: {output}")

        # 显示合并后的统计信息
        if output_path.exists():
            import json
            info_file = output_path / "meta" / "info.json"
            if info_file.exists():
                with open(info_file) as f:
                    info = json.load(f)
                print(f"\n📊 合并后统计:")
                print(f"  总 Episodes: {info.get('total_episodes', 'N/A')}")
                print(f"  总帧数: {info.get('total_frames', 'N/A')}")
                print(f"  总任务数: {info.get('total_tasks', 'N/A')}")
                print(f"  总视频数: {info.get('total_videos', 'N/A')}")

    except Exception as e:
        print("\n" + "=" * 80)
        print(colored("❌ 合并失败", "red", attrs=["bold"]))
        print("=" * 80)
        print(f"错误信息: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    tyro.cli(merge)
