"""Predefined ContainerProperties instances for common shipping container sizes."""

from dataclasses import dataclass, field

from simses.thermal.container import ContainerLayer, ContainerProperties

# ---------------------------------------------------------------------------
# Shared wall layers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AluminumLayer(ContainerLayer):
    """Aluminum layer for container walls."""

    thickness: float = 0.001  # m
    conductivity: float = 237.0  # W/mK
    density: float = 2700.0  # kg/m³
    specific_heat: float = 910.0  # J/kgK


@dataclass(frozen=True)
class SteelLayer(ContainerLayer):
    """Steel layer for container walls."""

    thickness: float = 0.0016  # m
    conductivity: float = 14.4  # W/mK
    density: float = 8050.0  # kg/m³
    specific_heat: float = 500.0  # J/kgK


@dataclass(frozen=True)
class RockWoolLayer(ContainerLayer):
    """Rock-wool insulation layer for container walls."""

    thickness: float = 0.050  # m
    conductivity: float = 0.050  # W/mK
    density: float = 100.0  # kg/m³
    specific_heat: float = 840.0  # J/kgK


@dataclass(frozen=True)
class PolyurethaneLayer(ContainerLayer):
    """Polyurethane insulation layer for container walls."""

    thickness: float = 0.015  # m
    conductivity: float = 0.022  # W/mK
    density: float = 35.0  # kg/m³
    specific_heat: float = 1400.0  # J/kgK


# ---------------------------------------------------------------------------
# 40-ft container  (rock-wool insulation)
# ---------------------------------------------------------------------------
@dataclass
class FortyFtContainer(ContainerProperties):
    """40-ft container with rock-wool insulation."""

    length: float = 12.0  # m (internal)
    width: float = 2.3  # m
    height: float = 2.35  # m
    h_inner: float = 30.0  # W/m²K
    h_outer: float = 30.0  # W/m²K
    inner: ContainerLayer = field(default_factory=AluminumLayer)
    mid: ContainerLayer = field(default_factory=RockWoolLayer)
    outer: ContainerLayer = field(default_factory=SteelLayer)


# ---------------------------------------------------------------------------
# 20-ft container  (polyurethane insulation)
# ---------------------------------------------------------------------------
@dataclass
class TwentyFtContainer(ContainerProperties):
    """20-ft container with polyurethane insulation."""

    length: float = 5.9  # m (internal)
    width: float = 2.3  # m
    height: float = 2.35  # m
    h_inner: float = 30.0  # W/m²K
    h_outer: float = 30.0  # W/m²K
    inner: ContainerLayer = field(default_factory=AluminumLayer)
    mid: ContainerLayer = field(default_factory=PolyurethaneLayer)
    outer: ContainerLayer = field(default_factory=SteelLayer)
