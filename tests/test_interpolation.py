"""Unit tests for the fast scalar interpolation helpers."""

import numpy as np
import pytest
from scipy.interpolate import RegularGridInterpolator

from simses.interpolation import interp1d_scalar, interp2d_scalar


class TestInterp1dScalar:
    def test_interior_point(self):
        xp = [0.0, 1.0, 2.0, 3.0]
        fp = [0.0, 10.0, 20.0, 30.0]
        assert interp1d_scalar(1.5, xp, fp) == pytest.approx(15.0)

    def test_exact_grid_nodes(self):
        xp = [0.0, 1.0, 2.0, 3.0]
        fp = [5.0, 10.0, 20.0, 35.0]
        for x, f in zip(xp, fp, strict=True):
            assert interp1d_scalar(x, xp, fp) == pytest.approx(f)

    def test_left_boundary(self):
        xp = [0.0, 1.0, 2.0]
        fp = [7.0, 8.0, 9.0]
        assert interp1d_scalar(0.0, xp, fp) == pytest.approx(7.0)

    def test_right_boundary(self):
        xp = [0.0, 1.0, 2.0]
        fp = [7.0, 8.0, 9.0]
        assert interp1d_scalar(2.0, xp, fp) == pytest.approx(9.0)

    def test_non_uniform_axis(self):
        xp = [0.0, 0.1, 1.0, 10.0]
        fp = [0.0, 1.0, 5.0, 50.0]
        # Between 1.0 and 10.0: x=5.5 -> (5.5-1.0)/(10-1)*(50-5)+5 = 0.5*45+5 = 27.5
        assert interp1d_scalar(5.5, xp, fp) == pytest.approx(27.5)

    def test_negative_values(self):
        xp = [-3.0, -1.0, 0.0, 2.0]
        fp = [-6.0, -2.0, 0.0, 4.0]
        # Linear y=2x
        assert interp1d_scalar(-2.0, xp, fp) == pytest.approx(-4.0)
        assert interp1d_scalar(1.0, xp, fp) == pytest.approx(2.0)

    def test_out_of_bounds_below_raises(self):
        xp = [0.0, 1.0, 2.0]
        fp = [0.0, 1.0, 2.0]
        with pytest.raises(ValueError, match="out of bounds"):
            interp1d_scalar(-0.001, xp, fp)

    def test_out_of_bounds_above_raises(self):
        xp = [0.0, 1.0, 2.0]
        fp = [0.0, 1.0, 2.0]
        with pytest.raises(ValueError, match="out of bounds"):
            interp1d_scalar(2.001, xp, fp)

    def test_matches_numpy_interp(self):
        """Result should agree with numpy.interp at interior points."""
        xp = [0.0, 0.5, 1.2, 2.7, 4.0, 5.5]
        fp = [1.0, 3.0, 2.0, 5.0, 4.5, 6.0]
        queries = [0.1, 0.5, 0.8, 1.2, 2.0, 3.3, 4.0, 5.0, 5.5]
        for x in queries:
            expected = float(np.interp(x, xp, fp))
            assert interp1d_scalar(x, xp, fp) == pytest.approx(expected)


class TestInterp2dScalar:
    def test_interior_point(self):
        xp = [0.0, 1.0, 2.0]
        yp = [0.0, 1.0]
        # f(x, y) = x + 10*y
        mat = [
            [0.0, 10.0],
            [1.0, 11.0],
            [2.0, 12.0],
        ]
        assert interp2d_scalar(0.5, 0.5, xp, yp, mat) == pytest.approx(5.5)
        assert interp2d_scalar(1.5, 0.25, xp, yp, mat) == pytest.approx(1.5 + 2.5)

    def test_exact_grid_nodes(self):
        xp = [0.0, 1.0, 2.0]
        yp = [10.0, 20.0]
        mat = [
            [1.0, 2.0],
            [3.0, 4.0],
            [5.0, 6.0],
        ]
        for i, x in enumerate(xp):
            for j, y in enumerate(yp):
                assert interp2d_scalar(x, y, xp, yp, mat) == pytest.approx(mat[i][j])

    def test_upper_right_corner(self):
        xp = [0.0, 1.0, 2.0]
        yp = [0.0, 1.0, 2.0]
        mat = [
            [0.0, 1.0, 2.0],
            [1.0, 2.0, 3.0],
            [2.0, 3.0, 4.0],
        ]
        assert interp2d_scalar(2.0, 2.0, xp, yp, mat) == pytest.approx(4.0)

    def test_edge_along_x_axis(self):
        xp = [0.0, 1.0, 2.0]
        yp = [0.0, 1.0]
        mat = [
            [0.0, 10.0],
            [1.0, 11.0],
            [2.0, 12.0],
        ]
        # y on bottom edge, interpolated in x
        assert interp2d_scalar(1.5, 0.0, xp, yp, mat) == pytest.approx(1.5)
        # y on top edge
        assert interp2d_scalar(1.5, 1.0, xp, yp, mat) == pytest.approx(11.5)

    def test_edge_along_y_axis(self):
        xp = [0.0, 1.0, 2.0]
        yp = [0.0, 1.0, 2.0]
        mat = [
            [0.0, 1.0, 2.0],
            [1.0, 2.0, 3.0],
            [2.0, 3.0, 4.0],
        ]
        # x on left edge, interpolate in y
        assert interp2d_scalar(0.0, 1.5, xp, yp, mat) == pytest.approx(1.5)
        # x on right edge
        assert interp2d_scalar(2.0, 0.5, xp, yp, mat) == pytest.approx(2.5)

    def test_non_uniform_axes(self):
        xp = [0.0, 0.5, 3.0]
        yp = [-2.0, 0.0, 5.0]
        # Bilinear function g(x, y) = 2x + 3y + 1 is exactly representable.
        mat = [[2 * x + 3 * y + 1 for y in yp] for x in xp]
        queries = [(0.25, -1.0), (1.0, 2.0), (2.5, 4.0), (0.5, 0.0)]
        for x, y in queries:
            expected = 2 * x + 3 * y + 1
            assert interp2d_scalar(x, y, xp, yp, mat) == pytest.approx(expected)

    def test_out_of_bounds_x_raises(self):
        xp = [0.0, 1.0]
        yp = [0.0, 1.0]
        mat = [[0.0, 1.0], [1.0, 2.0]]
        with pytest.raises(ValueError, match="x=.*out of bounds"):
            interp2d_scalar(-0.1, 0.5, xp, yp, mat)
        with pytest.raises(ValueError, match="x=.*out of bounds"):
            interp2d_scalar(1.1, 0.5, xp, yp, mat)

    def test_out_of_bounds_y_raises(self):
        xp = [0.0, 1.0]
        yp = [0.0, 1.0]
        mat = [[0.0, 1.0], [1.0, 2.0]]
        with pytest.raises(ValueError, match="y=.*out of bounds"):
            interp2d_scalar(0.5, -0.1, xp, yp, mat)
        with pytest.raises(ValueError, match="y=.*out of bounds"):
            interp2d_scalar(0.5, 1.1, xp, yp, mat)

    def test_matches_regular_grid_interpolator(self):
        """Result should match scipy's RegularGridInterpolator within machine eps."""
        rng = np.random.default_rng(seed=42)
        xp = [0.0, 0.1, 0.4, 1.0, 2.5, 5.0]
        yp = [-10.0, -3.0, 0.0, 2.0, 8.0]
        mat_np = rng.standard_normal((len(xp), len(yp)))
        mat = mat_np.tolist()

        rgi = RegularGridInterpolator((xp, yp), mat_np, method="linear")

        queries = [
            (0.0, -10.0),  # corner
            (5.0, 8.0),  # opposite corner
            (0.05, -5.0),  # interior
            (0.7, 0.0),  # on y-axis node
            (1.0, 4.0),  # on x-axis node
            (2.0, -1.0),
            (4.9, 7.99),
            (0.1, -10.0),  # edge
        ]
        for x, y in queries:
            expected = float(rgi((x, y)))
            actual = interp2d_scalar(x, y, xp, yp, mat)
            assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)
