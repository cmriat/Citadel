"""
Visualization module for alignment analysis.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


class AlignmentVisualizer:
    """Visualizer for alignment analysis results."""

    def __init__(self, figsize: tuple[int, int] = (14, 10)):
        self.figsize = figsize

    def create_report(self, state_diff: np.ndarray, video_diff: np.ndarray,
                      offsets: list[int], output_path: Path, episode: int,
                      zoom_range: tuple[int, int] = None) -> None:
        """
        Create visualization report with three subplots.

        Args:
            state_diff: State difference array
            video_diff: Video difference array
            offsets: List of offset values
            output_path: Path to save figure
            episode: Episode index
            zoom_range: Optional (start, end) for zoomed view
        """
        _fig, axes = plt.subplots(3, 1, figsize=self.figsize)

        # Normalize video_diff for comparison
        video_max = video_diff.max() if video_diff.max() > 0 else 1
        state_max = state_diff.max() if state_diff.max() > 0 else 1
        video_diff_scaled = video_diff / video_max * state_max

        # Plot 1: Full timeline
        self._plot_timeline(axes[0], state_diff, video_diff_scaled)

        # Plot 2: Zoomed view
        zoom_range = zoom_range or self._auto_zoom_range(state_diff)
        self._plot_zoomed(axes[1], state_diff, video_diff_scaled, zoom_range)

        # Plot 3: Offset distribution
        self._plot_distribution(axes[2], offsets)

        plt.suptitle(f"Episode {episode}: Frame vs State/Action Alignment Analysis", fontsize=14)
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close()

    def _plot_timeline(self, ax, state_diff: np.ndarray, video_diff_scaled: np.ndarray) -> None:
        """Plot full timeline comparison."""
        ax.plot(state_diff, "b-", linewidth=0.8, label="State diff", alpha=0.8)
        ax.plot(video_diff_scaled, "r-", linewidth=0.8, label="Video diff (scaled)", alpha=0.6)
        ax.set_ylabel("Difference")
        ax.set_title("State Diff vs Video Frame Diff (Full Timeline)")
        ax.legend()
        ax.grid(True, alpha=0.3)

    def _plot_zoomed(self, ax, state_diff: np.ndarray, video_diff_scaled: np.ndarray,
                     zoom_range: tuple[int, int]) -> None:
        """Plot zoomed view of active region."""
        start, end = zoom_range
        frames = np.arange(start, end)

        ax.plot(frames, state_diff[start:end], "b-o", linewidth=2, markersize=3, label="State diff")
        ax.plot(frames, video_diff_scaled[start:end], "r--s", linewidth=2, markersize=3,
                label="Video diff (scaled)")
        ax.set_xlabel("Frame")
        ax.set_ylabel("Difference")
        ax.set_title(f"Zoomed View: Frames {start}-{end}")
        ax.legend()
        ax.grid(True, alpha=0.3)

    def _plot_distribution(self, ax, offsets: list[int]) -> None:
        """Plot offset distribution histogram."""
        if len(offsets) > 0:
            bins = range(min(offsets) - 1, max(offsets) + 3)
            ax.hist(offsets, bins=bins, align="left", color="steelblue",
                    edgecolor="black", alpha=0.7)
            ax.axvline(x=np.mean(offsets), color="red", linestyle="--",
                       label=f"Mean: {np.mean(offsets):+.1f} frames")
            ax.axvline(x=np.median(offsets), color="orange", linestyle="--",
                       label=f"Median: {np.median(offsets):+.1f} frames")

        ax.set_xlabel("Offset (frames)")
        ax.set_ylabel("Count")
        ax.set_title("Distribution of Video-State Offset")
        ax.legend()
        ax.grid(True, alpha=0.3, axis="y")

    def _auto_zoom_range(self, state_diff: np.ndarray, window: int = 50) -> tuple[int, int]:
        """Auto-select a region with activity for zoomed view."""
        activity = np.convolve(state_diff, np.ones(window), mode="same")
        peak = np.argmax(activity)
        start = max(0, peak - window)
        end = min(len(state_diff), peak + window)
        return (start, end)
