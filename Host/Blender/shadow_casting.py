"""Which objects throw which shadows, as their renderers state it.

A renderer states how it draws into shadow maps (Unity's ShadowCastingMode), and a
streamed renderer also whether that shadow falls in the directional light's
cascades. Shadows-only is object visibility. The cascades have no per-object
switch here: an object blocks a light or it does not, per light, and that is
light linking. The objects that cast for local lights only are gathered in one
collection, each excluded, and that collection is the blocker set of every
directional light -- the shading stacks light each of them as their main light --
and an exclude-only set leaves every other object blocking it.
"""

from __future__ import annotations

import bpy

MAIN_LIGHT_EXCLUSIONS = "Ruri Main Light Shadow Exclusions"


def shadow_only(obj):
    """Seen by shadow rays and nothing else: no camera, reflection, refraction,
    medium or light probe."""
    obj.visible_camera = False
    obj.visible_diffuse = False
    obj.visible_glossy = False
    obj.visible_transmission = False
    obj.visible_volume_scatter = False
    obj.hide_probe_volume = True
    obj.hide_probe_sphere = True
    obj.hide_probe_plane = True


def exclude_from_main_light(obj):
    """Keep ``obj`` from blocking the directional lights while it blocks every other one."""
    collection = bpy.data.collections.get(MAIN_LIGHT_EXCLUSIONS)
    if collection is None:
        collection = bpy.data.collections.new(MAIN_LIGHT_EXCLUSIONS)
    if collection.objects.get(obj.name) is obj:
        return
    collection.objects.link(obj)
    # A link appends: the entry just made is the last one, and it starts included --
    # an include in a blocker set would make it one of the ONLY blockers.
    collection.collection_objects[len(collection.collection_objects) - 1].light_linking.link_state = "EXCLUDE"


def bind_directional_lights(scene):
    """Make the exclusion set the blocker set of every directional light in ``scene`` that has none
    yet; a light the user gave a blocker set of their own keeps it. Returns how many were bound."""
    collection = bpy.data.collections.get(MAIN_LIGHT_EXCLUSIONS)
    if collection is None:
        return 0
    bound = 0
    for obj in scene.objects:
        if obj.type != "LIGHT" or obj.data.type != "SUN" or obj.library is not None:
            continue
        if obj.light_linking.blocker_collection is None:
            obj.light_linking.blocker_collection = collection
            bound += 1
    return bound
