"""Cyclic degradation model for the Gasper et al. (2023) NMC|Gr B1 cell.

Ported from NREL/BLAST-Lite:
    https://github.com/NREL/BLAST-Lite/blob/main/blast/models/nmc_gr_50Ah_B1_2020.py
Original author: Paul Gasper (NREL).

Underlying model: Gasper et al., "Degradation and modeling of large-format
commercial lithium-ion cells as a function of chemistry, design, and aging
conditions", J. Energy Storage 73 (2023) 109042.
DOI: https://doi.org/10.1016/j.est.2023.109042 — see Appendix A.8 (ML model
for 'NMC|Gr B1').

The mathematics and coefficients below are reproduced one-to-one from
BLAST-Lite. The class is rewired to simses's stateless per-half-cycle
``CyclicDegradation`` Protocol API and uses an exact virtual-FEC
continuation of the underlying ``q = k_cyc * (EFC/1e5)**pcyc`` trajectory.

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
from simses.degradation.cycle_detector import HalfCycle
from simses.degradation.cyclic import CyclicDegradation
from simses.model.degradation.gasper_common import T_REF_K, power_law_continuation

# Coefficients from BLAST-Lite (nmc_gr_50Ah_B1_2020.py / paper Table A.8).
P3 = 0.844
P4 = 0.458
PCYC = 0.467

# Power-law normalisation: q = k_cyc * (EFC / EFC_SCALE)**PCYC.
EFC_SCALE = 1e5


class GasperNMCGrB1Cyclic(CyclicDegradation):
    """Cyclic aging for the Gasper et al. 'NMC|Gr B1' cell (50 Ah pouch).

    Stateless: virtual-FEC continuation is driven by ``accumulated_qloss``
    passed in by :class:`~simses.degradation.degradation.DegradationModel`.
    Temperature is sampled instantaneously from ``state.T`` at the moment
    the half-cycle completes; DoD, C-rate and FEC come from ``half_cycle``.
    """

    def update_capacity(self, state: BatteryState, half_cycle: HalfCycle, accumulated_qloss: float) -> float:
        delta_efc = half_cycle.full_equivalent_cycles
        if delta_efc == 0.0:
            return 0.0

        TdegKN = (state.T + 273.15) / T_REF_K
        dod = half_cycle.depth_of_discharge
        crate = half_cycle.c_rate

        kcyc = abs(P3 * ((dod**2) * (TdegKN**3) * math.sqrt(crate)) ** P4)

        delta_efc_scaled = delta_efc / EFC_SCALE
        return power_law_continuation(kcyc, accumulated_qloss, delta_efc_scaled, PCYC)

    def update_resistance(self, state: BatteryState, half_cycle: HalfCycle) -> float:
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
