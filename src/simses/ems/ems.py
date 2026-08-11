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
            aux_soc_target: float = 0.5,
    ):
        self.state = EMSState()
        self.storage_main = storage_main
        self.storage_aux = storage_aux
        self.aux_soc_target = aux_soc_target

    def step(self, power_setpoint:float, dt: float) -> None:
        aux_optimal = self.storage_aux.target_soc(self.aux_soc_target, dt)
        main_setpoint = power_setpoint - aux_optimal

        power_main = self.storage_main.step(main_setpoint, dt)

        aux_setpoint = power_setpoint - power_main
        power_aux = self.storage_aux.step(aux_setpoint, dt)

        self.state.power_setpoint = power_setpoint
        self.state.power = power_main + power_aux
        self.state.power_main = power_main
        self.state.power_aux = power_aux

    def target_soc(self, soc_target: float, dt: float) -> float:
        main_power = self.storage_main.target_soc(soc_target, dt)
        aux_power = self.storage_aux.target_soc(self.aux_soc_target, dt)
        return main_power + aux_power
