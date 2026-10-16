import importlib.util
from pathlib import Path
import unittest
import numpy as np
from scipy.spatial import cKDTree

spec = importlib.util.spec_from_file_location('core', Path(__file__).parents[1]/'scan_tools/core.py')
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


class GeometryTests(unittest.TestCase):
    def test_sampling_is_area_weighted(self):
        vertices = np.array([[0,0,0], [1,0,0], [0,1,0], [10,0,0], [12,0,0], [10,2,0]], float)
        points = core.sample_surface(vertices, np.array([[0,1,2],[3,4,5]]), 20000)
        self.assertAlmostEqual(float((points[:,0] > 5).mean()), 0.8, delta=0.02)

    def test_noisy_plane_with_outliers(self):
        rng = np.random.default_rng(9)
        xy = rng.uniform(-1, 1, (900, 2))
        plane = np.column_stack((xy, rng.normal(0, 0.001, 900)))
        points = np.vstack((plane, rng.uniform(-1, 1, (100, 3))))
        n, _, support, rms = core.fit_plane(points, 0.002)
        self.assertGreater(abs(n[2]), 0.999)
        self.assertGreater(support, 0.88)
        self.assertLess(rms, 0.002)

    def test_symmetry_with_asymmetric_outliers(self):
        rng = np.random.default_rng(8)
        half = rng.uniform([0.2,-2,-0.6], [1,2,0.6], (700,3))
        symmetric = np.vstack((half, half*np.array([-1,1,1])))
        angle = 0.31
        rot = np.array([[np.cos(angle), -np.sin(angle), 0], [np.sin(angle), np.cos(angle), 0], [0,0,1]])
        shift = np.array([4, 2, -1])
        world = symmetric @ rot.T + shift
        outliers = rng.uniform([4,5,2], [5,6,3], (100,3))
        points = np.vstack((world, outliers))
        tree = cKDTree(points)
        n, d, scores = core.symmetry_fit(points, lambda q: tree.query(q)[0], [rot[:,0]], 0.8)
        self.assertGreater(abs(n @ rot[:,0]), 0.999)
        self.assertLess(abs(d - n @ shift), 0.02)
        self.assertLess(scores['trimmed_rms_relative'], 0.003)

    def test_orientation_preserves_handedness_and_symmetry(self):
        rng = np.random.default_rng(3)
        points = rng.normal(size=(300,3)) + [3,4,5]
        n = core.unit([1, 2, 0.2])
        d = 4.3
        matrix = core.orientation(points, np.array([0,0,1]), (n,d))
        rot = matrix[:3,:3]
        np.testing.assert_allclose(rot @ rot.T, np.eye(3), atol=1e-12)
        self.assertAlmostEqual(np.linalg.det(rot), 1.0)
        self.assertAlmostEqual((rot @ (n*d)+matrix[:3,3])[0], 0, places=10)
        np.testing.assert_allclose(rot @ n, [1,0,0], atol=1e-12)

    def test_degenerate_surface_rejected(self):
        with self.assertRaises(ValueError):
            core.sample_surface(np.zeros((3,3)), np.array([[0,1,2]]))


if __name__ == '__main__':
    unittest.main()
