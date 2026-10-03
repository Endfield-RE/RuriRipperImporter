"""The StreamingScene tab's third half: the game's UI display stages.

``Scene`` and ``World`` next door browse places you walk around in. This one
browses the little lit stages an interface puts a model on -- CharInfo (the
character screen), CharFormation, WeaponInfo, the dialog stages -- and loads one
whole: its own sun, its own ambient, what its own volumes blend to (the character
lighting and the post-processing switches), and its art.

Which stages there are and what each states is the hook's answer
(``endfield.ui.stages`` / ``endfield.ui.stage``): it finds them among the game's
own assets and resolves every value -- a light, the ambient, an engine global its
volumes state, a seed of the stage's art -- so a version that ships another stage grows
another row here with no code change, and nothing here reads an asset.

What this module does is put that answer into the shared statement
(:mod:`Kernel.app.staging`). Writing it is the host's: a sun, an ambient and a
scene camera are things an application either has or has not, and this side never
learns which. Nothing here imports a host.
"""

from __future__ import annotations

from ...Kernel import host as host_port
from ...Kernel.app import browser as app_browser
from ...Kernel.app import command
from ...Kernel.app import schemas
from ...Kernel.app.state import Field, Schema
from ...Kernel.app import state as app_state
from ...Kernel.app import view as app_view
from ...Kernel.bridge import cabmap_state
from . import datasets

STATE = "ruri_endfield_ui_scene"

#: What a stated row is, in the dataset's own words.
ENVIRONMENT = "env"
VOLUME = "volume"
PREFAB = "prefab"


def state_of(context):
    return host_port.current().panel_state(context, STATE)


#: This tab's live view and the seats that draw it.
BOUND = app_view.Bound("Endfield:uistage", rules="")

UI_SCENE_STATE = Schema("EndfieldUIScene", """The display-stage browser's state.""", (
    Field("search", app_state.STRING, "", "Filter", "Filter by stage or folder name",
          update="on_search", live=True),
    Field("rows", app_state.COLLECTION, element=app_view.VIEW_ROW),
    Field("active_index", app_state.INT, 0),
    Field("import_art", app_state.BOOL, True, "Stage Prefab",
          "Import the stage's own prefab -- its floor, sky sphere, shadow plane and "
          "cameras -- into its own collection, and look through the camera the game "
          "looks through"),
    Field("apply_environment", app_state.BOOL, True, "Sun + Ambient",
          "Build the stage's directional light and set the world colour from its own "
          "sky SH"),
    Field("exposure_ev", app_state.FLOAT, 0.0, "Exposure",
          "Stops applied to everything this stage lights -- the sun AND the sky ambient "
          "together, so the balance the asset states is preserved. 0 is the asset's own "
          "values, unscaled. This control exists because the game sets its absolute level "
          "at RUNTIME by metering the frame (HGAutoExposure); no field in the asset pins "
          "it, so there is nothing to read and nothing honest to guess",
          soft_minimum=-8.0, soft_maximum=8.0),
    Field("apply_volume", app_state.BOOL, True, "Volume",
          "Write what the stage's own volumes blend to -- the character lighting and the "
          "post-processing switches -- onto the scene's world, the way a level's globals are "
          "written, for every shading stack of this game to read"),
    Field("reset_scene", app_state.BOOL, False, "Reset Scene",
          "Empty the document first. Off by default: a stage is normally loaded AROUND "
          "a character that is already here"),
    Field("status", app_state.STRING, "Refresh to read the game's UI display stages."),
), include=(schemas.LOADING_STATE,))


def _on_search(state, context):
    rebuild(state)


HANDLERS = app_state.Handlers("Endfield.ui_scene", on_search=_on_search)


def rebuild(state, table=None):
    """Ask the kernel for the list as the search box now reads it. The filter, the ordering
    and the screen sections all happen there, over the very table the hook built."""
    BOUND.open(BOUND.table if table is None else table, state)


# ---------------------------------------------------------------------------
# One stage as the shared statement
# ---------------------------------------------------------------------------
def _value(row):
    """One stated value: a number for a single component, the components' numbers otherwise."""
    components = row["components"]
    width = 1 if len(components) == 1 else len(components)
    numbers = tuple(float(row[axis]) for axis in "xyzw"[:width])
    return numbers[0] if width == 1 else numbers


def statement(state, entry):
    """One stage as the shared statement -- what the host is handed."""
    rows = datasets.ui_stage(entry.key)
    return {
        "label": entry.label,
        "exposure": float(state.exposure_ev) if state.apply_environment else 0.0,
        "environment": ([(row["target"], _value(row)) for row in rows if row["kind"] == ENVIRONMENT]
                        if state.apply_environment else []),
        "volume": ({row["target"]: tuple(float(row[axis]) for axis in "xyzw")
                    for row in rows if row["kind"] == VOLUME}
                   if state.apply_volume else {}),
        "prefabs": [row["seed"] for row in rows if row["kind"] == PREFAB] if state.import_art else [],
    }


# ---------------------------------------------------------------------------
# What the buttons do
# ---------------------------------------------------------------------------
def _loaded(context):
    return app_browser.state_of(context).loaded and cabmap_state.BRIDGE is not None


def _has_selection(context):
    return _loaded(context) and BOUND.picked(state_of(context)) is not None


def _refresh(context, arguments):
    """Read the game's UI display stages."""
    state = state_of(context)
    try:
        rebuild(state, datasets.ui_stages())
    except Exception as exc:
        state.status = "{0}: {1}".format(type(exc).__name__, exc)
        return {"CANCELLED"}
    state.status = BOUND.summary
    return None


def _load(context, arguments):
    """Put the selected display stage into the document."""
    state = state_of(context)
    entry = BOUND.picked(state)
    if entry is None:
        state.status = "Nothing selected."
        return
    host = host_port.current()
    if state.reset_scene and host_port.SceneGraph in host.capabilities:
        host.clear_scene(context)
    options = app_browser.as_options(app_browser.state_of(context))
    stated = yield command.Read(lambda: statement(state, entry), 0.4)
    yield command.Mark(0.6)
    lines = host.load_display_stage(context, stated, options)
    state.status = "{0}: {1}".format(stated["label"], "; ".join(lines) if lines else "nothing to apply")


REFRESH = command.COMMANDS.define(
    "ruri.ui_scene_refresh", "Refresh", _refresh,
    description="Read the game's UI display stages",
    icon="FILE_REFRESH", internal=True, poll=_loaded)
LOAD = command.COMMANDS.define(
    "ruri.ui_scene_load", "Load Stage", _load,
    description="Put the selected display stage into the scene",
    icon="IMPORT", requires=host_port.SceneGraph, poll=_has_selection, steps=True,
    status_state=STATE, failure="Loading this display stage failed")


_COLUMNS = (BOUND.column("", icon="LIGHT_AREA"),)
_GROUP_COLUMN = BOUND.column("", icon="FILE_FOLDER")


def draw_ui_scene_tab(layout, context):
    """The UI display stages: pick one, load it around whatever is already here."""
    state = state_of(context)
    command.draw_progress(layout, state)

    head = layout.row(align=True)
    head.prop(state, "search", text="", icon="VIEWZOOM")
    head.operator(REFRESH.id, text="", icon="FILE_REFRESH")

    if BOUND.view is None:
        layout.label(text=state.status, icon="INFO")
        layout.operator(REFRESH.id, icon="FILE_REFRESH")
        return

    app_view.draw_list(BOUND, layout, state, _COLUMNS, "endfield_ui_scenes",
                       group_column=_GROUP_COLUMN)
    if state.status:
        layout.label(text=state.status, icon="INFO")

    options = layout.column(align=True)
    options.enabled = BOUND.picked(state) is not None
    # 与 Scene/World 同一份导入选项 —— 画在按 Load 的地方。
    app_browser.draw_import_options(options, context)
    options.separator()
    options.prop(state, "apply_environment")
    exposure = options.row()
    exposure.enabled = state.apply_environment
    exposure.prop(state, "exposure_ev")
    options.prop(state, "apply_volume")
    options.prop(state, "import_art")
    options.prop(state, "reset_scene")
    options.operator(LOAD.id, icon="IMPORT")


def register():
    host_port.current().register_state(STATE, UI_SCENE_STATE, HANDLERS)


def unregister():
    host_port.current().unregister_state(STATE)
    BOUND.close()
