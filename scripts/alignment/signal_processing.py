"""
Signal processing module for alignment analysis.

Includes denoising, peak detection, and offset computation.
"""

from dataclasses import dataclass
from typing import Literal

import numpy as np

from .config import ANALYSIS_CONFIG, LEFT_GRIPPER_DIM


@dataclass
class AlignmentEvent:
    """Single alignment event result."""
    frame: int
    state_peak: int
    video_peak: int
    offset: int
    offset_ms: float
    state_change: float


class SignalProcessor:
    """Signal processing for alignment analysis."""

    def __init__(self, fps: float = 25.0):
        self.fps = fps
        self.config = ANALYSIS_CONFIG

    def compute_state_diff(self, state: np.ndarray, gripper_dim: int = LEFT_GRIPPER_DIM) -> np.ndarray:
        """Compute absolute difference of gripper state."""
        gripper_state = state[:, gripper_dim]
        return np.abs(np.concatenate([[0], np.diff(gripper_state)]))

    def find_significant_changes(self, state: np.ndarray, gripper_dim: int = LEFT_GRIPPER_DIM,
                                  threshold: float = None) -> np.ndarray:
        """
        Find frames where gripper state changes significantly.

        Args:
            state: State array [N, dim]
            gripper_dim: Gripper dimension index
            threshold: Minimum change threshold

        Returns:
            Array of frame indices with significant changes
        """
        threshold = threshold or self.config["state_change_threshold"]
        gripper_state = state[:, gripper_dim]
        state_diff = np.abs(np.diff(gripper_state))
        return np.where(state_diff > threshold)[0]

    def compute_offsets(self, state_diff: np.ndarray, video_diff: np.ndarray,
                        significant_frames: np.ndarray,
                        search_window: int = None) -> list[AlignmentEvent]:
        """
        Compute time offsets between state and video changes.

        For each significant state change, find the nearest video peak
        within the search window.

        Args:
            state_diff: State difference signal
            video_diff: Video difference signal
            significant_frames: Frames with significant state changes
            search_window: Window size for searching video peak

        Returns:
            List of AlignmentEvent results
        """
        search_window = search_window or self.config["search_window"]
        results = []

        for sf in significant_frames:
            start = max(0, sf - search_window)
            end = min(len(video_diff), sf + search_window + 1)

            local_video = video_diff[start:end]
            if len(local_video) == 0:
                continue

            video_peak = start + np.argmax(local_video)
            offset = video_peak - sf

            results.append(AlignmentEvent(
                frame=int(sf),
                state_peak=int(sf),
                video_peak=int(video_peak),
                offset=int(offset),
                offset_ms=float(offset * 1000 / self.fps),
                state_change=float(state_diff[sf])
            ))

        return results

    def denoise(self, video_diff: np.ndarray, state_diff: np.ndarray,
                method: Literal["state_guided", "weighted", "adaptive"] = "state_guided",
                window_size: int = None) -> np.ndarray:
        """
        Denoise video signal using state signal as reference.

        Args:
            video_diff: Raw video difference signal
            state_diff: State difference signal (reference)
            method: Denoising method
            window_size: Window size for denoising

        Returns:
            Denoised video signal
        """
        window_size = window_size or self.config["denoise_window"]

        if method == "state_guided":
            return self._denoise_state_guided(video_diff, state_diff, window_size)
        elif method == "weighted":
            return self._denoise_weighted(video_diff, state_diff, window_size)
        elif method == "adaptive":
            return self._denoise_adaptive(video_diff, state_diff, window_size)
        else:
            raise ValueError(f"Unknown denoising method: {method}")

    def _denoise_state_guided(self, video_diff: np.ndarray, state_diff: np.ndarray,
                               window_size: int) -> np.ndarray:
        """State-guided windowing denoising."""
        denoised = np.zeros_like(video_diff)

        # Find significant state changes
        state_threshold = np.median(state_diff) + 0.5 * np.std(state_diff)
        significant_indices = np.where(state_diff > state_threshold)[0]

        # Apply Gaussian-weighted windows around state events
        for idx in significant_indices:
            start = max(0, idx - window_size)
            end = min(len(video_diff), idx + window_size + 1)

            # Gaussian weights centered at state event
            local_indices = np.arange(start, end)
            weights = np.exp(-0.5 * ((local_indices - idx) / (window_size / 2)) ** 2)

            # Apply weighted video signal
            denoised[start:end] = np.maximum(
                denoised[start:end],
                video_diff[start:end] * weights
            )

        return denoised

    def _denoise_weighted(self, video_diff: np.ndarray, state_diff: np.ndarray,
                           window_size: int) -> np.ndarray:
        """Weight video signal by state envelope."""
        state_norm = state_diff / (state_diff.max() + 1e-8)

        # Smooth state signal to create envelope
        kernel_size = window_size * 2 + 1
        kernel = np.ones(kernel_size) / kernel_size
        state_envelope = np.convolve(state_norm, kernel, mode="same")
        state_envelope = np.clip(state_envelope * 3, 0, 1)

        return video_diff * state_envelope

    def _denoise_adaptive(self, video_diff: np.ndarray, state_diff: np.ndarray,
                           window_size: int) -> np.ndarray:
        """Adaptive thresholding based on state activity."""
        denoised = np.zeros_like(video_diff)
        median_state = np.median(state_diff)

        for i in range(len(video_diff)):
            start = max(0, i - window_size)
            end = min(len(video_diff), i + window_size + 1)

            local_state = state_diff[start:end]
            state_activity = local_state.max()

            if state_activity > median_state:
                denoised[i] = video_diff[i]
            else:
                denoised[i] = video_diff[i] * 0.1

        return denoised

    def compute_correlation(self, signal1: np.ndarray, signal2: np.ndarray) -> float:
        """Compute normalized correlation between two signals."""
        s1_norm = (signal1 - signal1.mean()) / (signal1.std() + 1e-8)
        s2_norm = (signal2 - signal2.mean()) / (signal2.std() + 1e-8)
        return float(np.corrcoef(s1_norm, s2_norm)[0, 1])
