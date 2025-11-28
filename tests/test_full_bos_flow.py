#!/usr/bin/env python3
"""测试完整的 BOS 拉取→转换→上传流程"""

import sys
import logging
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from lerobot_converter.bos import BosClient, BosDownloader, BosUploader
from lerobot_converter.pipeline.converter import LeRobotConverter

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_full_flow(episode_id: str = "episode_0001"):
    """测试完整流程"""

    print("=" * 80)
    print("BOS 完整流程测试")
    print("=" * 80)

    # 1. 初始化 BOS 客户端
    print("\n[1/5] 初始化 BOS 客户端...")
    bos_client = BosClient('config/bos_config.yaml')

    if not bos_client.test_connection():
        print("❌ BOS 连接失败")
        return False

    print("✓ BOS 连接成功")

    # 2. 下载数据
    print(f"\n[2/5] 下载 {episode_id}...")
    downloader = BosDownloader(bos_client)

    result = downloader.download_episode(episode_id)
    if not result:
        print("❌ 下载失败")
        return False

    data_path, _ = result
    print(f"✓ 下载成功: {data_path}")

    # 验证下载的文件
    episode_dir = data_path / episode_id
    joints_dir = episode_dir / "joints"
    images_dir = episode_dir / "images"

    print(f"\n  验证下载的文件:")
    print(f"  - Episode: {episode_dir.exists()}")
    print(f"  - Joints: {joints_dir.exists()} ({len(list(joints_dir.iterdir())) if joints_dir.exists() else 0} files)")
    print(f"  - Images: {images_dir.exists()} ({len([d for d in images_dir.iterdir() if d.is_dir()]) if images_dir.exists() else 0} cameras)")

    # 检查 metadata.json
    joints_meta = joints_dir / "metadata.json"
    images_meta = images_dir / "metadata.json"
    print(f"  - joints/metadata.json: {joints_meta.exists()}")
    print(f"  - images/metadata.json: {images_meta.exists()}")

    if not joints_meta.exists() or not images_meta.exists():
        print("\n⚠️  metadata.json 缺失！")

        # 列出实际下载的文件
        print(f"\n  Joints 目录内容:")
        for f in joints_dir.iterdir():
            print(f"    - {f.name}")

        print(f"\n  Images 目录内容:")
        for item in images_dir.iterdir():
            if item.is_dir():
                print(f"    - {item.name}/ ({len(list(item.iterdir()))} files)")
            else:
                print(f"    - {item.name}")

    # 3. 转换数据
    print(f"\n[3/5] 转换 {episode_id}...")

    try:
        # 加载转换配置
        import yaml
        with open('config/bos_config.yaml', 'r') as f:
            config = yaml.safe_load(f)

        conversion_config = config.get('conversion', {})
        config_template = conversion_config.get('config_template', 'config/new_format_chunking.yaml')
        output_pattern = config.get('output', {}).get('pattern', 'lerobot_dataset_{task}_{strategy}')

        # 创建 LeRobotConverter
        converter = LeRobotConverter(
            config_or_path=config_template,
            input_data_path=str(data_path),
            input_images_path=str(data_path)
        )

        # 推断 task 和 strategy
        task_name = bos_client.get_task_name()
        strategy = conversion_config.get('strategy', 'action_chunking')
        output_dir = output_pattern.format(task=task_name, strategy=strategy)

        # 转换单个 episode
        converter.convert(episode_id=episode_id)

        print(f"✓ 转换成功")

        # 检查输出目录（从日志中读取，或使用固定名称）
        output_path = Path("lerobot_dataset_new_format")
        if not output_path.exists():
            print(f"⚠️  输出目录不存在: {output_path}")
            return False

        print(f"  输出目录: {output_path}")
        print(f"  - data/: {(output_path / 'data').exists()}")
        print(f"  - videos/: {(output_path / 'videos').exists()}")
        print(f"  - meta/: {(output_path / 'meta').exists()}")

    except Exception as e:
        print(f"❌ 转换失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 4. 上传结果
    print(f"\n[4/5] 上传转换结果到 BOS...")
    uploader = BosUploader(bos_client)

    try:
        output_path = Path("lerobot_dataset_new_format")
        if not output_path.exists():
            print(f"❌ 输出目录不存在: {output_path}")
            return False

        success = uploader.upload_episode(output_path, episode_id)
        if success:
            print("✓ 上传成功")
        else:
            print("❌ 上传失败")
            return False

    except Exception as e:
        print(f"❌ 上传失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 5. 清理临时文件
    print(f"\n[5/5] 清理临时文件...")
    downloader.cleanup(episode_id)
    print("✓ 清理完成")

    print("\n" + "=" * 80)
    print("✅ 完整流程测试成功！")
    print("=" * 80)

    return True


if __name__ == '__main__':
    import sys

    episode_id = sys.argv[1] if len(sys.argv) > 1 else "episode_0001"

    success = test_full_flow(episode_id)
    sys.exit(0 if success else 1)
