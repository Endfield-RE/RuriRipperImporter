"""Put one of the game's UI display stages into the Blender scene.

Three things arrive, each straight out of the stage's own assets and none of them
invented here:

``HGEnvironmentPhase``   the sun -- direction, colour temperature, and the
                         PRE-DIVIDED intensity its own shaders are handed
                         (``directIntensityDividePi``; see ``_write_light``),
                         plus the sky's own ambient SH as the world colour.
``HGCharacterVolume``    the character-lighting overrides, pushed onto every
                         Endfield uber material in the scene as its
                         ``_CharacterParams*`` inputs (see BINDINGS -- which
                         volume field lands in which slot is read off how the
                         game's own shader uses that component).
``stage prefab``         the stage itself, loaded through the kernel's one load:
                         floor, sky sphere, cameras, hierarchy 1:1.

Only parameters the volume actually OVERRIDES are pushed: an unticked row in the
game's inspector contributes nothing, and writing its m_Value anyway would dress
a stale default up as a setting.
"""

from __future__ import annotations

import bpy
import numpy
from mathutils import Vector

from . import coordinate, derived_state, material_panel, materialise
from ...Kernel.app import loading, staging

MAIN_CAMERA_TAG = "MainCamera"

#: Where each target the game resolved gets written. The names are the shared
#: ones (``Kernel.app.staging``); which FIELD of which asset produced a value is
#: the game's answer and never reaches here.
LIGHT_DIRECTION = staging.LIGHT_DIRECTION
LIGHT_ENERGY = staging.LIGHT_ENERGY
LIGHT_ANGLE = staging.LIGHT_ANGLE
LIGHT_COLOR = staging.LIGHT_COLOR
LIGHT_SHADOWS = staging.LIGHT_SHADOWS
LIGHT_VOLUME = staging.LIGHT_VOLUME
WORLD_COLOR = staging.WORLD_COLOR

_XYZ = {"x": 0, "y": 1, "z": 2}


def apply_environment(context, pairs, name="Endfield Sun", exposure_ev=0.0):
    """Build/replace the stage's sun and world from the pairs the game resolved,
    one target at a time. Nothing here knows which field of which asset meant
    what -- only how to write a Blender light and a world.

    ``exposure_ev`` is stops, applied as ONE factor to every radiance the stage
    states -- the sun's energy and the sky's ambient alike -- so the balance
    between them stays exactly as authored. 0 writes the asset's own numbers.
    It is a control rather than a read value because the game's absolute level
    is produced at runtime by metering the rendered frame (HGAutoExposure); the
    asset fixes the RATIOS and nothing else, and inventing a factor to stand in
    for the missing level would be a number this add-on made up."""
    scale = 2.0 ** float(exposure_ev)
    sun = None
    for target, value in pairs:
        if target == WORLD_COLOR:
            _world(context, value, scale)
            continue
        sun = sun or _sun(context, name)
        _write_light(sun, target, value, scale)
    if sun is not None:
        derived_state.announce(sun)
    return sun


def _sun(context, name):
    """The stage's directional light, built once and reused."""
    data = bpy.data.lights.get(name)
    if data is None or data.type != "SUN":
        data = bpy.data.lights.new(name, type="SUN")
        data.name = name
    obj = bpy.data.objects.get(name)
    if obj is None or obj.data is not data:
        obj = bpy.data.objects.new(name, data)
        context.collection.objects.link(obj)
    elif obj.name not in context.scene.objects:
        context.collection.objects.link(obj)
    return obj


def _write_light(obj, target, value, scale):
    """One binding onto the sun.

    A direction is the direction the light TRAVELS, already resolved by the game
    from its pitch/yaw; Blender's sun shines down its own -Z, so the object
    simply tracks that vector.

    Energy goes in unchanged, and what arrives is the game's own
    ``directIntensityDividePi`` rather than its ``directIntensity`` -- because
    what READS this light is not Blender's own shading but the ported game
    shader (its ``mainLight.color`` capability is fulfilled with
    ``data.color * data.energy``), and the quantity that shader is handed in
    game is ``directColor * directIntensityDividePi``. Feeding it the undivided
    intensity is pi times too much light, which on a tone-mapped stage reads as
    a blown-white frame. The Lambert 1/pi is therefore accounted for exactly
    once, on the side that authored it.

    The colour arrives as the game emits it, linear and per unit of that energy:
    a temperature is the game's own curve, folded in before it gets here, never
    Blender's blackbody."""
    data = obj.data
    if target == LIGHT_DIRECTION:
        unity = numpy.array([value], dtype=numpy.float32)
        converted = coordinate.convert_points(unity)[0]
        direction = coordinate.root_matrix().to_3x3() @ Vector(
            (float(converted[0]), float(converted[1]), float(converted[2])))
        if direction.length > 1e-6:
            obj.rotation_mode = "QUATERNION"
            obj.rotation_quaternion = direction.to_track_quat("-Z", "Y")
    elif target == LIGHT_ENERGY:
        data.energy = value * scale
    elif target == LIGHT_ANGLE:
        data.angle = 2.0 * value
    elif target == LIGHT_COLOR:
        data.color = value
    elif target == LIGHT_SHADOWS:
        data.use_shadow = value > 0.5
    elif target == LIGHT_VOLUME:
        data.volume_factor = value


def _world(context, ambient, scale):
    """The stage's ambient: the DC term of its own baked sky SH per channel, as the game
    resolved it. Scaled by the same stops as the sun -- an exposure that moved one and not
    the other would change the balance the asset authored."""
    channels = [channel * scale for channel in ambient]
    world = context.scene.world
    if world is None:
        world = bpy.data.worlds.new("Endfield UI Stage")
        context.scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    if background is not None:
        background.inputs[0].default_value = (channels[0], channels[1], channels[2], 1.0)
    return world


def apply_character_params(pushed, materials=None):
    """Push the (slot, components, value) triples the game resolved onto every
    material of its own shading stack that is loaded.

    Returns (materials touched, parameters written)."""
    if not pushed:
        return 0, 0

    touched = written = 0
    for material in (materials if materials is not None else bpy.data.materials):
        entry = material_panel.stack_of(material)
        if entry is None:
            continue
        stack = entry["stack"]
        # 布局表住生成栈的清单里，经它自己的 part() 取；曾经写成 getattr(stack, "PARAMS", {})，
        # 而生成物从来没有过这个属性 —— 于是每张材质的 rows 恒为空，整个函数**静默一个 CP 都不写**
        # （零报错、零日志、画面纹丝不动）。
        try:
            params = stack.part(material.get("ruri_uber_part", ""))["params"]
        except (KeyError, TypeError):
            continue
        rows = {row[0]: row for row in params}
        colors = {key: list(value) for key, value
                  in dict(material.get("ruri_uber_colors") or {}).items()}
        hits = 0
        for slot, comps, value in pushed:
            name = "_CharacterParams{0}".format(slot)
            row = rows.get(name)
            if row is None:
                continue        # 这个 part 不吃这枚 CP —— 是常态,不是错
            current = colors.get(name)
            if current is None:
                # 快照里没有 = 还停在声明缺省。必须从**声明缺省**起手补齐四分量,
                # 否则只推 x 的绑定会把 yzw 一并清零。
                current = [float(row[2][0]), float(row[2][1]), float(row[2][2]), float(row[3])]
            current = [float(component) for component in current][:4]
            current += [0.0] * (4 - len(current))
            if _write_slot(current, comps, value):
                colors[name] = current
                hits += 1
        if hits:
            # 快照是参数唯一真源:写记录,再由栈把记录写成组输入的常量(sRGB 线性化与各段各循环体的口都在那一处)。
            material["ruri_uber_colors"] = colors
            stack.apply_params(material)
            touched += 1
            written += hits
    return touched, written


def _write_slot(current, comps, value):
    """Write one volume value into one CP slot's four components, in place: a tuple fills
    the components it names, a number the one component it names. Returns whether
    anything was written."""
    if comps in ("rgb", "xyzw"):
        current[:len(value)] = value
        return True
    if comps == "w":
        current[3] = value
        return True
    index = _XYZ.get(comps)
    if index is None:
        return False
    current[index] = value
    return True


def adopt_camera(context, cameras):
    """Make the stage's own camera the scene camera, so numpad-0 looks through
    what the game looks through. The render aspect follows: a vertical FOV only
    frames the same picture at the same aspect ratio.

    Which of a stage's cameras that is comes off Unity's own ``MainCamera`` tag,
    which the prefab states on exactly the one the game renders through; the
    rest are cinemachine rigs and per-body-type framing helpers. Falling back to
    "the first visible one" would be a guess, so it only happens when the prefab
    tags nothing."""
    if not cameras:
        return None
    tagged = [obj for obj in cameras if obj.get(materialise.TAG) == MAIN_CAMERA_TAG]
    visible = [obj for obj in cameras if not obj.hide_viewport] or list(cameras)
    chosen = tagged[0] if tagged else visible[0]
    context.scene.camera = chosen
    render = context.scene.render
    if render.resolution_x * 9 != render.resolution_y * 16:
        render.resolution_x, render.resolution_y = 1920, 1080
    return chosen


# ---------------------------------------------------------------------------
# The one entry the port names
# ---------------------------------------------------------------------------
def load(context, stage, options):
    """Write one stated display stage into this scene, and say what was written.

    The four halves are independent on purpose: a stage whose art is not wanted
    still lights the character, and a stage the install ships no prefab for still
    has a sun. What each of them IS came off the statement; none of it is read
    here."""
    done = []
    if stage["environment"]:
        sun = apply_environment(context, stage["environment"], stage["label"] + " Sun",
                                stage["exposure"])
        done.append("sun " + (sun.name if sun else "(no direction in the asset)"))
    if stage["character_params"]:
        touched, written = apply_character_params(stage["character_params"])
        done.append("{0} param(s) onto {1} material(s)".format(written, touched))
    if stage["prefabs"]:
        done.extend(_load_art(context, stage["prefabs"], options))
    return done


def _load_art(context, prefabs, options):
    """The stage's own prefab, loaded the ordinary way: its paths are its seeds."""
    seeds = [path for path in prefabs if path]
    if not seeds:
        return ["this stage names no art to build"]
    before = set(bpy.data.objects)
    built = loading.load(context, seeds, options)
    placed = [obj for obj in bpy.data.objects if obj not in before]
    meshes = len([obj for obj in placed if obj.type == "MESH"])
    cameras = [obj for obj in placed if obj.type == "CAMERA"]
    done = ["{0} mesh(es), {1} camera(s)".format(meshes, len(cameras))] + built.warnings[:3]
    chosen = adopt_camera(context, cameras)
    if chosen is not None:
        done.append("looking through " + chosen.name)
    return done
