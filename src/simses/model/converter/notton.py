import numpy as np

from simses.interpolation import interp1d_scalar


class Notton:
    """Generic parametric PV-inverter loss model.

    Efficiency curve of the form ``η(p) = p / (p + P0 + K·p²)`` where ``p``
    is the magnitude of normalised power (p.u. of the converter's rated
    max power). The fit is sampled at 201 points (101 per direction,
    mirrored about zero) at construction and interpolated at runtime, so
    ``ac_to_dc`` and ``dc_to_ac`` remain numerical inverses of each other.

    Three coefficient sets are published in Notton et al. (2010):
    ``TYPE_1`` (P0=0.0145, K=0.0437), ``TYPE_2`` (P0=0.0072, K=0.0345,
    used by default here), ``TYPE_3`` (P0=0.0088, K=0.1149). Custom
    coefficients can also be supplied directly.

    Source: Notton, G.; Lazarov, V.; Stoyanov, L. (2010). *Optimal sizing
    of a grid-connected PV system for various PV module technologies and
    inclinations, inverter efficiency characteristics and locations.*
    Renewable Energy 35(2) 541–554, doi:10.1016/j.renene.2009.07.013.
    """

    TYPE_1 = (0.0145, 0.0437)
    TYPE_2 = (0.0072, 0.0345)
    TYPE_3 = (0.0088, 0.1149)

    def __init__(self, coefficients: tuple[float, float] = TYPE_2) -> None:
        """
        Args:
            coefficients: ``(P0, K)`` tuple of Notton fit coefficients.
                Defaults to the published Type-2 inverter parameters.
        """
        P0, K = coefficients

        # Evaluate at non-zero magnitudes only; index 0 (p=0) is handled as output=0.
        p = np.linspace(0, 1, 101)
        eff = np.zeros_like(p)
        eff[1:] = p[1:] / (p[1:] + P0 + K * p[1:] ** 2)

        input_ch = p
        output_ch = input_ch * eff

        input_dch = -p
        output_dch = np.zeros_like(p)
        output_dch[1:] = input_dch[1:] / eff[1:]

        self._inp = np.hstack((input_dch[1:][::-1], 0.0, input_ch[1:])).tolist()
        self._out = np.hstack((output_dch[1:][::-1], 0.0, output_ch[1:])).tolist()

    def ac_to_dc(self, power_ac: float) -> float:
        return interp1d_scalar(power_ac, self._inp, self._out)

    def dc_to_ac(self, power_dc: float) -> float:
        return interp1d_scalar(power_dc, self._out, self._inp)
