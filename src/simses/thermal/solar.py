"""Pre-computation of solar heat load on a containerised BESS installation.

Converts a global horizontal irradiance (GHI) time series into absorbed
thermal power [W] using:

1. Astronomical solar position (Spencer / Fourier series, no external library).
2. Reindl clearness-index decomposition of GHI into direct and diffuse.
3. Per-face angle-of-incidence calculation for the five exposed container
   surfaces (North, South, East, West, Roof).

All computation is vectorised over the full time series so that the result
can be pre-computed once and fed step-by-step into
:attr:`~simses.thermal.ContainerThermalModel.Q_solar`.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from simses.thermal.container import ContainerProperties


@dataclass(frozen=True)
class SolarConfig:
    """Solar and surface parameters for solar heat-load pre-computation.

    Attributes:
        latitude:     Site latitude in degrees N (negative = Southern hemisphere).
        longitude:    Site longitude in degrees E (negative = West).
        azimuth:      Container orientation — compass bearing that the **North
                      face** of the container points toward, in degrees clockwise
                      from true North.  0 = North face points North (standard
                      alignment), 90 = rotated 90° clockwise (North face now
                      points East).
        absorptivity: Outer surface absorptivity coefficient (0–1).  Typical
                      painted steel ≈ 0.6.  Default: 0.6.
        albedo:       Ground reflectance (0–1).  Default: 0.2.
    """

    latitude: float
    longitude: float
    azimuth: float
    absorptivity: float = 0.6
    albedo: float = 0.2


def solar_heat_load(
    ghi: pd.Series,
    container: ContainerProperties,
    config: SolarConfig,
) -> pd.Series:
    """Pre-compute absorbed solar heat load on a container for a full timeseries.

    The calculation is vectorised: a single call processes an entire year (or
    any length) of GHI data at once.  The returned series can be indexed during
    the simulation loop and assigned to
    :attr:`~simses.thermal.ContainerThermalModel.Q_solar`.

    Args:
        ghi:       Global horizontal irradiance [W/m²].  Must carry a
                   timezone-aware :class:`pandas.DatetimeIndex`.  Negative
                   values are clamped to zero.
        container: Container geometry — ``length``, ``width``, and ``height``
                   (internal dimensions) are used to derive face areas.
        config:    Site location, container orientation, and surface properties.

    Returns:
        Absorbed solar power [W] with the same index as *ghi*.  All values are
        ≥ 0; night-time and below-horizon rows are zero.

    Raises:
        TypeError: If *ghi* is not a :class:`pandas.Series` or does not have a
            timezone-aware DatetimeIndex.

    Example::

        import pandas as pd
        from simses.thermal import ContainerLayer, ContainerProperties
        from simses.thermal.solar import SolarConfig, solar_heat_load

        df = pd.read_csv("munich_ghi_2024.csv", index_col=0, parse_dates=True)
        df.index = df.index.tz_localize("Europe/Berlin")
        ghi = df["ghi_wm2"]  # select one column → pd.Series

        props = ContainerProperties(
            length=6.06, width=2.44, height=2.59,
            h_inner=5.0, h_outer=15.0,
            inner=ContainerLayer(0.001, 200, 2700, 900),
            mid=ContainerLayer(0.06, 0.04, 30, 1000),
            outer=ContainerLayer(0.002, 50, 7800, 500),
        )
        config = SolarConfig(latitude=48.14, longitude=11.58, azimuth=0.0)
        q_solar = solar_heat_load(ghi.squeeze(), props, config)
    """
    if not isinstance(ghi, pd.Series):
        raise TypeError(f"ghi must be a pd.Series, got {type(ghi).__name__}")
    if not hasattr(ghi.index, "tz") or ghi.index.tz is None:
        raise TypeError("ghi must have a timezone-aware DatetimeIndex")

    ghi_vals = np.maximum(0.0, ghi.to_numpy(dtype=float))
    idx = ghi.index

    lat_rad = np.deg2rad(config.latitude)
    lon = config.longitude

    # --- Orbital parameters (vectorised over the full index) ---
    doy = idx.day_of_year.to_numpy(dtype=float)
    year = idx.year.to_numpy()
    is_leap = ((year % 4 == 0) & (year % 100 != 0)) | (year % 400 == 0)
    days_in_year = np.where(is_leap, 366.0, 365.0)

    oi = 360.0 * doy / days_in_year  # orbital inclination, degrees

    # Equation of time (seconds) — Spencer (1971) Fourier approximation
    eot = 60.0 * (
        0.0066
        + 7.3525 * np.cos(np.deg2rad(oi + 85.9))
        + 9.9359 * np.cos(np.deg2rad(2.0 * oi + 108.9))
        + 0.3387 * np.cos(np.deg2rad(3.0 * oi + 105.2))
    )

    # Solar declination (degrees)
    delta_rad = np.deg2rad(
        0.3948
        - 23.2559 * np.cos(np.deg2rad(oi + 9.1))
        - 0.3915 * np.cos(np.deg2rad(2.0 * oi + 5.4))
        - 0.1764 * np.cos(np.deg2rad(3.0 * oi + 26.0))
    )

    # --- Apparent solar time → hour angle ---
    # float seconds since Unix epoch — portable across pandas datetime64 resolutions
    _epoch = pd.Timestamp("1970-01-01", tz="UTC")
    unix_s = (idx.tz_convert("UTC") - _epoch).total_seconds().to_numpy(dtype=float)
    # Apparent solar time (s): UTC + longitude offset + equation of time
    solar_sec = (unix_s + lon * 240.0 + eot) % 86400.0
    # Hour angle: positive before noon (sun east of meridian)
    h_deg = (43200.0 - solar_sec) * 15.0 / 3600.0
    h_rad = np.deg2rad(h_deg)

    # --- Sun elevation ---
    sin_alpha = np.clip(
        np.cos(h_rad) * np.cos(lat_rad) * np.cos(delta_rad) + np.sin(lat_rad) * np.sin(delta_rad),
        -1.0,
        1.0,
    )
    cos_alpha = np.sqrt(np.maximum(0.0, 1.0 - sin_alpha**2))
    above = sin_alpha > 0.0  # sun above horizon

    # --- Solar azimuth (degrees, from North clockwise) ---
    # q1 = arccos((sin_alpha * sin_lat − sin_delta) / (cos_alpha * cos_lat))
    with np.errstate(divide="ignore", invalid="ignore"):
        acos_arg = np.where(
            cos_alpha > 1e-9,
            np.clip(
                (sin_alpha * np.sin(lat_rad) - np.sin(delta_rad)) / (cos_alpha * np.cos(lat_rad)),
                -1.0,
                1.0,
            ),
            0.0,
        )
    q1 = np.rad2deg(np.arccos(acos_arg))
    # Before noon h_deg > 0: sun east of meridian → azimuth < 180°
    # After noon h_deg ≤ 0: sun west of meridian → azimuth > 180°
    azimuth_sun = np.where(h_deg > 0.0, 180.0 - q1, 180.0 + q1)

    # --- GHI decomposition (Reindl clearness-index model) ---
    etr = (1.0 + 0.03344 * np.cos(np.deg2rad(doy * 0.9856 - 2.72))) * 1367.0
    etr_h = np.where(above, etr * sin_alpha, 1.0)  # avoid /0 outside daylight

    with np.errstate(divide="ignore", invalid="ignore"):
        kt = np.where(above, ghi_vals / etr_h, 0.0)

    sin_a = np.where(above, sin_alpha, 0.0)
    diffuse = np.where(
        ~above | (kt <= 0.0),
        0.0,
        np.where(
            kt <= 0.3,
            ghi_vals * (1.020 - 0.254 * kt + 0.0123 * sin_a),
            np.where(
                kt < 0.78,
                ghi_vals * (1.400 - 1.749 * kt + 0.177 * sin_a),
                np.where(kt < 1.0, ghi_vals * (0.486 - 0.182 * sin_a), 0.0),
            ),
        ),
    )
    diffuse = np.clip(diffuse, 0.0, None)
    # When kt > 1 (GHI exceeds extraterrestrial — physically impossible, data artefact),
    # the legacy code sets direct = 0 as well (mirroring get_direct_radiation_horizontal).
    direct_h = np.where(above & (diffuse > 0.0), np.maximum(0.0, ghi_vals - diffuse), 0.0)

    # DNI = direct_horizontal / sin(elevation)
    with np.errstate(divide="ignore", invalid="ignore"):
        dni = np.where(above & (sin_alpha > 1e-4), direct_h / sin_alpha, 0.0)

    # --- Per-face irradiance ---
    # Ground-reflected component on vertical surfaces (isotropic albedo)
    reflected = np.where(above, ghi_vals * config.albedo * 0.5, 0.0)
    # Isotropic sky diffuse on vertical surfaces (half-sky view factor = 0.5)
    diffuse_vert = np.where(above, diffuse * 0.5, 0.0)

    # Face areas from container geometry
    a_ns = container.length * container.height  # North and South faces
    a_ew = container.width * container.height  # East and West faces
    a_roof = container.length * container.width

    # Outward-normal azimuths of each face (degrees from North, clockwise)
    az_n = config.azimuth
    az_s = config.azimuth + 180.0
    az_e = config.azimuth + 90.0
    az_w = config.azimuth + 270.0

    def _face_power(area: float, face_az: float) -> np.ndarray:
        """Absorbed power [W] on one vertical face."""
        # cos of angle of incidence = cos(elevation) * cos(sun_az - face_normal_az)
        cos_aoi = np.where(
            above,
            cos_alpha * np.cos(np.deg2rad(azimuth_sun - face_az)),
            0.0,
        )
        direct = np.where(cos_aoi > 0.0, dni * cos_aoi, 0.0)
        return area * (direct + diffuse_vert + reflected)

    q_faces = _face_power(a_ns, az_n) + _face_power(a_ns, az_s) + _face_power(a_ew, az_e) + _face_power(a_ew, az_w)

    # Roof: full sky diffuse + direct horizontal (no reflected — faces upward)
    q_roof = np.where(above, a_roof * (direct_h + diffuse), 0.0)

    q_solar = config.absorptivity * (q_faces + q_roof)
    return pd.Series(np.maximum(0.0, q_solar), index=idx, name="Q_solar_W")
