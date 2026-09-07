"""Grid <-> map-frame geometry.

Pure NumPy: no rclpy, no ROS message packages, no FastAPI. The ROS 2 shell
imports this so the integration's maths is unit-testable without a ROS
installation.

This module is the CANONICAL pixel -> projected-metres conversion.
``app.corridor`` delegates to it; ``app.serializer`` applies the same
formula before projecting on to WGS84. Faz 2's C2 finding was exactly this
formula drifting apart across copies -- keep it in one place.

Conventions
-----------
K1  x = origin_x + col * resolution_m ; y = origin_y - row * resolution_m
    ``origin`` is the raster window's TOP-LEFT corner and rows increase
    southward.
K3  grid_map counts its indices AGAINST the map axes, so converting a
    LunaPath (rows, cols) array into a grid_map matrix is a transpose plus a
    flip -- not merely a column-major flatten. See the Faz 4 plan's "Ortak
    bağlam" section for the derivation.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def _geometry(metadata: dict[str, Any]) -> tuple[float, float, float, int, int]:
    origin = metadata.get("origin") or {}
    origin_x = float(origin.get("x", 0.0))
    origin_y = float(origin.get("y", 0.0))
    resolution = float(metadata["resolution_m"])
    shape = metadata.get("shape") or [0, 0]
    return origin_x, origin_y, resolution, int(shape[0]), int(shape[1])


# ── K1: pixel <-> projected metres ──────────────────────────────────────────

def pixel_to_map_xy(row: int, col: int, metadata: dict[str, Any]) -> tuple[float, float]:
    """(row, col) -> projected CRS metres (x east, y north).

    The row term is SUBTRACTED: ``origin`` is the window's top edge and rows
    increase southward. (Faz 2 review, C2.)
    """
    origin_x, origin_y, resolution, _rows, _cols = _geometry(metadata)
    return (origin_x + col * resolution, origin_y - row * resolution)


def map_xy_to_pixel(x: float, y: float, metadata: dict[str, Any]) -> tuple[int, int]:
    """Projected CRS metres -> nearest (row, col). Raises if out of grid."""
    origin_x, origin_y, resolution, rows, cols = _geometry(metadata)
    col = int(round((float(x) - origin_x) / resolution))
    row = int(round((origin_y - float(y)) / resolution))
    if not (0 <= row < rows and 0 <= col < cols):
        raise ValueError(
            f"({x}, {y}) maps to ({row}, {col}), outside the {rows}x{cols} grid"
        )
    return row, col


# ── K4: grid_map geometry ───────────────────────────────────────────────────

def grid_map_info(metadata: dict[str, Any]) -> dict[str, float]:
    """Extent and centre pose for grid_map_msgs/GridMapInfo.

    ``pose`` is the map CENTRE. It is derived (Faz 4 plan, K4) so that the
    grid_map cell centre for our pixel (r, c) lands exactly on
    ``pixel_to_map_xy(r, c)`` -- hence the ``(n - 1)`` half-cell terms rather
    than a plain ``origin +/- length / 2``. Without this the published
    nav_msgs/Path sits half a cell away from the published terrain.
    """
    origin_x, origin_y, resolution, rows, cols = _geometry(metadata)
    return {
        "resolution": resolution,
        "length_x": cols * resolution,   # easting extent  <- columns
        "length_y": rows * resolution,   # northing extent <- rows
        "pose_x": origin_x + 0.5 * (cols - 1) * resolution,
        "pose_y": origin_y - 0.5 * (rows - 1) * resolution,
    }


# ── K3: orientation ─────────────────────────────────────────────────────────

def to_grid_map_matrix(array: np.ndarray) -> np.ndarray:
    """LunaPath (rows, cols) -> grid_map Eigen matrix (size_x, size_y).

    grid_map index i runs along DECREASING x, index j along DECREASING y.
    Our col runs along increasing x and our row along decreasing y, so
    ``i = (cols - 1) - col`` and ``j = row``:

        G[i][j] = M[j][(cols - 1) - i]   ==   np.flipud(M.T)

    Getting this wrong is what makes the map appear rotated 90 degrees in
    RViz. A column-major flatten alone does NOT fix it -- that only changes
    byte order, not which of our axes becomes grid_map's x.
    """
    arr = np.asarray(array, dtype=np.float32)
    if arr.ndim != 2:
        raise ValueError(f"expected a 2-D grid, got shape {arr.shape}")
    return np.flipud(arr.T)


def from_grid_map_matrix(matrix: np.ndarray) -> np.ndarray:
    """Inverse of :func:`to_grid_map_matrix`."""
    mat = np.asarray(matrix, dtype=np.float32)
    if mat.ndim != 2:
        raise ValueError(f"expected a 2-D matrix, got shape {mat.shape}")
    return np.flipud(mat).T


def to_multiarray_layout(
    array: np.ndarray,
) -> tuple[list[tuple[str, int, int]], np.ndarray]:
    """Flatten a LunaPath grid the way grid_map_msgs expects.

    Mirrors grid_map's ``matrixEigenCopyToMultiArrayMessage`` for a
    column-major Eigen matrix: ``dim[0]`` is the outer (column) dimension,
    ``dim[1]`` the inner (row) one.
    """
    matrix = to_grid_map_matrix(array)
    size_x, size_y = matrix.shape          # (cols, rows) of the source grid
    dims = [
        ("column_index", size_y, size_x * size_y),
        ("row_index", size_x, size_x),
    ]
    return dims, matrix.flatten(order="F")


def from_multiarray_layout(
    dims: list[tuple[str, int, int]], flat: np.ndarray
) -> np.ndarray:
    """Inverse of :func:`to_multiarray_layout` -- back to LunaPath (rows, cols)."""
    sizes = {label: size for label, size, _stride in dims}
    size_x = sizes["row_index"]      # grid_map Eigen rows
    size_y = sizes["column_index"]   # grid_map Eigen columns
    matrix = np.asarray(flat, dtype=np.float32).reshape((size_x, size_y), order="F")
    return from_grid_map_matrix(matrix)
