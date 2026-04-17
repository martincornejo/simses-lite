# Interpolation API

The `simses.interpolation` module provides two fast scalar interpolation helpers used on the inner-loop hot path of the simulation. They are drop-in replacements for `numpy.interp` (1-D) and `scipy.interpolate.RegularGridInterpolator` (2-D bilinear) that avoid the ~2–80 µs of per-call argument sanitisation those libraries pay for a single scalar query.

Both helpers operate on plain Python lists and use `bisect` for the index search. Models should convert lookup-table arrays to lists **once at construction time** and pass them in on every step.

Out-of-bounds inputs **raise** rather than clip — silent clipping would mask integration overshoot, initialisation bugs, and upstream control errors.

## Functions

::: simses.interpolation.interp1d_scalar

::: simses.interpolation.interp2d_scalar
