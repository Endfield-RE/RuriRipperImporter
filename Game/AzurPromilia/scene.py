"""Every scene the install carries, under the folder tree the game files it in.

A row says whether the BUILT scene file is present: this title rarely ships the built ``.unity``
with its packages, so most scenes arrive as terrain, materials and colliders only. A row without
one is dimmed rather than hidden -- its resources are real and loading them is a real act, it just
is not the scene itself.

A row's payload is its seed -- the built scene file, else the folder its resources are filed
under -- so Load and Reveal are the kernel's verbs over it, and this tab needs nothing of the host
the browser does not already need.

Nothing here imports a host.
"""

from __future__ import annotations

from ...Kernel import host as host_port
from ...Kernel.app import browser as app_browser
from ...Kernel.app import cast_panel, command, filtering
from ...Kernel.app import layout as app_layout
from ...Kernel.app import schemas
from ...Kernel.app.state import Field, Schema
from ...Kernel.app import state as app_state
from ...Kernel.app import view as app_view
from ...Kernel.bridge import cabmap_state
from . import datasets

STATE = "ruri_azurpromilia_scene"
SPEC_KEY = "AzurPromilia:scene"

BOUND = app_view.Bound(SPEC_KEY)
_TABLE = {}


def state_of(context):
    return host_port.current().panel_state(context, STATE)


SCENE = Schema("AzurPromiliaScene", """The scene browser's whole state.""", (
    Field("search", app_state.STRING, "", "Filter",
          "Filter by scene name or folder",
          update="on_filter_edit", live=True),
    Field("rows", app_state.COLLECTION, element=app_view.VIEW_ROW),
    Field("active_index", app_state.INT, 0),
    Field("status", app_state.STRING, "Load a cabmap, then refresh the scene list."),
    Field("built_only", app_state.BOOL, False, "Built only",
          "Hide the scenes this install carries resources for but no built scene file"),
), include=(schemas.FILTER_STATE, schemas.LOADING_STATE))


def _on_filter_edit(state, context):
    rebuild(state)


HANDLERS = app_state.Handlers(
    "AzurPromilia.scene", base=filtering.HANDLERS, on_filter_edit=_on_filter_edit)


FILTER_SPEC = filtering.register_spec(filtering.FilterSpec(
    key=SPEC_KEY, fields=BOUND.fields,
    state_for=state_of,
    apply=lambda context: rebuild(state_of(context))))


def rebuild(state):
    """Ask the kernel for the drawn list as it is now stated. The search text, the rules, the
    sections and the truncation are all answered on the other side."""
    with filtering.rebuilding():
        BOUND.open(_TABLE.get("scenes"), state)


# ---------------------------------------------------------------------------
# What the buttons do
# ---------------------------------------------------------------------------
def _loaded(context):
    return app_browser.state_of(context).loaded and cabmap_state.BRIDGE is not None


def _refresh(context, arguments):
    """Read every scene the install carries."""
    state = state_of(context)
    try:
        _TABLE["scenes"] = datasets.scenes()
    except Exception as exc:
        state.status = "{0}: {1}".format(type(exc).__name__, exc)
        return {"CANCELLED"}
    rebuild(state)
    return None


REFRESH = command.COMMANDS.define(
    "ruri.azurpromilia_scene_refresh", "Refresh Scenes", _refresh,
    description="Read the scene list off the install's own folder tree",
    icon="FILE_REFRESH", poll=_loaded)


#: A scene row. Filtering already happened against the table's own fields, so no row is hidden at
#: draw time.
_COLUMNS = (
    BOUND.column("", width=0.7, icon="SCENE_DATA"),
    BOUND.column("detail", align=app_layout.RIGHT, enabled=False),
)
_GROUP_COLUMN = BOUND.column("", icon="OUTLINER_COLLECTION")


def draw(layout, context):
    state = state_of(context)

    command.draw_progress(layout, state)
    head = layout.row(align=True)
    head.label(text="Scenes", icon="SCENE_DATA")
    head.operator(REFRESH.id, text="", icon="FILE_REFRESH")

    filtering.draw_search_row(layout, state)
    app_view.draw_list(BOUND, layout, state, _COLUMNS, "azurpromilia_scenes",
                       group_column=_GROUP_COLUMN)

    options = layout.column(align=True)
    app_browser.draw_import_options(options, context)
    actions = options.column(align=True)
    entry = BOUND.picked(state)
    actions.enabled = entry is not None
    cast_panel.draw_row_verbs(actions, [entry.payload] if entry is not None and entry.payload else [],
                              STATE)


def register():
    host_port.current().register_state(
        STATE, SCENE, HANDLERS, extra={"FILTER_SPEC_KEY": SPEC_KEY})


def unregister():
    host_port.current().unregister_state(STATE)
    BOUND.close()
    _TABLE.clear()
