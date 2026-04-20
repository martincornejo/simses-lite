import numpy as np

from simses.interpolation import interp1d_scalar


def _notton_lut(P0_ch: float, K_ch: float, P0_dch: float, K_dch: float) -> tuple[list[float], list[float]]:
    """Build a 201-point input/output LUT for a Notton-form loss model.

    Efficiency follows ``η(p) = p / (p + P0 + K·p²)`` on each direction
    independently. The LUT stitches charge (0 → 1) and discharge (−1 → 0)
    branches into a single monotonic curve so that ``interp1d_scalar``
    can invert it exactly.
    """
    p = np.linspace(0, 1, 101)

    # Charge branch (AC -> DC): efficiency reduces DC output; P_dc = P_ac · η.
    eff_ch = p[1:] / (p[1:] + P0_ch + K_ch * p[1:] ** 2)
    input_ch = p
    output_ch = np.zeros_like(p)
    output_ch[1:] = p[1:] * eff_ch

    # Discharge branch (DC -> AC): battery supplies the loss; P_dc = P_ac / η
    # (i.e. |DC| > |AC|). With input_dch = −p, output_dch = input_dch / η.
    eff_dch = p[1:] / (p[1:] + P0_dch + K_dch * p[1:] ** 2)
    input_dch = -p
    output_dch = np.zeros_like(p)
    output_dch[1:] = -p[1:] / eff_dch

    inp = np.hstack((input_dch[1:][::-1], 0.0, input_ch[1:])).tolist()
    out = np.hstack((output_dch[1:][::-1], 0.0, output_ch[1:])).tolist()
    return inp, out


class Notton:
    """Generic parametric PV-inverter loss family — symmetric form.

    Efficiency curve of the form ``η(p) = p / (p + P0 + K·p²)`` where
    ``p`` is the magnitude of normalised power (p.u. of the converter's
    rated max power). Same coefficients apply to charge and discharge.

    For the three published inverter presets see :class:`NottonType1`,
    :class:`NottonType2`, :class:`NottonType3`. For Notton-form fits
    with per-direction coefficients see :class:`AsymmetricNotton`.

    Source: Notton, G.; Lazarov, V.; Stoyanov, L. (2010). *Optimal sizing
    of a grid-connected PV system for various PV module technologies and
    inclinations, inverter efficiency characteristics and locations.*
    Renewable Energy 35(2) 541–554, doi:10.1016/j.renene.2009.07.013.
    """

    def __init__(self, P0: float, K: float) -> None:
        """
        Args:
            P0: No-load loss coefficient (p.u.).
            K: Quadratic-loss coefficient (p.u.).
        """
        self._inp, self._out = _notton_lut(P0, K, P0, K)

    def ac_to_dc(self, power_ac: float) -> float:
        return interp1d_scalar(power_ac, self._inp, self._out)

    def dc_to_ac(self, power_dc: float) -> float:
        return interp1d_scalar(power_dc, self._out, self._inp)


class AsymmetricNotton:
    """Notton-form loss family with per-direction coefficients.

    Same efficiency law as :class:`Notton` but with independent charge
    and discharge parameter sets — each a ``(P0, K)`` pair. Used by
    manufacturer product models whose measured efficiency differs
    between charging and discharging (e.g. :class:`BonfiglioliTL4QFieldData`,
    :class:`SungrowSC1000TL`).
    """

    def __init__(
        self,
        charge: tuple[float, float],
        discharge: tuple[float, float],
    ) -> None:
        """
        Args:
            charge: ``(P0, K)`` coefficients for the charge branch.
            discharge: ``(P0, K)`` coefficients for the discharge branch.
        """
        P0_ch, K_ch = charge
        P0_dch, K_dch = discharge
        self._inp, self._out = _notton_lut(P0_ch, K_ch, P0_dch, K_dch)

    def ac_to_dc(self, power_ac: float) -> float:
        return interp1d_scalar(power_ac, self._inp, self._out)

    def dc_to_ac(self, power_dc: float) -> float:
        return interp1d_scalar(power_dc, self._out, self._inp)


class NottonType1(Notton):
    """Notton Type-1 inverter preset (``P0 = 0.0145, K = 0.0437``).

    Source: Notton et al. 2010, Renewable Energy 35(2) 541–554.
    """

    def __init__(self) -> None:
        super().__init__(P0=0.0145, K=0.0437)


class NottonType2(Notton):
    """Notton Type-2 inverter preset (``P0 = 0.0072, K = 0.0345``).

    Source: Notton et al. 2010, Renewable Energy 35(2) 541–554.
    """

    def __init__(self) -> None:
        super().__init__(P0=0.0072, K=0.0345)


class NottonType3(Notton):
    """Notton Type-3 inverter preset (``P0 = 0.0088, K = 0.1149``).

    Source: Notton et al. 2010, Renewable Energy 35(2) 541–554.
    """

    def __init__(self) -> None:
        super().__init__(P0=0.0088, K=0.1149)
