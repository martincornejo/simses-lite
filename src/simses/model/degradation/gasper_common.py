"""Shared helpers for the Gasper et al. (2023) family of degradation models.

This module hosts code that is reused by every ``gasper_*_calendar.py`` and
``gasper_*_cyclic.py`` module: the anode-potential function ``ua_from_soc``
(ported from BLAST-Lite, in turn derived from Safari & Delacourt, 2011) and
the closed-form power-law continuation helper ``power_law_continuation``
used to translate BLAST-Lite's offline ``q = k * x**p`` aggregation into
simses's per-step incremental ``CalendarDegradation`` / ``CyclicDegradation``
Protocol API.

The ``ua_from_soc`` function is ported from NREL/BLAST-Lite and is
distributed under the BSD-3-Clause license reproduced at the bottom of this
file. The continuation helper is original to simses and is covered by the
project license.

Original BLAST-Lite source:
    https://github.com/NREL/BLAST-Lite/blob/main/blast/models/degradation_model.py
Underlying paper:
    Gasper et al., "Degradation and modeling of large-format commercial
    lithium-ion cells as a function of chemistry, design, and aging
    conditions", J. Energy Storage 73 (2023) 109042.
    DOI: https://doi.org/10.1016/j.est.2023.109042
"""

import math

# ---------------------------------------------------------------------------
# Shared functions
# ---------------------------------------------------------------------------

# Reference anode potential at ~50% SOC; used to normalise Ua in the NMC|Gr
# calendar models (see e.g. nmc_gr_75Ah_A_2019.py in BLAST-Lite).
UA_REF = 0.123  # V

# Reference temperature used by the NMC|Gr models' Arrhenius-style
# normalisation (308.15 K = 35 °C).
T_REF_K = 273.15 + 35.0  # K


def ua_from_soc(soc: float) -> float:
    """Return the graphite anode potential ``Ua`` (V) for a given cell SOC.

    Implements the closed-form approximation used throughout Gasper et al.
    (2023) and BLAST-Lite: the lithiation fraction ``xa`` is linear in SOC,
    and ``Ua`` is a sum of one decaying exponential and four ``tanh`` terms
    plus a constant. Originally from Safari & Delacourt (2011).

    Args:
        soc: Cell state of charge in p.u. (0 to 1).

    Returns:
        Anode potential vs. Li/Li+ in volts.
    """
    xa = 8.5e-3 + soc * (0.78 - 8.5e-3)
    return (
        0.6379
        + 0.5416 * math.exp(-305.5309 * xa)
        + 0.044 * math.tanh(-(xa - 0.1958) / 0.1088)
        - 0.1978 * math.tanh((xa - 1.0571) / 0.0854)
        - 0.6875 * math.tanh((xa + 0.0117) / 0.0529)
        - 0.0175 * math.tanh((xa - 0.5692) / 0.0875)
    )


def power_law_continuation(k: float, accumulated_qloss: float, dx: float, p: float) -> float:
    """Return the incremental qloss for one step of a ``qloss = k * x**p`` trajectory.

    Uses *virtual-x continuation*: the accumulated qloss is inverted to find
    the equivalent ``x_virtual`` already "spent" on the current trajectory,
    the trajectory is advanced by ``dx``, and the new qloss is differenced
    against the accumulated value. This is exact (no linearisation error)
    and mirrors the pattern used by the existing Sony LFP Naumann models.

    Args:
        k: Stress-factor prefactor of the trajectory (instantaneous).
        accumulated_qloss: qloss accumulated on this trajectory so far (p.u.).
        dx: Increment of the independent variable for this step
            (days for calendar, EFC for cyclic; pre-scaled by the model's
            normalisation factor if any).
        p: Power-law exponent.

    Returns:
        ``delta_qloss`` (p.u.) to add to ``accumulated_qloss`` this step.
    """
    if k <= 0.0 or dx == 0.0:
        return 0.0
    if accumulated_qloss <= 0.0:
        return k * dx**p
    virtual_x = (accumulated_qloss / k) ** (1.0 / p)
    return k * (virtual_x + dx) ** p - accumulated_qloss


# ---------------------------------------------------------------------------
# Attribution and license of the BLAST-Lite code ported above
# ---------------------------------------------------------------------------
#
# The ``ua_from_soc`` function is a one-to-one port of the static
# ``_get_Ua`` method of BLAST-Lite's ``BatteryDegradationModel`` base class.
# Original implementation: Paul Gasper (NREL).
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
