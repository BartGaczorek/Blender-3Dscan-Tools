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


def symmetry_fit(points, distance, starts, keep=0.8, progress=None):
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
    for start_index, start in enumerate(starts):
        n = unit(start)
        d = float(center @ n)
        value = score(n, d)
        for level, angle in enumerate((0.12, 0.04, 0.012, 0.004, 0.001)):
            if progress:
                progress((start_index*5+level)/(len(starts)*5), f"Symetria: kandydat {start_index+1}/{len(starts)}, krok {level+1}/5")
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
    if progress:
        progress(1.0, "Dopasowanie symetrii zakończone")
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


def triangle_plane(vertices, triangles):
    """Area-weighted TLS of continuous triangle surfaces, independent of tessellation."""
    tri = np.asarray(vertices, float)[triangles]
    cross = np.cross(tri[:, 1]-tri[:, 0], tri[:, 2]-tri[:, 0])
    areas = np.linalg.norm(cross, axis=1)*0.5
    valid = areas > 1e-18
    tri, cross, areas = tri[valid], cross[valid], areas[valid]
    if len(tri) < 2 or areas.sum() <= 0:
        raise ValueError('Wybierz co najmniej dwa niezdegenerowane trójkąty')
    weights = areas / areas.sum()
    center = np.sum(tri.mean(axis=1)*weights[:, None], axis=0)
    # Subtract first: avoid catastrophic cancellation far from the world origin.
    q = tri-center
    total = q.sum(axis=1)
    second = (np.einsum('tki,tkj->tij', q, q) +
              np.einsum('ti,tj->tij', total, total))/12.0
    covariance = np.einsum('t,tij->ij', weights, second)
    values, vectors = np.linalg.eigh(covariance)
    if values[1] < 1e-16*max(values[-1], 1e-30):
        raise ValueError('Obszar jest zbyt wąski do wyznaczenia płaszczyzny')
    normal = vectors[:, 0]
    if np.dot(normal, cross.sum(axis=0)) < 0:
        normal = -normal
    deviations = (tri-center) @ normal
    return {'normal': normal.tolist(), 'center': center.tolist(),
            'rms': float(np.sqrt(max(0, values[0]))),
            'max_deviation': float(np.abs(deviations).max()),
            'area': float(areas.sum()), 'triangles': int(len(tri))}


def triangle_adjacency(triangles):
    """Edge-connected adjacency; coincident disconnected components stay separate."""
    adjacency = [[] for _ in range(len(triangles))]
    edges = {}
    for face, tri in enumerate(triangles):
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            edge = (min(int(a), int(b)), max(int(a), int(b)))
            edges.setdefault(edge, []).append(face)
    for faces in edges.values():
        for a in faces:
            adjacency[a].extend(b for b in faces if b != a)
    return adjacency


def planar_region(vertices, triangles, seed, angle_degrees=25, distance_relative=0.002,
                  adjacency=None):
    """Grow connected faces against a FIXED seed plane, not a drifting neighbour normal.

    The fixed normal + slab prevent gradual flood-fill around cylindrical surfaces.
    Grow and refit once to reduce the effect of scan noise in the clicked triangle.
    """
    if not 0 <= seed < len(triangles):
        raise ValueError('Nieprawidłowy trójkąt')
    tri = vertices[triangles]
    cross = np.cross(tri[:, 1]-tri[:, 0], tri[:, 2]-tri[:, 0])
    norms = np.linalg.norm(cross, axis=1)
    normals = cross / np.maximum(norms[:, None], 1e-30)
    if norms[seed] < 1e-18:
        raise ValueError('Kliknięty trójkąt jest zdegenerowany')
    adjacency = triangle_adjacency(triangles) if adjacency is None else adjacency
    scale = float(np.linalg.norm(np.ptp(vertices, axis=0)))
    threshold = max(scale*distance_relative, 1e-12)
    cosine = np.cos(np.deg2rad(angle_degrees))
    normal = normals[seed]
    center = tri[seed].mean(axis=0)
    region = [seed]
    for _ in range(2):
        accepted = ((normals @ normal >= cosine) &
                    (np.max(np.abs((tri-center) @ normal), axis=1) <= threshold))
        accepted[seed] = True
        visited = {seed}
        stack = [seed]
        while stack:
            face = stack.pop()
            for neighbour in adjacency[face]:
                if neighbour not in visited and accepted[neighbour]:
                    visited.add(neighbour)
                    stack.append(neighbour)
        region = sorted(visited)
        if len(region) < 2:
            raise ValueError('Za mały obszar. Kliknij wnętrze ścianki lub zwiększ tolerancję')
        fit = triangle_plane(vertices, triangles[region])
        normal, center = np.array(fit['normal']), np.array(fit['center'])
    fit['faces'] = region
    fit['rms_relative'] = fit['rms']/max(scale, 1e-30)
    fit['max_deviation_relative'] = fit['max_deviation']/max(scale, 1e-30)
    return fit
