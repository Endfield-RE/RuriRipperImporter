"""What Painter's viewport shows the ported shader through.

The generated shader writes the final picture: its last step is the game's own output
transform, the one Blender's compositor applies. So the display has exactly one
requirement, and it is a correctness matter rather than a preference -- it must add
nothing on top: Linear tone mapping and no colour LUT.

An import applies it. This is where it can be looked at and applied again without one:
a project opened from disk, or a colour managed project that refused the tone mapping
the first time, leave the display changing the picture a second time, and until now
nothing said so anywhere.

Registered as a "look" section (:mod:`Kernel.app.look`), so the tab that asks what
the frame finally looks like gets this host's answer without naming this host.
"""

from __future__ import annotations

from . import shader, sp_apply
from ...Kernel import host as host_port
from ...Kernel.app import browser as app_browser
from ...Kernel.app import command
from ...Kernel.app.state import Field, Schema
from ...Kernel.app import state as app_state

STATE = "ruri_display"

#: What each switch is called and what it turns on, keyed by the option the
#: browser already remembers -- so the words are said once and this section reads
#: the same values the import does.
_SWITCHES = ("neutral_display",)

DISPLAY = Schema("Display", """The display section's own state: the last thing it
did.""", (
    Field("status", app_state.STRING, ""),
))

HANDLERS = app_state.Handlers("Substance.display")


def state_of(context):
    return host_port.current().panel_state(context, STATE)


def _identified(context):
    """A shader stack is resolved from the install in front of the panel, so until one is
    identified -- and the game ships one -- there is nothing to state requirements."""
    return shader.stack() is not None


def _apply(context, arguments):
    """Put the display back to adding nothing on top of the shader."""
    state = state_of(context)
    lines = []
    try:
        sp_apply.apply_display_settings(
            lines, app_browser.as_options(app_browser.state_of(context)))
    except Exception as exc:
        state.status = "{0}: {1}".format(type(exc).__name__, exc)
        return {"CANCELLED"}
    state.status = "  ·  ".join(line for line in lines if not line.startswith("!! ")) \
        or "nothing to apply -- the switch below is off."
    for line in lines:
        host_port.current().log(host_port.WARNING if line.startswith("!! ")
                                else host_port.INFO, line)
    return None


APPLY = command.COMMANDS.define(
    "ruri.display_apply", "Apply Display Settings", _apply,
    description="Set the display to add nothing on top of the shader: Linear tone mapping, "
                "no colour LUT",
    icon="IMPORT", requires=host_port.DisplaySettings, poll=_identified)


def draw(layout, context):
    """The Display section."""
    box = layout.box()
    box.label(text="Display", icon="SHADING_RENDERED")
    if not _identified(context):
        box.label(text="No generated shader states a requirement: {0}.".format(shader.absence()),
                  icon="INFO")
        return
    box.label(text="Tone mapping Linear, no colour LUT -- the shader writes the final picture, "
                   "and a second pass changes it.", icon="INFO")
    switches = box.column(align=True)
    browser = app_browser.state_of(context)
    for key in _SWITCHES:
        switches.prop(browser, key)
    box.operator(APPLY.id, icon="IMPORT")
    state = state_of(context)
    if state.status:
        box.label(text=state.status, icon="INFO")


def register():
    host_port.current().register_state(STATE, DISPLAY, HANDLERS)


def unregister():
    host_port.current().unregister_state(STATE)
