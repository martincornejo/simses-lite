from simses.model.converter.notton import AsymmetricNotton, Notton


class BonfiglioliTL4Q(Notton):
    """Bonfiglioli RPS TL-4Q converter — datasheet parameterisation.

    Symmetric Notton-form fit with ``P0 = 0.0072, K = 0.034`` measured
    under manufacturer datasheet conditions.

    See :class:`BonfiglioliTL4QFieldData` for the asymmetric variant
    parameterised from FCR field data.

    Source: F. Müller (M.Sc. thesis, TUM) — Notton fit of the
    `Bonfiglioli RPS TL-4Q datasheet
    <http://www.docsbonfiglioli.com/pdf_documents/catalogue/VE_CAT_RTL-4Q_STD_ENG-ITA_R00_5_WEB.pdf>`_.
    """

    def __init__(self) -> None:
        super().__init__(P0=0.0072, K=0.034)


class BonfiglioliTL4QFieldData(AsymmetricNotton):
    """Bonfiglioli RPS TL-4Q converter — FCR field-data parameterisation.

    Asymmetric Notton-form fit measured on frequency containment reserve
    (FCR) battery systems; reflects real deployment losses including
    auxiliary consumption. Charge: ``P0 = 0.00195, K = 0.01349``.
    Discharge: ``P0 = 0.00292, K = 0.03609``.

    See :class:`BonfiglioliTL4Q` for the symmetric datasheet variant.

    Source: F. Müller (M.Sc. thesis, TUM) — field fit on FCR BESS
    deployments of the Bonfiglioli RPS TL-4Q.
    """

    def __init__(self) -> None:
        super().__init__(
            charge=(0.00195, 0.01349),
            discharge=(0.00292, 0.03609),
        )
