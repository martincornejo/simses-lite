from dataclasses import dataclass

from simses.ems.storage import Storage


@dataclass
class EMSState:
    power_setpoint: float = 0.0
    power: float = 0.0
    power_main: float = 0.0
    power_aux: float = 0.0
    loss: float = 0.0

class EMS:
    def __init__(
            self,
            storage_main: Storage,
            storage_aux: Storage,
            main_power_change: float,  # limit how fast power to main system can change in W/s
            aux_soc_target: float = 0.5,
    ):
        self.state = EMSState()
        self.storage_main = storage_main
        self.storage_aux = storage_aux
        self.main_power_change = main_power_change
        self.aux_soc_target = aux_soc_target

    def step(self, power_setpoint:float, dt: float) -> None:
        aux_optimal = self.storage_aux.target_soc(self.aux_soc_target, dt)
        main_setpoint = self._main_powerlimit(power_setpoint - aux_optimal, dt)

        power_main = self.storage_main.step(main_setpoint, dt)

        aux_setpoint = power_setpoint - power_main
        power_aux = self.storage_aux.step(aux_setpoint, dt)

        self.state.power_setpoint = power_setpoint
        self.state.power = power_main + power_aux
        self.state.power_main = power_main
        self.state.power_aux = power_aux

    def target_soc(self, soc_target: float, dt: float) -> float:
        main_power = self.storage_main.target_soc(soc_target, dt)
        main_power = self._main_powerlimit(main_power, dt)
        aux_power = self.storage_aux.target_soc(self.aux_soc_target, dt)
        return main_power + aux_power

    def _main_powerlimit(self, power_setpoint: float, dt: float) -> float:
        dp = dt * self.main_power_change
        last_power = self.state.power_main
        return min(max(power_setpoint, last_power-dp), last_power+dp)
