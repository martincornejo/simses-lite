"""Fast scalar linear-interpolation helpers used across simses models.

These functions are scalar-input replacements for ``numpy.interp`` (1-D) and
``scipy.interpolate.RegularGridInterpolator`` (2-D bilinear). They are used
on the inner-loop hot path of the simulation, where the per-call overhead of
the numpy/scipy implementations dominates the actual interpolation math:

* ``np.interp`` on a scalar pays for argument-array conversion and broadcasting
  on every call (~2 us each).
* ``RegularGridInterpolator.__call__`` runs ~80 us of input sanitisation per
  scalar call before doing any work.

The helpers below operate on plain Python lists and use ``bisect`` for the
index search, which is the fastest scalar path on CPython. Models should
convert their lookup-table arrays to lists once at construction time and pass
those lists in on every call.

Both helpers **raise on out-of-bounds inputs** rather than clipping. Silent
clipping in physical models is dangerous: it masks integration overshoot,
state initialisation errors, and bugs in upstream control code. Surfacing
the violation as a ``ValueError`` makes those bugs immediately diagnosable.
"""

import bisect


def interp1d_scalar(x: float, xp: list[float], fp: list[float]) -> float:
    """Linear interpolation of a scalar against a sorted axis.

    Args:
        x:  Query value.
        xp: Strictly ascending axis (Python list).
        fp: Function values at ``xp`` (Python list, same length).

    Returns:
        ``f(x)`` by linear interpolation.

    Raises:
        ValueError: If ``x`` lies outside ``[xp[0], xp[-1]]``.
    """
    if x < xp[0] or x > xp[-1]:
        raise ValueError(f"x={x} out of bounds [{xp[0]}, {xp[-1]}]")
    if x == xp[-1]:
        return fp[-1]
    i = bisect.bisect_right(xp, x) - 1
    x0 = xp[i]
    return fp[i] + (fp[i + 1] - fp[i]) * (x - x0) / (xp[i + 1] - x0)


def interp2d_scalar(
    x: float,
    y: float,
    xp: list[float],
    yp: list[float],
    mat: list[list[float]],
) -> float:
    """Bilinear interpolation of a scalar (x, y) against a 2-D LUT.

    ``mat`` is indexed as ``mat[i][j]`` with ``xp[i]`` and ``yp[j]`` as the
    grid coordinates. Both axes must be strictly ascending. The result is
    bit-for-bit equivalent to ``RegularGridInterpolator((xp, yp), mat)((x, y))``
    at every grid node and at all interior points (machine epsilon).

    Args:
        x:   Query value along the first axis.
        y:   Query value along the second axis.
        xp:  Strictly ascending first-axis values.
        yp:  Strictly ascending second-axis values.
        mat: 2-D table; ``mat[i][j]`` is the value at ``(xp[i], yp[j])``.

    Returns:
        ``f(x, y)`` by bilinear interpolation.

    Raises:
        ValueError: If ``x`` or ``y`` lies outside its respective LUT range.
    """
    if x < xp[0] or x > xp[-1]:
        raise ValueError(f"x={x} out of bounds [{xp[0]}, {xp[-1]}]")
    if y < yp[0] or y > yp[-1]:
        raise ValueError(f"y={y} out of bounds [{yp[0]}, {yp[-1]}]")

    if x == xp[-1]:
        i = len(xp) - 2
        u = 1.0
    else:
        i = bisect.bisect_right(xp, x) - 1
        x0 = xp[i]
        u = (x - x0) / (xp[i + 1] - x0)

    if y == yp[-1]:
        j = len(yp) - 2
        v = 1.0
    else:
        j = bisect.bisect_right(yp, y) - 1
        y0 = yp[j]
        v = (y - y0) / (yp[j + 1] - y0)

    row_i = mat[i]
    row_i1 = mat[i + 1]
    f00 = row_i[j]
    f01 = row_i[j + 1]
    f10 = row_i1[j]
    f11 = row_i1[j + 1]

    one_minus_u = 1.0 - u
    one_minus_v = 1.0 - v
    return (
        one_minus_u * one_minus_v * f00
        + u * one_minus_v * f10
        + one_minus_u * v * f01
        + u * v * f11
    )
