"""Calendar degradation model for the Gasper et al. (2023) NMC|Gr B1 cell.

Ported from NREL/BLAST-Lite:
    https://github.com/NREL/BLAST-Lite/blob/main/blast/models/nmc_gr_50Ah_B1_2020.py
Original author: Paul Gasper (NREL).

Underlying model: Gasper et al., "Degradation and modeling of large-format
commercial lithium-ion cells as a function of chemistry, design, and aging
conditions", J. Energy Storage 73 (2023) 109042.
DOI: https://doi.org/10.1016/j.est.2023.109042 — see Appendix A.8 (ML model
for 'NMC|Gr B1').

The mathematics and coefficients below are reproduced one-to-one from
BLAST-Lite. The class is rewired to simses's stateless per-step
``CalendarDegradation`` Protocol API and uses an exact virtual-time
continuation of the underlying ``q = k_cal * (t/1e4d)**pcal`` trajectory.

BLAST-Lite is distributed under BSD-3-Clause; the license text is reproduced
at the bottom of this file as required by the copyright notice.

The Gasper et al. paper publishes capacity-fade equations only; no
resistance-rise model is provided. ``update_resistance`` therefore returns 0.

Applicability note
------------------
The fit corresponds to a specific ~2020-vintage 50 Ah pouch NMC|Gr cell
(anonymised in the paper). Manufacturer-specific behaviour of modern
large-format NMC|Gr cells will differ; treat quantitative EOL predictions
from this model as approximate. Of the four NMC|Gr chemistries in Gasper
et al. its single-term power-law form extrapolates cleanly outside the
[0.8, 1] DoD training band.
"""

import math

from simses.battery.state import BatteryState
from simses.degradation.calendar import CalendarDegradation
from simses.model.degradation.gasper_common import (
    T_REF_K,
    UA_REF,
    power_law_continuation,
    ua_from_soc,
)

# Coefficients from BLAST-Lite (nmc_gr_50Ah_B1_2020.py / paper Table A.8).
P1 = 36.2
P2 = -4.4
PCAL = 0.708

# Power-law normalisation: q = k_cal * (t_days / TIME_SCALE_DAYS)**PCAL.
TIME_SCALE_DAYS = 1e4


class GasperNMCGrB1Calendar(CalendarDegradation):
    """Calendar aging for the Gasper et al. 'NMC|Gr B1' cell (50 Ah pouch).

    Stateless: virtual-time continuation is driven by ``accumulated_qloss``
    passed in by :class:`~simses.degradation.degradation.DegradationModel`.
    """

    def update_capacity(self, state: BatteryState, dt: float, accumulated_qloss: float) -> float:
        if dt == 0.0:
            return 0.0

        TdegK = state.T + 273.15
        TdegKN = TdegK / T_REF_K
        UaN = ua_from_soc(state.soc) / UA_REF

        kcal = P1 * math.exp(P2 * (1.0 / (TdegKN**3)) * (UaN ** (1.0 / 3.0)))

        dt_days_scaled = (dt / 86400.0) / TIME_SCALE_DAYS
        return power_law_continuation(kcal, accumulated_qloss, dt_days_scaled, PCAL)

    def update_resistance(self, state: BatteryState, dt: float) -> float:
        return 0.0


# ---------------------------------------------------------------------------
# BLAST-Lite BSD-3-Clause license (verbatim, as required by the BSD-3
# clauses governing the redistribution of the ported model code above).
# ---------------------------------------------------------------------------
#
# Copyright (c) 2023, Alliance for Energy Innovation, LLC
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice,
#   this list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF
# THE POSSIBILITY OF SUCH DAMAGE.
