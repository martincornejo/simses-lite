from simses.model.converter.notton import AsymmetricNotton


class SungrowSC1000TL(AsymmetricNotton):
    """Sungrow SC1000TL converter — FCR field-data parameterisation.

    Asymmetric Notton-form fit, backed by field data from a frequency
    containment reserve storage system. Charge: ``P0 = 0.007701864,
    K = 0.017290859``. Discharge: ``P0 = 0.005511580, K = 0.018772838``.

    Source: field fit by F. Müller (M.Sc. thesis, TUM) on a Sungrow
    SC1000TL inverter deployed in an FCR BESS. The thesis also provides
    Rampinelli and rational-form fits of the same dataset; the Notton
    fit was the configured default in the legacy simses implementation
    and is the one reproduced here.
    """

    def __init__(self) -> None:
        super().__init__(
            charge=(0.007701864, 0.017290859),
            discharge=(0.005511580, 0.018772838),
        )
