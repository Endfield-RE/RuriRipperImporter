"""A material a file links from a library is drawn through a twin compiled in this session.

A library's material carries its record, and the record is content of the library file. The graph a stack
compiles from a record is plugin data (see :mod:`plugin_data`), and a linked material can hold nothing this
session writes: a file never writes the data it links. So a stack compiles the linked record into a twin that
is runtime data, and every user the session draws through is pointed at it:

- users inside linked data (the meshes of a level linked into a shot) take the twin directly; linked data is
  never written, so nothing more is owed;
- local users (a character's override mesh, a local object) are moved with ``user_remap``. They ARE written,
  so for the length of every save they go back to the library's material and come forward again after it:
  the file keeps saying what it links, never a twin that is not in it.

The load pass hands every user back before it drops plugin data (the twins with it), so reloading the stacks
finds the file as saved and compiles the twins anew. A file being opened frees the previous one whole; its
pairs are simply forgotten."""

from __future__ import annotations

import bpy

_PAIRS = []
_HELD = []


def _alive(pair):
    try:
        return bool(pair[0].name) and bool(pair[1].name)
    except ReferenceError:
        return False


def twinned(original):
    """Whether this session already draws ``original`` (a linked material) through a twin."""
    return any(_alive(pair) and pair[0] == original for pair in _PAIRS)


def _repoint_linked(user, current, wanted):
    """Point a linked datablock's slots that hold ``current`` at ``wanted``. A kind of user that keeps a
    material anywhere else (a node socket, a grease pencil layer) is named: it keeps drawing ``current``."""
    moved = 0
    if isinstance(user, bpy.types.Object):
        for slot in user.material_slots:
            if slot.link == 'OBJECT' and slot.material == current:
                slot.material = wanted
                moved += 1
    else:
        materials = getattr(user, "materials", None)
        if materials is not None:
            for index, material in enumerate(materials):
                if material == current:
                    materials[index] = wanted
                    moved += 1
    if not moved:
        print("[linked-twins] !! {0} {1} keeps {2}: it holds the material outside a material slot".format(
            type(user).__name__, user.name_full, current.name_full), flush=True)
    return moved


def adopt(pairs):
    """``pairs`` of (linked material, its compiled twin): every user now draws the twin. Returns the linked
    slots repointed (local users move with ``user_remap``, which reports no count)."""
    if not pairs:
        return 0
    users = bpy.data.user_map(subset=[original for original, _twin in pairs])
    moved = 0
    for original, twin in pairs:
        for user in users.get(original, ()):
            if user.library is not None:
                moved += _repoint_linked(user, original, twin)
        original.user_remap(twin)
        _PAIRS.append((original, twin))
    return moved


def release():
    """Hand every user back to its linked material and forget the twins. The load pass calls this before it
    drops plugin data; pairs whose datablocks are already freed (a file was opened) are only forgotten."""
    live = [pair for pair in _PAIRS if _alive(pair)]
    if live:
        users = bpy.data.user_map(subset=[twin for _original, twin in live])
        for original, twin in live:
            for user in users.get(twin, ()):
                if user.library is not None:
                    _repoint_linked(user, twin, original)
            twin.user_remap(original)
    del _PAIRS[:]
    del _HELD[:]


@bpy.app.handlers.persistent
def _before_save(*_args):
    live = [pair for pair in _PAIRS if _alive(pair)]
    if not live:
        return
    users = bpy.data.user_map(subset=[twin for _original, twin in live])
    for original, twin in live:
        if any(user.library is None for user in users.get(twin, ())):
            twin.user_remap(original)
            _HELD.append((original, twin))


@bpy.app.handlers.persistent
def _after_save(*_args):
    for original, twin in _HELD:
        if _alive((original, twin)):
            original.user_remap(twin)
    del _HELD[:]


_HANDLERS = (("save_pre", _before_save), ("save_post", _after_save), ("save_post_fail", _after_save))


def register():
    for chain_name, handler in _HANDLERS:
        chain = getattr(bpy.app.handlers, chain_name)
        if handler not in chain:
            chain.append(handler)


def unregister():
    for chain_name, handler in _HANDLERS:
        chain = getattr(bpy.app.handlers, chain_name)
        if handler in chain:
            chain.remove(handler)
