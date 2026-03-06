#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Quality metrics for the image optimizer.

Provides alpha-weighted SSIM computation as a standalone function.
"""

from __future__ import annotations

import numpy as np


def ssim_from_arrays(orig: np.ndarray, quant: np.ndarray) -> float:
    """Alpha-weighted SSIM between two RGBA float64 arrays.

    Uses a 7×7 box filter (Wang et al.) with local alpha density
    weighting so transparent spritesheet regions do not inflate
    the similarity score.
    Args:
        orig: Original image as an ``(H, W, C)`` float64 array.
        quant: Quantized image with the same shape as *orig*.
    Returns:
        Value in ``[0, 1]`` (1 = identical).
    """
    if orig.shape != quant.shape:
        return 0.0

    L = 255.0
    C1 = (0.01 * L) ** 2
    C2 = (0.03 * L) ** 2
    win = 7

    def _box_mean(arr: np.ndarray) -> np.ndarray:
        h, w = arr.shape
        if h < win or w < win:
            return np.full_like(arr, arr.mean())
        cum = np.cumsum(np.cumsum(arr, axis=0), axis=1)
        cum = np.pad(cum, ((1, 0), (1, 0)), mode="constant")
        return (
            cum[win:, win:] - cum[:-win, win:] - cum[win:, :-win] + cum[:-win, :-win]
        ) / (win * win)

    has_alpha = orig.ndim == 3 and orig.shape[2] >= 4
    alpha_2d = orig[:, :, 3] / 255.0 if has_alpha else np.ones(orig.shape[:2])
    h, w = alpha_2d.shape
    alpha_weight = (
        _box_mean(alpha_2d)
        if h >= win and w >= win
        else np.full_like(alpha_2d, alpha_2d.mean())
    )
    alpha_weight_sum = float(alpha_weight.sum())
    use_alpha = alpha_weight_sum > 0.0

    num_channels = orig.shape[2] if orig.ndim == 3 else 1
    ssim_sum = 0.0

    for c in range(num_channels):
        x = orig[:, :, c] if num_channels > 1 else orig
        y = quant[:, :, c] if num_channels > 1 else quant

        mu_x = _box_mean(x)
        mu_y = _box_mean(y)

        sigma_x_sq = np.maximum(_box_mean(x * x) - mu_x * mu_x, 0.0)
        sigma_y_sq = np.maximum(_box_mean(y * y) - mu_y * mu_y, 0.0)
        sigma_xy = _box_mean(x * y) - mu_x * mu_y

        numerator = (2.0 * mu_x * mu_y + C1) * (2.0 * sigma_xy + C2)
        denominator = (mu_x**2 + mu_y**2 + C1) * (sigma_x_sq + sigma_y_sq + C2)

        ssim_map = numerator / denominator

        if use_alpha:
            ssim_sum += float(np.sum(ssim_map * alpha_weight) / alpha_weight_sum)
        else:
            ssim_sum += float(np.mean(ssim_map))

    return max(0.0, min(1.0, ssim_sum / num_channels))
