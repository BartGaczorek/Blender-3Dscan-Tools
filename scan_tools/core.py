"""Geometry algorithms; numpy only, independent of Blender. Coordinates are unitless."""
import numpy as np


def unit(v):
    length = np.linalg.norm(v)
    if length < 1e-12:
        raise ValueError('Degenerate direction')
    return np.asarray(v, dtype=float) / length


def sample_surface(vertices, triangles, count=6000, seed=17):
    rng = np.random.default_rng(seed)
    tri = vertices[triangles]
    areas = np.linalg.norm(np.cross(tri[:, 1]-tri[:, 0], tri[:, 2]-tri[:, 0]), axis=1)
    if not np.isfinite(areas).all() or areas.sum() <= 1e-15:
        raise ValueError('Empty, invalid or degenerate surface')
    chosen = tri[rng.choice(len(tri), count, p=areas/areas.sum())]
    uv = rng.random((count, 2))
    root = np.sqrt(uv[:, 0])
    return ((1-root[:, None])*chosen[:, 0] +
            (root*(1-uv[:, 1]))[:, None]*chosen[:, 1] +
            (root*uv[:, 1])[:, None]*chosen[:, 2])


def pca(points):
    center = np.mean(points, axis=0)
    values, axes = np.linalg.eigh(np.cov((points-center).T))
    return center, axes[:, np.argsort(values)[::-1]]


def fit_plane(points, tolerance=0.006, trials=160):
    """RANSAC followed by TLS. tolerance is relative to the sample bbox diagonal."""
    rng = np.random.default_rng(31)
    scale = np.linalg.norm(np.ptp(points, axis=0))
    best = np.zeros(len(points), dtype=bool)
    for _ in range(trials):
        a, b, c = points[rng.choice(len(points), 3, replace=False)]
        cross = np.cross(b-a, c-a)
        if np.linalg.norm(cross) < 1e-12:
            continue
        n = unit(cross)
        mask = np.abs((points-a) @ n) < tolerance*scale
        if mask.sum() > best.sum():
            best = mask
    if best.sum() < 3:
        raise ValueError('No usable plane')
    center, axes = pca(points[best])
    normal = axes[:, -1]
    # Orient the candidate outward, away from the sampled surface centroid.
    if np.dot(normal, center-np.mean(points, axis=0)) < 0:
        normal = -normal
    rms = float(np.sqrt(np.mean(((points[best]-center) @ normal)**2)))
    return normal, center, float(best.mean()), rms


def reflect(points, normal, offset):
    return points - 2*((points @ normal-offset)[:, None])*normal


def symmetry_fit(points, distance, starts, keep=0.8):
    """Trimmed reflected-point to surface distance. distance takes Nx3 -> N.

    Coordinate descent fits normal (2 DOF) and offset (1 DOF).
    This is local optimization; starts must represent plausible candidate normals.
    """
    center = points.mean(axis=0)
    scale = np.linalg.norm(np.ptp(points, axis=0))
    count = max(3, int(len(points)*keep))

    def score(n, d):
        distances = np.asarray(distance(reflect(points, n, d)))
        if len(distances) != len(points) or not np.isfinite(distances).all():
            raise ValueError('Invalid surface distances')
        return float(np.mean(np.partition(distances**2, count-1)[:count]))

    best = None
    for start in starts:
        n = unit(start)
        d = float(center @ n)
        value = score(n, d)
        for angle in (0.12, 0.04, 0.012, 0.004, 0.001):
            for _ in range(12):
                axis = np.eye(3)[np.argmin(abs(n))]
                u = unit(np.cross(n, axis))
                v = np.cross(n, u)
                candidates = [(n, d+sign*scale*angle*0.25) for sign in (-1, 1)]
                for tangent in (u, v):
                    for sign in (-1, 1):
                        nn = unit(n+sign*angle*tangent)
                        # Keep plane anchored about centroid when tilting.
                        candidates.append((nn, d+float(center @ (nn-n))))
                improved = False
                for nn, dd in candidates:
                    val = score(nn, dd)
                    if val < value:
                        n, d, value = nn, dd, val
                        improved = True
                if not improved:
                    break
        if best is None or value < best[2]:
            best = (n.copy(), d, value)
    n, d, value = best
    residuals = np.asarray(distance(reflect(points, n, d)))
    return n, d, {'trimmed_rms_relative': float(np.sqrt(value)/scale),
                  'p95_relative': float(np.percentile(residuals, 95)/scale),
                  'retained_fraction': keep}


def orientation(points, plane_normal=None, symmetry=None):
    center, axes = pca(points)
    if symmetry is not None:
        x, offset = symmetry
        x = unit(x)
        center = center + (offset-center @ x)*x
        z = plane_normal if plane_normal is not None else axes[:, np.argmin(abs(axes.T @ x))]
        z = np.asarray(z) - np.dot(z, x)*x
        if np.linalg.norm(z) < 0.1:
            z = axes[:, np.argmin(abs(axes.T @ x))]
            z = z-np.dot(z, x)*x
        z = unit(z)
        y = unit(np.cross(z, x))
        z = np.cross(x, y)
    else:
        z = unit(plane_normal if plane_normal is not None else axes[:, 2])
        x = axes[:, 0]-np.dot(axes[:, 0], z)*z
        if np.linalg.norm(x) < 0.1:
            x = axes[:, 1]-np.dot(axes[:, 1], z)*z
        x = unit(x)
        y = unit(np.cross(z, x))
        x = np.cross(y, z)
    rotation = np.stack((x, y, z))
    transform = np.eye(4)
    transform[:3, :3] = rotation
    transform[:3, 3] = -rotation @ center
    return transform
