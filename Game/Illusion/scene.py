"""Browse the game's places the way it lists them, and import one.

One list, because the game has one set of places under two names: every one is a
Unity level, and picking one and importing it is the whole interaction -- nothing
here is streamed, so there is no window to choose.

The list itself comes from the game's hook (the ``scene.places`` dataset) and the
filtering runs on the same C# engine the bundle browser uses, over that dataset's
own handle. A row's payload is its seed, so importing and revealing it are the
kernel's own verbs; nothing on this side reads a byte of the game, and nothing here
imports a host.
"""

from __future__ import annotations

from ...Kernel import host as host_port
from ...Kernel.app import browser as app_browser
from ...Kernel.app import cast_panel, command, filtering
from ...Kernel.app import schemas
from ...Kernel.app.state import Field, Schema
from ...Kernel.app import state as app_state
from ...Kernel.app import view as app_view
from ...Kernel.bridge import cabmap_state
from . import datasets

STATE = "ruri_kk_scene"
SPEC_KEY = "Illusion:scene"

def state_of(context):
    return host_port.current().panel_state(context, STATE)


#: This tab's live view and the seats that draw it. Which column is the name, the
#: id or the family is each column's own statement, made where the hook builds the
#: place table.
BOUND = app_view.Bound(SPEC_KEY)

SCENE = Schema("IllusionScene", """The place browser's whole state.""", (
    Field("search", app_state.STRING, "", "Filter",
          "Filter by displayed name or bundle",
          update="on_filter_edit", live=True),
    Field("rows", app_state.COLLECTION, element=app_view.VIEW_ROW),
    Field("active_index", app_state.INT, 0),
    Field("status", app_state.STRING, "Refresh to read the game's scene list."),
    Field("reset_scene", app_state.BOOL, True, "Reset Scene",
          "Delete existing scene objects before importing"),
), include=(schemas.FILTER_STATE, schemas.LOADING_STATE))


def _on_filter_edit(state, context):
    rebuild(state)


HANDLERS = app_state.Handlers(
    "Illusion.scene", base=filtering.HANDLERS, on_filter_edit=_on_filter_edit)

FILTER_SPEC = filtering.register_spec(filtering.FilterSpec(
    key=SPEC_KEY, fields=BOUND.fields,
    state_for=state_of,
    apply=lambda context: rebuild(state_of(context))))


def selected(state):
    return BOUND.picked(state)


def selected_place(state):
    """Every column of the place the user is on. The drawn line IS the row, so
    there is nothing to look up."""
    entry = BOUND.picked(state)
    return None if entry is None else entry.values()


def rebuild(state):
    """Ask the kernel for the drawn list as it is now stated. Nothing is matched,
    sorted, grouped or counted here."""
    with filtering.rebuilding():
        table = datasets.table(datasets.PLACES)
        if table is None:
            state.status = datasets.why_empty(datasets.PLACES) or "Load a cabmap, then refresh."
        BOUND.open(table, state)


# ---------------------------------------------------------------------------
# What the buttons do
# ---------------------------------------------------------------------------
def _loaded(context):
    return app_browser.state_of(context).loaded and cabmap_state.BRIDGE is not None


def _refresh(context, arguments):
    """Read every place the game names, out of its own tables."""
    state = state_of(context)
    try:
        datasets.table(datasets.PLACES, refresh=True)
    except Exception as exc:
        state.status = "{0}: {1}".format(type(exc).__name__, exc)
        return {"CANCELLED"}
    rebuild(state)
    return None


REFRESH = command.COMMANDS.define(
    "ruri.kk_scene_refresh", "Refresh Scenes", _refresh,
    description="Read every place the game names, out of its own tables",
    icon="FILE_REFRESH", poll=_loaded)


_COLUMNS = (BOUND.column("", icon="WORLD"),)
_GROUP_COLUMN = BOUND.column("", icon="OUTLINER_COLLECTION")


def draw(layout, context):
    state = state_of(context)

    command.draw_progress(layout, state)
    filtering.draw_search_row(layout, state, extra_operator=(REFRESH.id, "FILE_REFRESH"))
    app_view.draw_list(BOUND, layout, state, _COLUMNS, "illusion_places",
                       group_column=_GROUP_COLUMN)
    layout.label(text=state.status, icon="INFO")

    place = selected_place(state)
    entry = selected(state)
    actions = layout.column(align=True)
    actions.enabled = place is not None
    if place is not None:
        info = actions.box()
        info.label(text="{0}  ->  {1}".format(place["bundle"], place["asset"]))
        info.label(text="named by {0}".format(place["sources"]))
    # 与浏览器同一份导入选项;"清场"只在真有场景图可清的宿主上有意义。
    app_browser.draw_import_options(actions, context)
    scene_graph = host_port.SceneGraph in host_port.current().capabilities
    if scene_graph:
        actions.prop(state, "reset_scene")
    cast_panel.draw_row_verbs(actions, [entry.payload] if entry is not None and entry.payload else [],
                              STATE, reset_scene=scene_graph and state.reset_scene)


def register():
    host_port.current().register_state(
        STATE, SCENE, HANDLERS, extra={"FILTER_SPEC_KEY": SPEC_KEY})


def unregister():
    host_port.current().unregister_state(STATE)
