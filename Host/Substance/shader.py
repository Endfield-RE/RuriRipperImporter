"""Which generated shader stack this session is wiring, and where its files are.

The plugin used to carry the answer as a constant -- ``SHADER_NAME =
"Ruri_Endfield_Uber"`` and a ``shader/`` folder inside the package -- which made
the whole Painter half of the toolchain a one-game plugin by construction, and
put a game's name in a module that has no business knowing one.

The stack is instead resolved: the install publishes its own productName,
``Game/<that name>/shader/Substance/`` is where the generator was told to write
that game's Painter projection, and the shader's name is the name of the
manifest sitting in it. Adding a second game is a second recipe and a second
folder; nothing here changes, and nothing here spells a game.

WHICH install that is comes from the BROWSER, not from a stored copy of it. The
browser tab IS an install (its ``game_name`` is the productName that build
published), and the decoder, the texture-role layer and every game tab already
read it there. A second copy in the settings store drifted the moment the panel
that used to write it was deleted -- and drifted silently, as a stored empty
string that reads exactly like "not identified yet".
"""

from __future__ import annotations

from ...Kernel import shaderstack


def game_name():
    """The product the browser's current tab is on, or "" before one is typed."""
    from ...Kernel.app import browser
    try:
        config = browser.active_config(browser.state_of(None))
    except (KeyError, RuntimeError):
        return ""
    return ((config.game_name if config is not None else "") or "").strip()


def stack():
    """The stack for the game this session is reading, or None when there is none to wire --
    no install identified yet, or a game the generator ships no stack for this application for.
    Never another game's: a set wired against another game's shader is a wrong result."""
    game = game_name()
    return shaderstack.stack_for(game) if game else None


def absence():
    """Why :func:`stack` answered None, worded for the report."""
    game = game_name()
    if not game:
        return ("no install has been identified yet -- type this game's folder into the "
                "RuriRipper panel first")
    return "the generator ships no shader stack for {0} to this application".format(game)


def _required():
    found = stack()
    if found is None:
        raise RuntimeError(absence())
    return found


def name():
    return _required().shader_name()


def source_path():
    return _required().asset(name() + ".glsl")


def manifest_path():
    return _required().manifest_path()
