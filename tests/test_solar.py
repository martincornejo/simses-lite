"""Tests for solar_heat_load and SolarConfig."""

import pandas as pd
import pytest

from simses.thermal.container import ContainerLayer, ContainerProperties
from simses.thermal.solar import SolarConfig, solar_heat_load

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _simple_container() -> ContainerProperties:
    """20ft container with minimal wall layers (geometry is what matters here)."""
    layer = ContainerLayer(thickness=0.001, conductivity=50.0, density=7800.0, specific_heat=500.0)
    return ContainerProperties(
        length=6.06,
        width=2.44,
        height=2.59,
        h_inner=5.0,
        h_outer=15.0,
        inner=layer,
        mid=layer,
        outer=layer,
    )


def _munich_config(azimuth: float = 0.0) -> SolarConfig:
    return SolarConfig(latitude=48.14, longitude=11.58, azimuth=azimuth)


def _ghi_series(timestamps: list[str], values: list[float], tz: str = "Europe/Berlin") -> pd.Series:
    idx = pd.DatetimeIndex(timestamps, tz=tz)
    return pd.Series(values, index=idx)


# ---------------------------------------------------------------------------
# Basic correctness
# ---------------------------------------------------------------------------


class TestNightAndZeroGhi:
    def test_midnight_returns_zero(self):
        ghi = _ghi_series(["2024-06-21 00:00:00"], [0.0])
        q = solar_heat_load(ghi, _simple_container(), _munich_config())
        assert q.iloc[0] == pytest.approx(0.0)

    def test_ghi_zero_at_midday_returns_zero(self):
        # GHI = 0 (overcast/no data) even though sun is above horizon
        ghi = _ghi_series(["2024-06-21 12:00:00"], [0.0])
        q = solar_heat_load(ghi, _simple_container(), _munich_config())
        assert q.iloc[0] == pytest.approx(0.0)

    def test_always_nonnegative(self):
        timestamps = [f"2024-06-21 {h:02d}:00:00" for h in range(24)]
        values = [max(0.0, 800.0 * (1 - abs(h - 12) / 6)) for h in range(24)]
        ghi = _ghi_series(timestamps, values)
        q = solar_heat_load(ghi, _simple_container(), _munich_config())
        assert (q.values >= 0.0).all()


class TestDaytimeProducesPositivePower:
    def test_clear_summer_midday_munich(self):
        # Sunny summer noon in Munich: GHI ≈ 900 W/m², expect significant heat load
        ghi = _ghi_series(["2024-06-21 13:00:00"], [900.0])
        q = solar_heat_load(ghi, _simple_container(), _munich_config())
        assert q.iloc[0] > 500.0, f"Expected > 500 W, got {q.iloc[0]:.1f} W"

    def test_monotone_with_ghi(self):
        # Higher GHI must produce higher Q_solar (monotone, even if not linear)
        ts = ["2024-06-21 13:00:00"]
        q1 = solar_heat_load(_ghi_series(ts, [200.0]), _simple_container(), _munich_config())
        q2 = solar_heat_load(_ghi_series(ts, [600.0]), _simple_container(), _munich_config())
        q3 = solar_heat_load(_ghi_series(ts, [900.0]), _simple_container(), _munich_config())
        assert q1.iloc[0] < q2.iloc[0] < q3.iloc[0]


# ---------------------------------------------------------------------------
# Index / timezone handling
# ---------------------------------------------------------------------------


class TestIndexHandling:
    def test_output_index_matches_input(self):
        timestamps = [f"2024-07-15 {h:02d}:00:00" for h in range(24)]
        values = [max(0.0, 600.0 * (1 - abs(h - 12) / 7)) for h in range(24)]
        ghi = _ghi_series(timestamps, values)
        q = solar_heat_load(ghi, _simple_container(), _munich_config())
        assert list(q.index) == list(ghi.index)
        assert len(q) == 24

    def test_raises_on_naive_index(self):
        idx = pd.DatetimeIndex(["2024-06-21 12:00:00"])  # no timezone
        ghi = pd.Series([900.0], index=idx)
        with pytest.raises(TypeError, match="timezone-aware"):
            solar_heat_load(ghi, _simple_container(), _munich_config())

    def test_raises_on_dataframe(self):
        idx = pd.DatetimeIndex(["2024-06-21 12:00:00"], tz="Europe/Berlin")
        df = pd.DataFrame({"ghi": [900.0]}, index=idx)
        with pytest.raises(TypeError, match="pd.Series"):
            solar_heat_load(df, _simple_container(), _munich_config())

    def test_negative_ghi_clamped_to_zero(self):
        ghi = _ghi_series(["2024-06-21 12:00:00"], [-100.0])
        q = solar_heat_load(ghi, _simple_container(), _munich_config())
        assert q.iloc[0] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Geometry and orientation
# ---------------------------------------------------------------------------


class TestKtGreaterThanOne:
    def test_direct_is_zero_when_ghi_exceeds_extraterrestrial(self):
        # GHI = 2000 W/m² far exceeds ETR_h at Munich midday (~1200 W/m²), so kt > 1.
        # This is a data artefact (physically impossible).  Legacy behaviour: diffuse = 0
        # AND direct = 0.  Without the fix, direct_h = ghi - 0 = 2000, causing a DNI spike.
        container = _simple_container()
        config = _munich_config()
        ghi_val = 2000.0
        ghi = _ghi_series(["2024-06-21 13:00:00"], [ghi_val])
        q = solar_heat_load(ghi, container, config)

        # With kt > 1: diffuse = 0, direct = 0.  Only ground-reflected contributes to
        # vertical faces; roof gets nothing (direct_h + diffuse = 0).
        reflected = ghi_val * config.albedo * 0.5
        total_vert_area = 2 * (container.length + container.width) * container.height
        q_expected = config.absorptivity * total_vert_area * reflected
        assert q.iloc[0] == pytest.approx(q_expected)


class TestContainerOrientation:
    def test_absorptivity_zero_gives_zero(self):
        config = SolarConfig(latitude=48.14, longitude=11.58, azimuth=0.0, absorptivity=0.0)
        ghi = _ghi_series(["2024-06-21 13:00:00"], [900.0])
        q = solar_heat_load(ghi, _simple_container(), config)
        assert q.iloc[0] == pytest.approx(0.0)

    def test_larger_container_gives_more_power(self):
        layer = ContainerLayer(0.001, 50.0, 7800.0, 500.0)
        small = ContainerProperties(3.0, 2.0, 2.0, 5.0, 15.0, layer, layer, layer)
        large = ContainerProperties(6.0, 2.0, 2.0, 5.0, 15.0, layer, layer, layer)
        ts = ["2024-06-21 13:00:00"]
        ghi = _ghi_series(ts, [900.0])
        q_small = solar_heat_load(ghi, small, _munich_config())
        q_large = solar_heat_load(ghi, large, _munich_config())
        assert q_large.iloc[0] > q_small.iloc[0]

    def test_rotation_changes_distribution_not_total_magnitude(self):
        # Rotating by 180° gives the same total (symmetric N/S faces, symmetric E/W faces)
        ts = ["2024-06-21 13:00:00"]
        ghi = _ghi_series(ts, [900.0])
        q0 = solar_heat_load(ghi, _simple_container(), _munich_config(azimuth=0.0))
        q180 = solar_heat_load(ghi, _simple_container(), _munich_config(azimuth=180.0))
        # Total is the same because N↔S swap and E↔W swap preserve total area/orientation
        assert q0.iloc[0] == pytest.approx(q180.iloc[0], rel=1e-9)
