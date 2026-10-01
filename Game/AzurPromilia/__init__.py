"""AzurPromilia -- everything the add-on has for this game and nothing else.

Two tabs and the head of the Look tab, none of which means anything for another title:

``Scene``      every scene the install carries, under the folder tree the game files it in, saying
               which of them ship a built scene file at all. (``scene``)
``Character``  the cast off the game's own tables, one row per outfit under the character it
               dresses. (``roster``)
Look           the volume sets the render pipeline puts its post chain under, and the colour
               grading each gives it. (``display``)

Every reading behind them lives upstream in ``Ruri.RipperHook.AzurPromilia``: the configuration
tables and the cipher they are kept under, the outfit -> unit -> model join, and what an avatar seed
loads as -- the prefab plus the parts its own map wears, at one level. A row's payload is its seed,
so both tabs load and reveal through the kernel's own verbs.

Declared as one GAME_MODULE row (see ``Game``), so the core panel reveals both tabs exactly while
the install in front of it IS this game, and never names it itself.
"""

from __future__ import annotations

import importlib

from ...Kernel import host as host_port
from .. import GameModule, GameSection, GameTab

#: The parts the tabs are composed of, each with the capability its host must answer. The cast and
#: the scenes are lists whose rows load through the kernel's own verbs, which need nothing of the host
#: the browser does not already need; the volume sets grade the host's display chain, so they need one.
SECTIONS = (GameSection("roster"), GameSection("scene"), GameSection("display", host_port.Compositor))

_LOADED = []


def _register():
    _LOADED[:] = [importlib.import_module("." + one.id, __name__)
                  for one in SECTIONS if one.available]
    for module in _LOADED:
        module.register()


def _unregister():
    for module in reversed(_LOADED):
        module.unregister()
    _LOADED[:] = []


GAME_MODULE = GameModule(
    # The productName this game's player builds under, as its own app.info states it -- the same
    # string the upstream decoder declares, so the join is equality.
    game_name="AzurPromilia",
    label="Azur Promilia",
    sections=SECTIONS,
    tabs=(
        GameTab("scene", "Scene",
                "Every scene the install carries, and which of them ship a built scene file",
                ("scene", "draw")),
        GameTab("character", "Character",
                "The cast off the game's own tables, one row per outfit",
                ("roster", "draw")),
    ),
    # The volume sets the pipeline grades its post chain with: this title's own post-processing
    # objects, read by its own hook.
    look=("display", "draw"),
    register=_register,
    unregister=_unregister,
)
