"""
Visualize LeRobot parquet data for quick verification after conversion.

Usage:
    pixi run visualize /path/to/episode_0001
    pixi run visualize /path/to/episode_0001 --frames 500
    pixi run visualize /path/to/episode_0001 --no-save
"""

import sys
from pathlib import Path
from typing import Optional
import numpy as np
import pyarrow.parquet as pq
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


# Delta threshold for marking as PROBLEM
DELTA_THRESHOLD = 0.01


def load_parquet(path: Path) -> dict:
    """Load parquet file and return as dict of numpy arrays."""
    table = pq.read_table(path)
    data = {}
    for col in table.column_names:
        arr = table[col].to_pylist()
        if arr and isinstance(arr[0], list):
            data[col] = np.array(arr)
        else:
            data[col] = np.array(arr)
    return data


def find_parquet_file(input_path: Path) -> Path:
    """Find parquet file from input path (file or directory)."""
    if input_path.is_file() and input_path.suffix == '.parquet':
        return input_path

    candidates = [
        input_path / "data" / "chunk-000" / "episode_000000.parquet",
        input_path / "chunk-000" / "episode_000000.parquet",
        *input_path.glob("**/*.parquet")
    ]

    for candidate in candidates:
        if isinstance(candidate, Path) and candidate.exists():
            return candidate

    raise FileNotFoundError(f"No parquet file found in {input_path}")


def get_episode_name(parquet_path: Path) -> str:
    """Extract episode name from path."""
    # Try to find episode directory name
    for parent in parquet_path.parents:
        if parent.name.startswith("episode_"):
            return parent.name
    return parquet_path.stem


def visualize_arm(
    state: np.ndarray,
    action: np.ndarray,
    arm_name: str,
    episode_name: str,
    num_frames: int,
    output_path: Optional[Path] = None
):
    """
    Visualize single arm (6 joints + gripper) in 3x3 grid layout.

    Args:
        state: [N, 7] array (6 joints + 1 gripper)
        action: [N, 7] array (6 joints + 1 gripper)
        arm_name: "Left Arm" or "Right Arm"
        episode_name: Episode identifier
        num_frames: Number of frames to visualize
        output_path: Path to save figure
    """
    fig, axes = plt.subplots(3, 3, figsize=(15, 12))
    fig.suptitle(
        f'{episode_name} - {arm_name} (6 Joints + Gripper) | First {num_frames} Frames',
        fontsize=14, fontweight='bold'
    )

    t = np.arange(num_frames)

    # Compute deltas for all dimensions
    deltas = action[:num_frames] - state[:num_frames]
    joint_deltas = deltas[:, :6]  # First 6 dims are joints
    gripper_delta = deltas[:, 6]  # Last dim is gripper

    # Plot Joint 0-5 (first 6 subplots)
    for i in range(6):
        row, col = i // 3, i % 3
        ax = axes[row, col]

        delta_mean = np.mean(deltas[:, i])
        is_problem = abs(delta_mean) > DELTA_THRESHOLD

        # Plot state and action
        ax.plot(t, state[:num_frames, i], 'b-', label='State', linewidth=1.5)
        ax.plot(t, action[:num_frames, i], 'r--', label='Action', linewidth=1.5)

        # Title with delta info
        status = "⚠ PROBLEM" if is_problem else "✓ Normal"
        title_color = 'red' if is_problem else 'green'

        ax.set_title(f'Joint {i}\nΔ Mean: {delta_mean:.6f} {status}',
                     fontsize=10, color=title_color, fontweight='bold')

        ax.set_xlabel('Time Step', fontsize=9)
        ax.set_ylabel('Value', fontsize=9)
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3)

    # Plot Gripper (position [2, 0])
    ax = axes[2, 0]
    gripper_delta_mean = np.mean(gripper_delta)
    is_problem = abs(gripper_delta_mean) > DELTA_THRESHOLD

    ax.plot(t, state[:num_frames, 6], 'b-', label='State', linewidth=1.5)
    ax.plot(t, action[:num_frames, 6], 'r--', label='Action', linewidth=1.5)

    status = "⚠ PROBLEM" if is_problem else "✓ Normal"
    title_color = 'red' if is_problem else 'green'

    ax.set_title(f'Gripper\nΔ Mean: {gripper_delta_mean:.6f} {status}',
                 fontsize=10, color=title_color, fontweight='bold')
    ax.set_xlabel('Time Step', fontsize=9)
    ax.set_ylabel('Value', fontsize=9)
    ax.legend(loc='upper right', fontsize=8)
    ax.grid(True, alpha=0.3)

    # Delta Statistics text box (position [2, 1])
    ax = axes[2, 1]
    ax.axis('off')

    avg_joint_delta = np.mean(np.abs(joint_deltas))
    gripper_dim = 6 if arm_name == "Left Arm" else 13

    # Determine overall status
    any_problem = any(abs(np.mean(deltas[:, i])) > DELTA_THRESHOLD for i in range(7))
    overall_status = "⚠ PROBLEM" if any_problem else "✓ READY"
    overall_color = 'red' if any_problem else 'green'

    stats_text = f"""DELTA STATISTICS
(First {num_frames} frames)

Joints (0-5):
  Avg |Δ|: {avg_joint_delta:.6f}

{arm_name.split()[0]} Gripper (Dim {gripper_dim}):
  Δ Mean: {gripper_delta_mean:.6f}
"""

    ax.text(
        0.5, 0.6, stats_text,
        transform=ax.transAxes,
        ha='center', va='center',
        fontsize=11, family='monospace',
        bbox=dict(boxstyle='round', facecolor='lightyellow', edgecolor='gray')
    )
    ax.text(
        0.5, 0.15, overall_status,
        transform=ax.transAxes,
        ha='center', va='center',
        fontsize=16, fontweight='bold', color=overall_color,
        bbox=dict(boxstyle='round', facecolor='white', edgecolor=overall_color, linewidth=2)
    )

    # Delta Distribution histogram (position [2, 2])
    ax = axes[2, 2]

    joint_deltas_flat = joint_deltas.flatten()
    gripper_deltas_flat = gripper_delta.flatten()

    ax.hist(joint_deltas_flat, bins=50, alpha=0.7, color='steelblue',
            label=f'Joints (μ={np.mean(joint_deltas_flat):.6f})', edgecolor='black')
    ax.hist(gripper_deltas_flat, bins=30, alpha=0.7, color='coral',
            label=f'Gripper (μ={np.mean(gripper_deltas_flat):.6f})', edgecolor='black')
    ax.axvline(x=0, color='black', linestyle='--', linewidth=2, label='Zero')

    ax.set_title('Delta Distribution', fontsize=12, fontweight='bold')
    ax.set_xlabel('Delta Value', fontsize=9)
    ax.set_ylabel('Frequency', fontsize=9)
    ax.legend(loc='upper right', fontsize=8)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.subplots_adjust(top=0.93)

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"  ✅ Saved: {output_path.name}")

    plt.close(fig)


def print_summary(data: dict, num_frames: int):
    """Print data summary to console."""
    state = data.get('observation.state')
    action = data.get('action')

    print("\n" + "=" * 60)
    print("DATA SUMMARY")
    print("=" * 60)
    print(f"Total frames: {len(state)}")
    print(f"Visualizing: {num_frames} frames")
    print(f"State shape: {state.shape}")
    print(f"Action shape: {action.shape}")

    if state.shape[1] == 14:
        print("\nDual-arm configuration detected (14 dims)")
        print("  Left arm:  dims 0-5 (joints) + dim 6 (gripper)")
        print("  Right arm: dims 7-12 (joints) + dim 13 (gripper)")

    # Quick delta check
    deltas = action[:num_frames] - state[:num_frames]
    print(f"\nDelta Statistics (first {num_frames} frames):")
    print(f"  Mean |Δ|: {np.mean(np.abs(deltas)):.6f}")
    print(f"  Max  |Δ|: {np.max(np.abs(deltas)):.6f}")

    # Check for problems
    problems = []
    for i in range(state.shape[1]):
        delta_mean = abs(np.mean(deltas[:, i]))
        if delta_mean > DELTA_THRESHOLD:
            problems.append(f"Dim {i}: Δ={delta_mean:.6f}")

    if problems:
        print(f"\n⚠️  POTENTIAL ISSUES (|Δ Mean| > {DELTA_THRESHOLD}):")
        for p in problems:
            print(f"    {p}")
    else:
        print(f"\n✅ All dimensions within tolerance (|Δ Mean| < {DELTA_THRESHOLD})")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    input_path = Path(sys.argv[1])

    # Parse options
    no_save = "--no-save" in sys.argv

    # Parse --frames option
    num_frames = 500  # default
    for i, arg in enumerate(sys.argv):
        if arg == "--frames" and i + 1 < len(sys.argv):
            num_frames = int(sys.argv[i + 1])

    try:
        parquet_path = find_parquet_file(input_path)
        print(f"📂 Loading: {parquet_path}")
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    # Load data
    data = load_parquet(parquet_path)
    state = data.get('observation.state')
    action = data.get('action')

    if state is None or action is None:
        print("❌ Error: observation.state or action not found")
        sys.exit(1)

    # Adjust num_frames if needed
    total_frames = len(state)
    num_frames = min(num_frames, total_frames)

    # Print summary
    print_summary(data, num_frames)

    # Get episode name
    episode_name = get_episode_name(parquet_path)

    # Determine output directory
    episode_dir = parquet_path.parent.parent.parent
    output_dir = episode_dir if not no_save else None

    print("\n" + "=" * 60)
    print("GENERATING VISUALIZATIONS")
    print("=" * 60)

    # Check if dual-arm (14 dims) or single-arm (7 dims)
    num_dims = state.shape[1]

    if num_dims == 14:
        # Dual-arm: generate two figures
        # Left arm: dims 0-6
        visualize_arm(
            state[:, :7], action[:, :7],
            "Left Arm", episode_name, num_frames,
            output_dir / "viz_left_arm.png" if output_dir else None
        )

        # Right arm: dims 7-13
        visualize_arm(
            state[:, 7:], action[:, 7:],
            "Right Arm", episode_name, num_frames,
            output_dir / "viz_right_arm.png" if output_dir else None
        )
    elif num_dims == 7:
        # Single arm
        visualize_arm(
            state, action,
            "Arm", episode_name, num_frames,
            output_dir / "viz_arm.png" if output_dir else None
        )
    else:
        print(f"⚠️  Unexpected dimension: {num_dims}, skipping visualization")

    if output_dir:
        print(f"\n📁 Figures saved to: {output_dir}")

    print("\n✅ Visualization complete!")


if __name__ == "__main__":
    main()
