import numpy as np

from simses.interpolation import interp1d_scalar


class Rampinelli:
    """Generic parametric PV-inverter loss family.

    Efficiency curve of the form
    ``η(p) = p / (p + K0 + K1·p + K2·p²)``
    where ``p`` is the magnitude of normalised power (p.u. of the
    converter's rated max power). Three-parameter extension of the
    Notton form — the extra linear term lets the fit capture a wider
    range of measured efficiency curves. Symmetric about zero. The fit
    is sampled at 201 points (101 per direction, mirrored about zero)
    at construction and interpolated at runtime, so ``ac_to_dc`` and
    ``dc_to_ac`` remain numerical inverses of each other.

    Source: Rampinelli, G. A.; Krenzinger, A.; Chenlo Romero, F. (2014).
    *Mathematical models for efficiency of inverters used in grid
    connected photovoltaic systems.* Renewable and Sustainable Energy
    Reviews 34, 578–587, doi:10.1016/j.rser.2014.03.047.
    """

    def __init__(self, K0: float, K1: float, K2: float) -> None:
        """
        Args:
            K0: No-load loss coefficient (p.u.).
            K1: Linear loss coefficient (p.u.).
            K2: Quadratic loss coefficient (p.u.).
        """
        p = np.linspace(0, 1, 101)
        eff = np.zeros_like(p)
        eff[1:] = p[1:] / (p[1:] + K0 + K1 * p[1:] + K2 * p[1:] ** 2)

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
