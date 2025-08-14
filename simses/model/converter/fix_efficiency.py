class FixedEfficiency:
    def __init__(self, effc, effd=None) -> None:
        self.effc = effc
        self.effd = effd if effd is not None else effc

    def ac_to_dc(self, power_ac: float) -> float:
        if power_ac >= 0:
            return power_ac * self.effc
        else:  # power_ac < 0:
            return power_ac / self.effd

    def dc_to_ac(self, power_dc: float) -> float:
        if power_dc >= 0:
            return power_dc / self.effc
        else:  # power_dc < 0:
            return power_dc * self.effd
