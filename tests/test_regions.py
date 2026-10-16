import importlib.util
from pathlib import Path
import unittest
import numpy as np

spec = importlib.util.spec_from_file_location('core', Path(__file__).parents[1]/'scan_tools/core.py')
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


def grid(size=12):
    vertices = np.array([(x/size, y/size, 0) for y in range(size+1) for x in range(size+1)], float)
    triangles = []
    for y in range(size):
        for x in range(size):
            a = y*(size+1)+x
            triangles += [(a,a+1,a+size+2), (a,a+size+2,a+size+1)]
    return vertices, np.array(triangles)


class RegionTests(unittest.TestCase):
    def test_noisy_plane_and_area(self):
        vertices, triangles = grid()
        vertices[:,2] = np.random.default_rng(5).normal(0, 0.0001, len(vertices))
        fit = core.planar_region(vertices, triangles, 40, 25, 0.003)
        self.assertGreater(len(fit['faces']), 0.99*len(triangles))
        self.assertLess(fit['rms'], 0.0002)
        self.assertGreater(fit['normal'][2], 0.999)
        self.assertAlmostEqual(fit['area'], 1, places=4)

    def test_sharp_corner_is_not_flooded(self):
        vertices = np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0],[1,0,1],[1,1,1]], float)
        triangles = np.array([[0,1,2],[0,2,3],[1,4,5],[1,5,2]])
        fit = core.planar_region(vertices, triangles, 0, 25, 0.002)
        self.assertEqual(fit['faces'], [0,1])

    def test_disconnected_coplanar_patch_is_not_flooded(self):
        vertices = np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0], [3,0,0],[4,0,0],[4,1,0],[3,1,0]], float)
        triangles = np.array([[0,1,2],[0,2,3],[4,5,6],[4,6,7]])
        fit = core.planar_region(vertices, triangles, 0)
        self.assertEqual(fit['faces'], [0,1])

    def test_continuous_curve_does_not_drift_across_surface(self):
        vertices, triangles = grid(24)
        # Gradually changing normals: an angle-only neighbour flood would take all faces.
        vertices[:,2] = vertices[:,0]**2
        fit = core.planar_region(vertices, triangles, 0, 25, 0.002)
        self.assertLess(len(fit['faces']), len(triangles)*0.3)

    def test_far_origin_tls_is_stable(self):
        vertices, triangles = grid()
        vertices += [1e7, -1e7, 1e7]
        fit = core.triangle_plane(vertices, triangles)
        self.assertLess(fit['rms'], 1e-8)
        self.assertAlmostEqual(fit['area'], 1.0)
        self.assertGreater(fit['normal'][2], 0.9999)

    def test_fit_invariant_under_retessellation(self):
        a, at = grid(2)
        b, bt = grid(17)
        # Same exact inclined plane with vastly different triangulation density.
        for vertices in (a,b):
            vertices[:,2] = vertices[:,0]*0.4 + vertices[:,1]*0.2 + 7
        af, bf = core.triangle_plane(a,at), core.triangle_plane(b,bt)
        np.testing.assert_allclose(af['normal'], bf['normal'], atol=1e-12)
        np.testing.assert_allclose(af['center'], bf['center'], atol=1e-12)
        self.assertAlmostEqual(af['area'], bf['area'])

    def test_symmetry_progress_is_monotonic(self):
        points = np.array([[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]],float)
        events = []
        core.symmetry_fit(points, lambda q: np.min(np.linalg.norm(q[:,None]-points[None],axis=2),axis=1),
                          [np.array([1,0,0]),np.array([0,1,0])], progress=lambda p,label: events.append(p))
        self.assertEqual(events, sorted(events))
        self.assertEqual(events[-1], 1)


if __name__ == '__main__':
    unittest.main()
