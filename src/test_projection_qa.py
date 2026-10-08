"""Analytic geometry and metric tests. Run: python -m unittest src.test_projection_qa."""
import unittest

import numpy as np

from starter.kitti_io import KittiCalib, load_calib
from starter.projection import cam_to_image, velo_to_cam


class ProjectionTests(unittest.TestCase):
    def test_reference_point(self):
        calib = load_calib("data/synthetic/training/calib/000000.txt")
        cam = velo_to_cam(np.array([[10., 0., 0.]]), calib)
        uv, depth, mask = cam_to_image(cam, calib.P2, (375, 1242, 3))
        self.assertAlmostEqual(cam[0, 2], 9.728, delta=0.01)
        np.testing.assert_allclose(uv[0], [614., 175.], atol=1.)
        self.assertTrue(mask[0])
        self.assertEqual(depth[0], cam[0, 2])

    def test_rectification_and_translation(self):
        r = np.array([[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]])
        calib = KittiCalib(np.eye(3, 4), r, np.column_stack((np.eye(3), [1., 2., 3.])))
        np.testing.assert_allclose(velo_to_cam(np.array([[2., 3., 4.]]), calib), [[-5., 3., 7.]])

    def test_invalid_depth_and_image_edges(self):
        p = np.array([[0., 0., 1.], [9., 9., 1.], [10., 1., 1.],
                      [-1., 0., 1.], [0., 10., 1.], [0., 0., -1.],
                      [0., 0., .1], [np.nan, 0., 1.], [0., np.inf, 1.]])
        uv, depth, mask = cam_to_image(p, np.eye(3, 4), (10, 10))
        np.testing.assert_array_equal(mask, [True, True, False, False, False, False, False, False, False])
        np.testing.assert_array_equal(uv, [[0., 0.], [9., 9.]])
        np.testing.assert_array_equal(depth, [1., 1.])

    def test_empty_and_zero_projection_scale(self):
        uv, depth, mask = cam_to_image(np.empty((0, 3)), np.eye(3, 4), (10, 10))
        self.assertEqual(uv.shape, (0, 2))
        self.assertEqual(depth.shape, (0,))
        self.assertEqual(mask.shape, (0,))
        self.assertEqual(velo_to_cam(np.empty((0, 3)), KittiCalib(
            np.eye(3, 4), np.eye(3), np.eye(3, 4))).shape, (0, 3))
        _, _, mask = cam_to_image(np.array([[1., 2., 3.]]), np.zeros((3, 4)), (10, 10))
        self.assertFalse(mask.any())

    def test_full_p2_translation(self):
        p2 = np.array([[10., 0., 0., 2.], [0., 10., 0., 4.], [0., 0., 1., 1.]])
        uv, depth, _ = cam_to_image(np.array([[1., 2., 3.]]), p2, (20, 20))
        np.testing.assert_allclose(uv, [[3., 6.]])
        np.testing.assert_allclose(depth, [3.])


if __name__ == "__main__":
    unittest.main()
