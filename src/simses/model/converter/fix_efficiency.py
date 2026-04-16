class FixedEfficiency:
    """Constant-efficiency converter loss model.

    Applies a fixed efficiency factor in each direction. Pass a single
    ``float`` for a symmetric model (same efficiency for charging and
    discharging), or a ``(charge, discharge)`` tuple for distinct
    efficiencies per direction.

    Examples:
        >>> FixedEfficiency(0.95)            # symmetric 95% round-trip factor
        >>> FixedEfficiency((0.96, 0.94))    # 96% charging, 94% discharging
    """

    def __init__(self, eff: float | tuple[float, float]) -> None:
        """
        Args:
            eff: Either a single efficiency in p.u. (``0 < eff <= 1``), or
                a ``(charge, discharge)`` tuple of per-direction
                efficiencies in p.u.
        """
        if isinstance(eff, tuple):
            self.eff_charge, self.eff_discharge = eff
        else:
            self.eff_charge = self.eff_discharge = eff

    def ac_to_dc(self, power_ac: float) -> float:
        if power_ac >= 0:
            return power_ac * self.eff_charge
        else:  # power_ac < 0
            return power_ac / self.eff_discharge

    def dc_to_ac(self, power_dc: float) -> float:
        if power_dc >= 0:
            return power_dc / self.eff_charge
        else:  # power_dc < 0
            return power_dc * self.eff_discharge
