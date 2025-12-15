"""
Clustering Analysis Utilities

This module provides comprehensive clustering and correlation analysis functions
for gene expression and binding affinity data. It supports hierarchical clustering,
k-means clustering, and correlation matrix computation with various methods.

Key features:
- Hierarchical clustering with customizable linkage methods
- K-means clustering with silhouette score evaluation
- Pearson and Spearman correlation matrix computation
- Matrix reordering based on hierarchical clustering for heatmap visualization
- Performance optimizations for large datasets

Author: Human LncRNA Atlas Project
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
from scipy.cluster.hierarchy import linkage, dendrogram, fcluster
from scipy.spatial.distance import pdist, squareform
from scipy.stats import spearmanr
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

logger = logging.getLogger(__name__)


def hierarchical_cluster(
    data: List[List[float]],
    method: str = "ward",
    metric: str = "euclidean",
    labels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Perform hierarchical clustering on the input data matrix.

    This function computes a hierarchical clustering using scipy's linkage algorithm
    and generates dendrogram data suitable for front-end visualization.

    Args:
        data: 2D array-like of shape (n_samples, n_features). Each row is a sample.
        method: Linkage method. Options: 'ward', 'single', 'complete', 'average',
                'weighted', 'centroid', 'median'. Default is 'ward'.
        metric: Distance metric. Options: 'euclidean', 'cityblock', 'cosine',
                'correlation', etc. Default is 'euclidean'.
                Note: 'ward' method only works with 'euclidean' metric.
        labels: Optional list of labels for samples. Length must match len(data).

    Returns:
        Dictionary containing:
            - linkage_matrix: 2D array of linkage matrix (n_samples-1, 4)
            - dendrogram: Dictionary with dendrogram structure (icoord, dcoord, leaves, etc.)
            - method: The linkage method used
            - metric: The distance metric used
            - labels: The input labels (or None)
            - n_clusters_suggested: Suggested number of clusters based on inconsistency

    Raises:
        ValueError: If data is empty, has wrong shape, or parameters are invalid
        RuntimeError: If clustering computation fails

    Example:
        >>> data = [[1.0, 2.0], [1.5, 1.8], [5.0, 8.0], [8.0, 8.0]]
        >>> result = hierarchical_cluster(data, method='ward')
        >>> print(f"Suggested clusters: {result['n_clusters_suggested']}")
    """
    # Input validation
    if not data:
        raise ValueError("Data cannot be empty")

    data_array = np.array(data, dtype=np.float64)

    if data_array.ndim != 2:
        raise ValueError(f"Data must be 2D array, got shape {data_array.shape}")

    if data_array.shape[0] < 2:
        raise ValueError("Data must have at least 2 samples for clustering")

    if labels is not None and len(labels) != data_array.shape[0]:
        raise ValueError(
            f"Labels length ({len(labels)}) must match data rows ({data_array.shape[0]})"
        )

    # Validate method and metric combination
    if method == "ward" and metric != "euclidean":
        logger.warning(
            "Ward method requires euclidean metric. Overriding metric to 'euclidean'."
        )
        metric = "euclidean"

    try:
        # Compute linkage matrix
        logger.info(
            f"Computing hierarchical clustering: method={method}, metric={metric}, "
            f"n_samples={data_array.shape[0]}, n_features={data_array.shape[1]}"
        )

        linkage_matrix = linkage(data_array, method=method, metric=metric)

        # Generate dendrogram data (without plotting)
        dendrogram_data = dendrogram(
            linkage_matrix, no_plot=True, labels=labels, orientation="top"
        )

        # Suggest number of clusters based on inconsistency
        # Using a simple heuristic: find the largest gap in the linkage distances
        distances = linkage_matrix[:, 2]
        if len(distances) > 2:
            distance_diffs = np.diff(distances)
            max_gap_idx = np.argmax(distance_diffs)
            n_clusters_suggested = len(distances) - max_gap_idx
        else:
            n_clusters_suggested = 2

        # Ensure reasonable cluster count (between 2 and sqrt(n))
        max_clusters = int(np.sqrt(data_array.shape[0]))
        n_clusters_suggested = max(2, min(n_clusters_suggested, max_clusters))

        logger.info(
            f"Hierarchical clustering completed. Suggested clusters: {n_clusters_suggested}"
        )

        return {
            "linkage_matrix": linkage_matrix.tolist(),
            "dendrogram": {
                "icoord": dendrogram_data["icoord"],
                "dcoord": dendrogram_data["dcoord"],
                "ivl": dendrogram_data["ivl"],  # Leaf labels
                "leaves": dendrogram_data["leaves"],  # Leaf ordering
                "color_list": dendrogram_data["color_list"],
            },
            "method": method,
            "metric": metric,
            "labels": labels,
            "n_clusters_suggested": int(n_clusters_suggested),
        }

    except Exception as e:
        logger.error(f"Hierarchical clustering failed: {e}")
        raise RuntimeError(f"Hierarchical clustering computation failed: {e}")


def kmeans_cluster(
    data: List[List[float]],
    n_clusters: int = 5,
    random_state: int = 42,
    n_init: int = 10,
    max_iter: int = 300,
) -> Dict[str, Any]:
    """
    Perform K-means clustering on the input data matrix.

    This function standardizes the data, applies K-means clustering, and evaluates
    the clustering quality using the silhouette score.

    Args:
        data: 2D array-like of shape (n_samples, n_features). Each row is a sample.
        n_clusters: Number of clusters to form. Default is 5.
        random_state: Random seed for reproducibility. Default is 42.
        n_init: Number of times K-means will be run with different centroid seeds.
                Default is 10.
        max_iter: Maximum number of iterations for a single run. Default is 300.

    Returns:
        Dictionary containing:
            - clusters: List of cluster labels (one per sample)
            - centers: 2D array of cluster centers in original feature space
            - centers_scaled: 2D array of cluster centers in standardized space
            - silhouette: Silhouette coefficient (range: -1 to 1, higher is better)
            - inertia: Sum of squared distances to nearest cluster center
            - n_clusters: The number of clusters used
            - n_iter: Number of iterations run by K-means

    Raises:
        ValueError: If data is empty, has wrong shape, or n_clusters is invalid
        RuntimeError: If clustering computation fails

    Example:
        >>> data = [[1.0, 2.0], [1.5, 1.8], [5.0, 8.0], [8.0, 8.0], [7.0, 9.0]]
        >>> result = kmeans_cluster(data, n_clusters=2)
        >>> print(f"Silhouette score: {result['silhouette']:.3f}")
        >>> print(f"Cluster labels: {result['clusters']}")
    """
    # Input validation
    if not data:
        raise ValueError("Data cannot be empty")

    data_array = np.array(data, dtype=np.float64)

    if data_array.ndim != 2:
        raise ValueError(f"Data must be 2D array, got shape {data_array.shape}")

    n_samples = data_array.shape[0]

    if n_samples < 2:
        raise ValueError("Data must have at least 2 samples for clustering")

    if n_clusters < 2:
        raise ValueError(f"n_clusters must be >= 2, got {n_clusters}")

    if n_clusters > n_samples:
        raise ValueError(
            f"n_clusters ({n_clusters}) cannot exceed n_samples ({n_samples})"
        )

    try:
        logger.info(
            f"Computing K-means clustering: n_clusters={n_clusters}, "
            f"n_samples={n_samples}, n_features={data_array.shape[1]}"
        )

        # Standardize features (important for K-means)
        scaler = StandardScaler()
        data_scaled = scaler.fit_transform(data_array)

        # Perform K-means clustering
        kmeans = KMeans(
            n_clusters=n_clusters,
            random_state=random_state,
            n_init=n_init,
            max_iter=max_iter,
        )
        cluster_labels = kmeans.fit_predict(data_scaled)

        # Compute silhouette score (only if we have at least 2 clusters and 2 samples per cluster)
        silhouette = None
        if n_clusters > 1 and n_clusters < n_samples:
            try:
                silhouette = silhouette_score(data_scaled, cluster_labels)
            except Exception as e:
                logger.warning(f"Could not compute silhouette score: {e}")
                silhouette = None

        # Transform cluster centers back to original feature space
        centers_scaled = kmeans.cluster_centers_
        centers_original = scaler.inverse_transform(centers_scaled)

        if silhouette is not None:
            logger.info(f"K-means clustering completed. Silhouette score: {silhouette:.4f}")
        else:
            logger.info("K-means clustering completed. Silhouette score: N/A")

        return {
            "clusters": cluster_labels.tolist(),
            "centers": centers_original.tolist(),
            "centers_scaled": centers_scaled.tolist(),
            "silhouette": float(silhouette) if silhouette is not None else None,
            "inertia": float(kmeans.inertia_),
            "n_clusters": int(n_clusters),
            "n_iter": int(kmeans.n_iter_),
        }

    except Exception as e:
        logger.error(f"K-means clustering failed: {e}")
        raise RuntimeError(f"K-means clustering computation failed: {e}")


def compute_correlation_matrix(
    data: List[List[float]], method: str = "pearson", labels: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Compute correlation matrix between samples.

    This function calculates pairwise correlations between all samples (rows)
    in the data matrix using either Pearson or Spearman correlation.

    Args:
        data: 2D array-like of shape (n_samples, n_features). Each row is a sample.
        method: Correlation method. Options: 'pearson', 'spearman'. Default is 'pearson'.
        labels: Optional list of labels for samples. Length must match len(data).

    Returns:
        Dictionary containing:
            - correlation_matrix: 2D symmetric correlation matrix (n_samples, n_samples)
            - method: The correlation method used
            - labels: The input labels (or None)
            - n_samples: Number of samples
            - n_features: Number of features

    Raises:
        ValueError: If data is empty, has wrong shape, or method is invalid
        RuntimeError: If correlation computation fails

    Example:
        >>> data = [[1.0, 2.0, 3.0], [1.5, 2.5, 3.5], [5.0, 8.0, 11.0]]
        >>> result = compute_correlation_matrix(data, method='pearson')
        >>> print(f"Correlation shape: {np.array(result['correlation_matrix']).shape}")
    """
    # Input validation
    if not data:
        raise ValueError("Data cannot be empty")

    data_array = np.array(data, dtype=np.float64)

    if data_array.ndim != 2:
        raise ValueError(f"Data must be 2D array, got shape {data_array.shape}")

    if data_array.shape[0] < 2:
        raise ValueError("Data must have at least 2 samples for correlation")

    if labels is not None and len(labels) != data_array.shape[0]:
        raise ValueError(
            f"Labels length ({len(labels)}) must match data rows ({data_array.shape[0]})"
        )

    if method not in ["pearson", "spearman"]:
        raise ValueError(f"Method must be 'pearson' or 'spearman', got '{method}'")

    try:
        logger.info(
            f"Computing {method} correlation matrix: "
            f"n_samples={data_array.shape[0]}, n_features={data_array.shape[1]}"
        )

        if method == "pearson":
            # Pearson correlation: compute correlation between rows
            correlation_matrix = np.corrcoef(data_array)
        else:  # spearman
            # Spearman correlation: rank-based correlation
            correlation_matrix, _ = spearmanr(data_array, axis=1)

            # spearmanr returns a scalar if only 2 samples, reshape to 2D
            if data_array.shape[0] == 2 and np.isscalar(correlation_matrix):
                correlation_matrix = np.array([[1.0, correlation_matrix],
                                               [correlation_matrix, 1.0]])

        # Handle NaN values (can occur if a sample has zero variance)
        correlation_matrix = np.nan_to_num(correlation_matrix, nan=0.0)

        logger.info(f"{method.capitalize()} correlation matrix computed successfully")

        return {
            "correlation_matrix": correlation_matrix.tolist(),
            "method": method,
            "labels": labels,
            "n_samples": int(data_array.shape[0]),
            "n_features": int(data_array.shape[1]),
        }

    except Exception as e:
        logger.error(f"Correlation matrix computation failed: {e}")
        raise RuntimeError(f"Correlation computation failed: {e}")


def reorder_by_clustering(
    matrix: List[List[float]], labels: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Reorder matrix rows and columns based on hierarchical clustering.

    This function is specifically designed for creating clustered heatmaps. It performs
    hierarchical clustering on both rows and columns (if matrix is square) and reorders
    them according to the dendrogram leaf order for optimal visualization.

    Args:
        matrix: 2D array-like of shape (n_rows, n_cols). The data matrix to reorder.
        labels: Optional list of labels for rows. Length must match matrix rows.
                If matrix is square, these labels will be used for both axes.

    Returns:
        Dictionary containing:
            - reordered_matrix: 2D array with rows and columns reordered
            - row_order: List of indices showing the new row order
            - col_order: List of indices showing the new column order
            - row_labels: Reordered row labels (if provided)
            - col_labels: Reordered column labels (if matrix is square and labels provided)
            - row_dendrogram: Dendrogram data for rows (icoord, dcoord, leaves)
            - col_dendrogram: Dendrogram data for columns (None if matrix not square)

    Raises:
        ValueError: If matrix is empty or has wrong shape
        RuntimeError: If clustering computation fails

    Example:
        >>> matrix = [[1.0, 0.8], [0.8, 1.0]]
        >>> labels = ['Gene1', 'Gene2']
        >>> result = reorder_by_clustering(matrix, labels)
        >>> print(f"Row order: {result['row_order']}")
        >>> print(f"Reordered labels: {result['row_labels']}")
    """
    # Input validation
    if not matrix:
        raise ValueError("Matrix cannot be empty")

    matrix_array = np.array(matrix, dtype=np.float64)

    if matrix_array.ndim != 2:
        raise ValueError(f"Matrix must be 2D array, got shape {matrix_array.shape}")

    n_rows, n_cols = matrix_array.shape

    if n_rows < 2:
        raise ValueError("Matrix must have at least 2 rows for clustering")

    if labels is not None and len(labels) != n_rows:
        raise ValueError(
            f"Labels length ({len(labels)}) must match matrix rows ({n_rows})"
        )

    try:
        logger.info(
            f"Reordering matrix by clustering: shape=({n_rows}, {n_cols})"
        )

        # Cluster rows
        row_linkage = linkage(matrix_array, method="average", metric="euclidean")
        row_dendrogram = dendrogram(row_linkage, no_plot=True)
        row_order = row_dendrogram["leaves"]

        # Reorder rows
        reordered_matrix = matrix_array[row_order, :]

        # Reorder row labels
        reordered_row_labels = None
        if labels is not None:
            reordered_row_labels = [labels[i] for i in row_order]

        # Cluster columns (only if different from rows or if square matrix)
        col_order = None
        col_dendrogram_data = None
        reordered_col_labels = None

        if n_cols >= 2:
            # Transpose for column clustering
            col_linkage = linkage(matrix_array.T, method="average", metric="euclidean")
            col_dendrogram = dendrogram(col_linkage, no_plot=True)
            col_order = col_dendrogram["leaves"]

            # Reorder columns
            reordered_matrix = reordered_matrix[:, col_order]

            col_dendrogram_data = {
                "icoord": col_dendrogram["icoord"],
                "dcoord": col_dendrogram["dcoord"],
                "leaves": col_dendrogram["leaves"],
                "color_list": col_dendrogram["color_list"],
            }

            # If square matrix and labels provided, use same labels for columns
            if n_rows == n_cols and labels is not None:
                reordered_col_labels = [labels[i] for i in col_order]

        logger.info(
            f"Matrix reordering completed. New order: rows={row_order}, cols={col_order}"
        )

        return {
            "reordered_matrix": reordered_matrix.tolist(),
            "row_order": row_order,
            "col_order": col_order if col_order is not None else list(range(n_cols)),
            "row_labels": reordered_row_labels,
            "col_labels": reordered_col_labels,
            "row_dendrogram": {
                "icoord": row_dendrogram["icoord"],
                "dcoord": row_dendrogram["dcoord"],
                "leaves": row_dendrogram["leaves"],
                "color_list": row_dendrogram["color_list"],
            },
            "col_dendrogram": col_dendrogram_data,
        }

    except Exception as e:
        logger.error(f"Matrix reordering failed: {e}")
        raise RuntimeError(f"Matrix reordering computation failed: {e}")


def find_optimal_clusters(
    data: List[List[float]], max_clusters: int = 10, method: str = "silhouette"
) -> Dict[str, Any]:
    """
    Find optimal number of clusters for the data using silhouette or elbow method.

    This helper function evaluates clustering quality for different numbers of clusters
    and suggests the optimal number.

    Args:
        data: 2D array-like of shape (n_samples, n_features). Each row is a sample.
        max_clusters: Maximum number of clusters to evaluate. Default is 10.
        method: Evaluation method. Options: 'silhouette', 'elbow'. Default is 'silhouette'.

    Returns:
        Dictionary containing:
            - optimal_k: Suggested optimal number of clusters
            - scores: List of scores for each k (silhouette scores or inertias)
            - k_range: List of k values evaluated
            - method: The evaluation method used

    Raises:
        ValueError: If data is empty or max_clusters is invalid
        RuntimeError: If evaluation fails

    Example:
        >>> data = [[1.0, 2.0], [1.5, 1.8], [5.0, 8.0], [8.0, 8.0], [7.0, 9.0]]
        >>> result = find_optimal_clusters(data, max_clusters=4)
        >>> print(f"Optimal K: {result['optimal_k']}")
    """
    # Input validation
    if not data:
        raise ValueError("Data cannot be empty")

    data_array = np.array(data, dtype=np.float64)
    n_samples = data_array.shape[0]

    if n_samples < 2:
        raise ValueError("Data must have at least 2 samples")

    if method not in ["silhouette", "elbow"]:
        raise ValueError(f"Method must be 'silhouette' or 'elbow', got '{method}'")

    # Limit max_clusters to reasonable range
    max_clusters = min(max_clusters, n_samples - 1)
    if max_clusters < 2:
        raise ValueError("max_clusters must be at least 2")

    try:
        logger.info(f"Finding optimal clusters using {method} method (2 to {max_clusters})")

        # Standardize data
        scaler = StandardScaler()
        data_scaled = scaler.fit_transform(data_array)

        k_range = list(range(2, max_clusters + 1))
        scores = []

        for k in k_range:
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = kmeans.fit_predict(data_scaled)

            if method == "silhouette":
                score = silhouette_score(data_scaled, labels)
            else:  # elbow
                score = kmeans.inertia_

            scores.append(score)

        # Find optimal k
        if method == "silhouette":
            # Higher silhouette is better
            optimal_idx = np.argmax(scores)
        else:  # elbow
            # Find the "elbow" point using the kneedle algorithm (simplified)
            # Compute the rate of change
            if len(scores) >= 3:
                rate_of_change = np.diff(scores)
                second_derivative = np.diff(rate_of_change)
                # Find the point with maximum curvature
                optimal_idx = np.argmax(np.abs(second_derivative)) + 1
            else:
                optimal_idx = 0

        optimal_k = k_range[optimal_idx]

        logger.info(f"Optimal K found: {optimal_k} ({method} score: {scores[optimal_idx]:.4f})")

        return {
            "optimal_k": int(optimal_k),
            "scores": [float(s) for s in scores],
            "k_range": k_range,
            "method": method,
        }

    except Exception as e:
        logger.error(f"Optimal cluster finding failed: {e}")
        raise RuntimeError(f"Optimal cluster evaluation failed: {e}")
