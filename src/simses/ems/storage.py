from typing import Protocol


class StorageState(Protocol):
    power_setpoint: float = 0.0
    power: float = 0.0
    loss: float = 0.0


class Storage(Protocol):
    state: StorageState

    def step(self, power_setpoint:float, dt: float) -> None:
        ...

    def target_soc(self, soc_target: float, dt: float) -> None:
        ...
