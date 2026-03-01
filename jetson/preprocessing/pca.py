"""
PCA — Dimensionality reduction for CSI subcarrier data.

WiFi CSI has many subcarriers (~52 for 20MHz), but not all carry useful
motion information. PCA identifies the principal components that capture
the most variance (i.e., the subcarriers most reactive to human movement).
"""

import numpy as np
from sklearn.decomposition import PCA


def fit_pca(amplitude: np.ndarray, n_components: int = 10,
            variance_threshold: float = 0.95) -> tuple:
    """
    Fit PCA on CSI amplitude data.

    Args:
        amplitude: (n_samples, n_subcarriers) array
        n_components: Max components to keep
        variance_threshold: Keep enough components to explain this fraction
                           of total variance (overrides n_components if fewer needed)
    Returns:
        (pca_model, transformed_data, explained_variance_ratio)
    """
    # Fit PCA
    pca = PCA(n_components=min(n_components, amplitude.shape[1]))
    transformed = pca.fit_transform(amplitude)

    # Find how many components needed for threshold
    cumulative_variance = np.cumsum(pca.explained_variance_ratio_)
    n_sufficient = np.searchsorted(cumulative_variance, variance_threshold) + 1
    n_sufficient = min(n_sufficient, pca.n_components_)

    print(f"[pca] {n_sufficient} components explain "
          f"{cumulative_variance[n_sufficient - 1]:.1%} of variance")

    return pca, transformed[:, :n_sufficient], pca.explained_variance_ratio_


def apply_pca(pca: PCA, amplitude: np.ndarray, n_components: int = None) -> np.ndarray:
    """
    Apply a pre-fitted PCA model to new data.

    Args:
        pca: Fitted PCA model from fit_pca()
        amplitude: (n_samples, n_subcarriers) array
        n_components: Number of components to keep (default: all fitted)
    Returns:
        (n_samples, n_components) reduced array
    """
    transformed = pca.transform(amplitude)
    if n_components:
        transformed = transformed[:, :n_components]
    return transformed
