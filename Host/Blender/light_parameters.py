"""What a stated light carries into the shading stacks beyond what the host's own light hands a light loop, stamped
once on the Blender light a statement made -- its content, like its colour.

Three things, all LIGHT attributes the stacks' one light template reads:

* the source's camera-distance fade, as four coefficients under :data:`material_builder.LIGHT_FADE_PROPERTY` -- every
  stack's template scales the light by it, the way the source's light list does for every one of its shaders;
* the source's own per-light parameter vectors (culling box, tube length, cookie rect, ...) for a stack that lights
  through the source's own light model, under the names that stack declares
  (:data:`material_builder.LIGHT_PARAMETERS`), in the order the statement states them;
* the light's world orientation under :data:`material_builder.LIGHT_FRAME_PROPERTY`, which the source's tube, fog
  and cookie lighting turn on and the host's light loop does not hand over -- stamped as placed, like the culling box
  beside it, so turning a light after the import does not turn its tube or its cookie.

A vector of zeros is not stamped: an attribute a light does not carry reads zero anyway (the stacks encode a plain
light as zeros), and every property on a light lengthens the search each of its attribute reads makes.
"""

from __future__ import annotations

from . import material_builder


def attribute_names():
    """The parameter attribute names in statement order, as every loaded stack that reads parameters states them.
    Stacks reading none are not counted; two stacks reading different layouts cannot share one light and are
    refused."""
    layouts = {tuple(provider()) for provider in material_builder.LIGHT_PARAMETERS}
    layouts.discard(())
    if len(layouts) > 1:
        raise RuntimeError(
            "[light-parameters] the loaded shading stacks read different light parameters {0}; they come from "
            "different generator builds -- redeploy the stale ones".format(sorted(layouts)))
    return list(next(iter(layouts))) if layouts else []


def stamp(light, stated):
    """Stamp a stated light's fade coefficients and parameter vectors onto its Blender light data ``light``."""
    fade = [float(value) for value in stated["fade"]]
    if any(fade):
        light[material_builder.LIGHT_FADE_PROPERTY] = fade
    vectors = stated["parameters"]
    if len(vectors) == 0:
        return
    names = attribute_names()
    if len(vectors) != len(names):
        raise ValueError("[light-parameters] light {0} states {1} parameter vectors; the stacks read {2}".format(
            light.name, len(vectors), len(names)))
    for name, vector in zip(names, vectors):
        values = [float(value) for value in vector]
        if any(values):
            light[name] = values


def stamp_frame(obj, world):
    """Stamp a stated light's world orientation onto its Blender object ``obj`` placed at the world matrix ``world``:
    the (x, y, z) of the world rotation quaternion with w >= 0. An unturned light carries none."""
    rotation = world.to_3x3().normalized().to_quaternion()
    if rotation.w < 0.0:
        rotation.negate()
    frame = [rotation.x, rotation.y, rotation.z]
    if any(frame):
        obj[material_builder.LIGHT_FRAME_PROPERTY] = frame
