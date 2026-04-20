import numpy as np

from simses.interpolation import interp1d_scalar


class Bonfiglioli:
    """Bonfiglioli RPS TL-4Q converter loss model.

    Notton-form efficiency fit with asymmetric charge and discharge
    coefficients and a minimum-efficiency floor that clips the fit at
    low normalised power. Two parameter sets are published:

    * :attr:`DATASHEET` (default) — manufacturer datasheet measurements.
      Symmetric: ``P0=0.0072, K=0.034, min_eff=0.5813`` for both
      directions.
    * :attr:`FIELD_DATA` — measured on FCR battery systems. Asymmetric:
      charge ``P0=0.00195, K=0.01349, min_eff=0.3441``; discharge
      ``P0=0.00292, K=0.03609, min_eff=0.2742``. Reflects real
      deployment losses including auxiliary consumption.

    Source: field fit and datasheet reading by F. Müller (M.Sc. thesis,
    TUM), from the
    `Bonfiglioli RPS TL-4Q datasheet
    <http://www.docsbonfiglioli.com/pdf_documents/catalogue/VE_CAT_RTL-4Q_STD_ENG-ITA_R00_5_WEB.pdf>`_.
    """

    # (P0_ch, K_ch, min_eff_ch, P0_dch, K_dch, min_eff_dch)
    DATASHEET = (0.0072, 0.034, 0.5813, 0.0072, 0.034, 0.5813)
    FIELD_DATA = (0.00195, 0.01349, 0.3441, 0.00292, 0.03609, 0.2742)

    def __init__(self, coefficients: tuple[float, float, float, float, float, float] = DATASHEET) -> None:
        """
        Args:
            coefficients: ``(P0_ch, K_ch, min_eff_ch, P0_dch, K_dch,
                min_eff_dch)`` tuple. Defaults to :attr:`DATASHEET`.
        """
        P0_ch, K_ch, min_eff_ch, P0_dch, K_dch, min_eff_dch = coefficients

        p = np.linspace(0, 1, 101)

        eff_ch = np.zeros_like(p)
        eff_ch[1:] = np.maximum(min_eff_ch, p[1:] / (p[1:] + P0_ch + K_ch * p[1:] ** 2))
        input_ch = p
        output_ch = input_ch * eff_ch

        eff_dch = np.zeros_like(p)
        eff_dch[1:] = np.maximum(min_eff_dch, p[1:] / (p[1:] + P0_dch + K_dch * p[1:] ** 2))
        input_dch = -p
        output_dch = np.zeros_like(p)
        output_dch[1:] = input_dch[1:] / eff_dch[1:]

        self._inp = np.hstack((input_dch[1:][::-1], 0.0, input_ch[1:])).tolist()
        self._out = np.hstack((output_dch[1:][::-1], 0.0, output_ch[1:])).tolist()

    def ac_to_dc(self, power_ac: float) -> float:
        return interp1d_scalar(power_ac, self._inp, self._out)

    def dc_to_ac(self, power_dc: float) -> float:
        return interp1d_scalar(power_dc, self._out, self._inp)
