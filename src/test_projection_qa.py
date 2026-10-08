"""Analytic geometry and metric tests. Run: python -m unittest src.test_projection_qa."""
import unittest

import numpy as np

from starter.kitti_io import KittiCalib, KittiObject, load_calib
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


class MetricTests(unittest.TestCase):
    def test_rotated_box_bottom_center(self):
        from src.projection_qa import points_in_box
        obj = KittiObject("Car", 0., 0, 0., np.array([0., 0., 10., 10.]),
                          np.array([2., 2., 4.]), np.array([10., 5., 20.]), np.pi / 2)
        p = np.array([[10., 4., 21.9], [10., 4., 22.1], [10.9, 3., 20.],
                      [11.1, 4., 20.], [10., 5.1, 20.], [10., 2.9, 20.],
                      [np.nan, 4., 20.]])
        np.testing.assert_array_equal(points_in_box(p, obj), [True, False, True, False, False, False, False])

    def test_fixed_denominator_and_undefined(self):
        from src.projection_qa import alignment_metrics
        self.assertEqual(alignment_metrics(10, 9, 7), (90., 70., 20., True))
        # Losing projected points does not reduce the baseline denominator.
        self.assertEqual(alignment_metrics(10, 9, 0), (90., 0., 90., True))
        self.assertEqual(alignment_metrics(10, 9, 8), (90., 80., 10., True))
        self.assertTrue(all(np.isnan(v) for v in alignment_metrics(0, 0, 0)))

    def test_lateral_axes_and_zero_drift(self):
        from src.projection_qa import drift_calib
        c = KittiCalib(np.eye(3, 4), np.eye(3), np.eye(3, 4))
        np.testing.assert_allclose(drift_calib(c, "translation", 5., "kitti").Tr_velo_to_cam[:, 3], [0., .05, 0.])
        np.testing.assert_allclose(drift_calib(c, "translation", 5., "nuscenes").Tr_velo_to_cam[:, 3], [.05, 0., 0.])
        np.testing.assert_allclose(drift_calib(c, "yaw", 0., "kitti").T_cam_velo, c.T_cam_velo)
        np.testing.assert_allclose(c.Tr_velo_to_cam, np.eye(3, 4))

    def test_range_boundaries_and_fixed_pixel_indices(self):
        from src.projection_qa import expanded_projection, range_bucket
        self.assertEqual([range_bucket(v) for v in (9.9, 10., 30., 30.1)],
                         ["near_lt10m", "mid_10to30m", "mid_10to30m", "far_gt30m"])
        c = KittiCalib(np.eye(3, 4), np.eye(3), np.eye(3, 4))
        uv, depth, mask = expanded_projection(np.array([[1., 2., 1.], [-1., 0., 1.], [3., 4., 1.]]), c, (10, 10))
        np.testing.assert_array_equal(mask, [True, False, True])
        np.testing.assert_allclose(uv[[0, 2]], [[1., 2.], [3., 4.]])
        self.assertTrue(np.isnan(uv[1]).all())
        self.assertTrue(np.isnan(depth[1]))


if __name__ == "__main__":
    unittest.main()
