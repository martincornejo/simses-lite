import numpy as np

from simses.interpolation import interp1d_scalar


class Sungrow:
    """Sungrow SC1000TL converter loss model.

    Manufacturer-specific fit with asymmetric charge and discharge
    coefficients, backed by field data from a frequency containment
    reserve storage system. Three fit families are available via the
    ``fit`` argument:

    * ``"notton"`` (default) — ``η(p) = p / (p + P0 + K·p²)``. Minimum
      efficiency floor of 0.2092 applied to the discharge branch.
    * ``"rampinelli"`` — ``η(p) = p / (p + K0 + K1·p + K2·p²)``. Same
      discharge floor.
    * ``"rational"`` — ``η(p) = (a1·p + a0) / (p² + b1·p + b0)``. No
      minimum floor (the rational form stays bounded naturally).

    The fit is sampled at 201 points (101 per direction) at construction
    and interpolated at runtime, so ``ac_to_dc`` and ``dc_to_ac`` remain
    numerical inverses of each other.

    Source: field fit by F. Müller (M.Sc. thesis, TUM) on a
    Sungrow SC1000TL inverter deployed in an FCR BESS.
    """

    _MIN_EFF_DCH = 0.2092

    # (P0, K) for each direction
    _NOTTON_CH = (0.007701864, 0.017290859)
    _NOTTON_DCH = (0.005511580, 0.018772838)

    # (K0, K1, K2) for each direction
    _RAMPINELLI_CH = (0.007421847, 0.003452202, 0.011994448)
    _RAMPINELLI_DCH = (0.003407887, 0.013809826, 0.003155305)

    # (a1, a0, b1, b0) for each direction
    _RATIONAL_CH = (47.773200770, 0.210333852, 47.572383928, 0.630988885)
    _RATIONAL_DCH = (57.341420538, 0.092381040, 57.318868901, 0.441493908)

    def __init__(self, fit: str = "notton") -> None:
        """
        Args:
            fit: Fit family, one of ``"notton"``, ``"rampinelli"``,
                ``"rational"``. Defaults to ``"notton"``.
        """
        if fit == "notton":
            eff_ch = self._sample_notton(self._NOTTON_CH, apply_floor=False)
            eff_dch = self._sample_notton(self._NOTTON_DCH, apply_floor=True)
        elif fit == "rampinelli":
            eff_ch = self._sample_rampinelli(self._RAMPINELLI_CH, apply_floor=False)
            eff_dch = self._sample_rampinelli(self._RAMPINELLI_DCH, apply_floor=True)
        elif fit == "rational":
            eff_ch = self._sample_rational(self._RATIONAL_CH)
            eff_dch = self._sample_rational(self._RATIONAL_DCH)
        else:
            raise ValueError(f"Unknown fit '{fit}'; expected 'notton', 'rampinelli', or 'rational'.")

        p = np.linspace(0, 1, 101)
        input_ch = p
        output_ch = input_ch * eff_ch

        input_dch = -p
        output_dch = np.zeros_like(p)
        output_dch[1:] = input_dch[1:] / eff_dch[1:]

        self._inp = np.hstack((input_dch[1:][::-1], 0.0, input_ch[1:])).tolist()
        self._out = np.hstack((output_dch[1:][::-1], 0.0, output_ch[1:])).tolist()

    @staticmethod
    def _sample_notton(coeffs: tuple[float, float], apply_floor: bool) -> np.ndarray:
        P0, K = coeffs
        p = np.linspace(0, 1, 101)
        eff = np.zeros_like(p)
        eff[1:] = p[1:] / (p[1:] + P0 + K * p[1:] ** 2)
        if apply_floor:
            eff[1:] = np.maximum(Sungrow._MIN_EFF_DCH, eff[1:])
        return eff

    @staticmethod
    def _sample_rampinelli(coeffs: tuple[float, float, float], apply_floor: bool) -> np.ndarray:
        K0, K1, K2 = coeffs
        p = np.linspace(0, 1, 101)
        eff = np.zeros_like(p)
        eff[1:] = p[1:] / (p[1:] + K0 + K1 * p[1:] + K2 * p[1:] ** 2)
        if apply_floor:
            eff[1:] = np.maximum(Sungrow._MIN_EFF_DCH, eff[1:])
        return eff

    @staticmethod
    def _sample_rational(coeffs: tuple[float, float, float, float]) -> np.ndarray:
        a1, a0, b1, b0 = coeffs
        p = np.linspace(0, 1, 101)
        eff = np.zeros_like(p)
        eff[1:] = (a1 * p[1:] + a0) / (p[1:] ** 2 + b1 * p[1:] + b0)
        return eff

    def ac_to_dc(self, power_ac: float) -> float:
        return interp1d_scalar(power_ac, self._inp, self._out)

    def dc_to_ac(self, power_dc: float) -> float:
        return interp1d_scalar(power_dc, self._out, self._inp)
