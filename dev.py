from simses.battery.battery import Battery, BatteryState
from simses.model.cell.sony_lfp import SonyLFP

cell = SonyLFP()
bat = Battery(cell, voltage=320, energy_capacity=96e3)

state = BatteryState.initialize(bat, start_soc=0.0, start_T=273.15 + 25)

print(state)

for t in range(0, 4 * 3600, 60):
    state = bat.update(state, power_setpoint=25e3, t=t)

print(state)

for t in range(4 * 3600, 8 * 3600, 60):
    state = bat.update(state, power_setpoint=-25e3, t=t)  # TODO: fix small deviaiton

print(state)