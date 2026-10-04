"""This game's answer to "bring the model's own secondary motion across".

Two ways in, one implementation, and neither of them is here: the import options
carry it as a switch and the asset browser as a button, both drawn by the core panel
off the capability the option declares. What IS here is the READING -- the core
never learns that these settings exist, only that this game answered.

Writing them onto a rig is the host's (``Host.write_secondary_motion``), because
which solver holds them and what it calls each parameter is a fact about the
application, not about this game. Nothing here imports a host.
"""

from __future__ import annotations

from ...Kernel.bridge import cabmap_state
from . import cloth


def read(cabs):
    """What those model prefabs state about their secondary motion, in the shared
    vocabulary (:mod:`Kernel.app.rigging`), or None for nothing to bring across.

    This is the callable the game module declares (see ``Game.GameModule``), so both
    ways in reach it without the host ever learning what these settings are -- only
    whether this game answered."""
    cabs = [cab for cab in cabs if cab]
    if cabmap_state.BRIDGE is None or not cabs:
        return None
    reading = cloth.read(cabs)
    return reading if reading["configs"] else None
