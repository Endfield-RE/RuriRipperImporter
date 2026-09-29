"""The renderer a level is shaded under.

The generated shading stacks are verified in a scene whose renderer is EEVEE with every one of its own
settings at the renderer's defaults, whose view applies no exposure, gamma, curve or white balance of its
own, and whose compositor runs on the GPU the display chain is authored for -- the chain itself does the tone
mapping and puts the display transform it needs in place when it installs. A level imported into a startup
scene saved with other settings (a horizon-scan thickness, ray-tracing thicknesses, a CPU compositor) would
be shaded under a configuration none of the stacks was verified under, and look it. So a level import puts
the renderer back first; what the level itself states for it -- its medium's integration, its shadow pool --
is applied on top afterwards.
"""

from __future__ import annotations

import bpy

ENGINE = "BLENDER_EEVEE"
COMPOSITOR_DEVICE = "GPU"
#: The view's own adjustments, each put back to its default; the transform and look are the display chain's.
VIEW_ADJUSTMENTS = ("exposure", "gamma", "use_curve_mapping", "use_white_balance")


def apply(scene):
    """Put ``scene``'s renderer in the configuration the stacks are verified under."""
    scene.render.engine = ENGINE
    _to_defaults(scene.eevee)
    view = scene.view_settings
    for name in VIEW_ADJUSTMENTS:
        _set_default(view, view.bl_rna.properties[name])
    scene.render.compositor_device = COMPOSITOR_DEVICE


def _to_defaults(struct):
    """Every writable setting of ``struct`` and of the settings structs it holds, at its RNA default."""
    for prop in struct.bl_rna.properties:
        if prop.identifier == "rna_type" or prop.type == "COLLECTION":
            continue
        if prop.type == "POINTER":
            held = getattr(struct, prop.identifier)
            if held is not None and not isinstance(held, bpy.types.ID):
                _to_defaults(held)
            continue
        if not prop.is_readonly:
            _set_default(struct, prop)


def _set_default(struct, prop):
    if prop.type == "ENUM":
        setattr(struct, prop.identifier, prop.default_flag if prop.is_enum_flag else prop.default)
    elif getattr(prop, "array_length", 0) > 0:
        setattr(struct, prop.identifier, prop.default_array)
    else:
        setattr(struct, prop.identifier, prop.default)
