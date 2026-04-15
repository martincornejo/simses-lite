"""Predefined ContainerProperties instances for common shipping container sizes."""

from simses.thermal.container import ContainerLayer, ContainerProperties

# ---------------------------------------------------------------------------
# Shared wall layers
# ---------------------------------------------------------------------------
_INNER_AL = ContainerLayer(
    thickness=0.001,  # m
    conductivity=237.0,  # W/mK
    density=2700.0,  # kg/m³
    specific_heat=910.0,  # J/kgK
)

_OUTER_STEEL = ContainerLayer(
    thickness=0.0016,  # m
    conductivity=14.4,  # W/mK
    density=8050.0,  # kg/m³
    specific_heat=500.0,  # J/kgK
)

# ---------------------------------------------------------------------------
# 40-ft container  (rock-wool insulation)
# ---------------------------------------------------------------------------
FortyFtContainer = ContainerProperties(
    length=12.0,  # m (internal)
    width=2.3,  # m
    height=2.35,  # m
    h_inner=30.0,  # W/m²K
    h_outer=30.0,  # W/m²K
    inner=_INNER_AL,
    mid=ContainerLayer(
        thickness=0.050,  # m
        conductivity=0.050,  # W/mK
        density=100.0,  # kg/m³
        specific_heat=840.0,  # J/kgK
    ),
    outer=_OUTER_STEEL,
)

# ---------------------------------------------------------------------------
# 20-ft container  (polyurethane insulation)
# ---------------------------------------------------------------------------
TwentyFtContainer = ContainerProperties(
    length=5.9,  # m (internal)
    width=2.3,  # m
    height=2.35,  # m
    h_inner=30.0,  # W/m²K
    h_outer=30.0,  # W/m²K
    inner=_INNER_AL,
    mid=ContainerLayer(
        thickness=0.015,  # m
        conductivity=0.022,  # W/mK
        density=35.0,  # kg/m³
        specific_heat=1400.0,  # J/kgK
    ),
    outer=_OUTER_STEEL,
)
