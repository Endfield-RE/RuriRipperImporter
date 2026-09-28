"""A level's participating medium, as an EEVEE volume the renderer integrates itself.

The source integrates its fog in a grid of froxels and every material reads the integral at
its own depth. EEVEE integrates volume objects in a froxel grid of its own and composites
the result over each surface after the surface's material has run -- so the medium goes in
as a volume object, and the material's own share of the integral is the identity, which is
what the generated stacks fold that query to. A world volume would not do: EEVEE switches
every sun off under a world volume that absorbs.

The medium's extinction is grey: ``density_scale * sum(density * 2^-max(-127, falloff * (y -
height)))`` over the source's own height ``y``, one term per stated layer. It scatters its
albedo times that and absorbs the rest -- a Volume Scatter and a Volume Absorption of one
colour and one density, whose extinctions sum to that density in every channel. What it adds
of the sky and of itself goes in as volume emission: ``max(dot(L1, (g * ray, 1)) *
ambient_scale, 0)`` per channel times the scattering, plus the stated emission. Everything
is scaled by the near fade-in over the distance travelled past the range's start.

The sun it scatters is the level sun itself. The source lights its medium with the main light
along the main light's direction, through the main light's shadow maps, but in the colour the
phase states before decoding it and at the undivided intensity, scaled by the medium's direct
scattering; the level sun carries the decoded colour at the intensity over pi. A second sun
would not do: EEVEE tags shadow pages for every sun at every visible pixel and froxel whatever
its light linking says, and two suns overflow the shadow pool at full resolution, which EEVEE
answers by dropping shadows. EEVEE's volume lighting is linear in the light's colour and in the
medium's scattering colour, so the difference is exact to fold: the level sun takes the volume
share ``I * s * max(k) / E`` (``k`` = stated colour / sun colour per channel, ``E`` its energy),
the medium's scattering and absorption colours become ``albedo * k / max(k)`` -- their
extinctions still sum to the density, every factor stays at most one -- and every lamp copy
takes its colour over ``k / max(k)``, so a lamp scatters exactly what it did before.

A lamp scatters into the medium by the volume factor the statement gave it. The source lights
its medium with its lamps unshadowed (unless the medium says otherwise) and without the
inverse-square singularity: its falloff is ``1 / (d^2 + 1)``. EEVEE's volume falloff for a
sphere light of radius ``r``, ``2 / (d^2 + r^2 + d sqrt(d^2 + r^2))``, tends to
``1 / (d^2 + 0.75 r^2)``, so a copy of radius ``2 / sqrt(3)`` has the source's far field and a
finite centre (half again the source's value there). Each such lamp gets that copy, for the
medium alone, and gives up its own volume share.

The grid is the source's: its slices over ``[start, end]`` with its log2 depth distribution
and one froxel per its pixel tile. The source's slices sit at ``(2^(z/S) - O) / B`` for slice
``z`` of ``Z``; EEVEE's at the same form over ``t = z / (Z - 1)`` with ``S' = 4 (1 -
distribution)``, so ``distribution = 1 - S / (4 (Z - 1))``. EEVEE's own world and probe
lighting of volumes is clamped away (the medium states its sky in-scatter itself), and its
volume self-shadowing is off, as the source's is.
"""

from __future__ import annotations

import math

import bpy
from mathutils import Vector

from . import material_builder

MEDIUM = "Ruri Level Medium"
RECEIVERS = "Ruri Level Medium Receivers"
TWIN_SUFFIX = " (medium)"
#: On a lamp's copy: the lamp it copies.
TWIN_OF = "ruri_medium_twin_of"
#: On a lamp's own light data: the volume share it handed its copy.
HANDED_SHARE = "ruri_medium_share"
#: On the level sun's light data: the volume share the level stated for it, before the medium's.
STATED_SHARE = "ruri_medium_stated_share"
TWIN_RADIUS = 2.0 / math.sqrt(3.0)
#: What EEVEE's indirect volume lighting is clamped to: its SH energy limit, zero excluded.
NO_INDIRECT = 1e-9
TILE_SIZES = ("1", "2", "4", "8", "16")


def apply(context, medium, sun):
    """Stand ``medium`` (see :meth:`Kernel.host.SceneGraph.apply_medium`) up in the scene,
    lit by ``sun`` (the level sun object), replacing whatever medium a previous call stood up.
    Returns the lines to report."""
    scene = context.scene
    withdraw(scene)
    tint = _sun_share(sun, medium)
    domain = _domain(scene, medium, tint)
    receivers = bpy.data.collections.new(RECEIVERS)
    receivers.objects.link(domain)
    copies = _lamp_copies(scene, medium, receivers, tint)
    _integration(scene, medium)
    return ["medium {0}: {1:g}-{2:g} m, {3} lamp(s) in it".format(
        medium["label"], medium["range"][0], medium["range"][1], copies)]


def withdraw(scene):
    """Take a stood-up medium back out: its volume, the lamps' copies, every lamp's volume
    share back where the statement put it and the level sun's back to what the level stated."""
    for obj in list(bpy.data.objects):
        if obj.name == MEDIUM or TWIN_OF in obj:
            data = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if data is not None and data.users == 0:
                if isinstance(data, bpy.types.Light):
                    bpy.data.lights.remove(data)
                elif isinstance(data, bpy.types.Mesh):
                    bpy.data.meshes.remove(data)
    for light in bpy.data.lights:
        for key in (HANDED_SHARE, STATED_SHARE):
            if key in light:
                light.volume_factor = float(light[key])
                del light[key]
    receivers = bpy.data.collections.get(RECEIVERS)
    if receivers is not None:
        bpy.data.collections.remove(receivers)
    material = bpy.data.materials.get(MEDIUM)
    if material is not None and material.users == 0:
        bpy.data.materials.remove(material)
    _ = scene


def _domain(scene, medium, tint):
    """A box around everything in the scene, grown by the medium's range: wherever the view
    stands among the scene, all of the range it integrates is inside."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    corners = [obj.matrix_world @ Vector(corner)
               for obj in (candidate.evaluated_get(depsgraph) for candidate in scene.objects
                           if candidate.type == "MESH")
               for corner in obj.bound_box]
    reach = float(medium["range"][1])
    if corners:
        low = Vector([min(c[i] for c in corners) - reach for i in range(3)])
        high = Vector([max(c[i] for c in corners) + reach for i in range(3)])
    else:
        low, high = Vector((-reach,) * 3), Vector((reach,) * 3)
    mesh = bpy.data.meshes.new(MEDIUM)
    vertices = [(x, y, z) for x in (low.x, high.x) for y in (low.y, high.y) for z in (low.z, high.z)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(_material(medium, tint))
    domain = bpy.data.objects.new(MEDIUM, mesh)
    domain.display_type = "BOUNDS"
    domain.hide_select = True
    scene.collection.objects.link(domain)
    return domain


def _material(medium, tint):
    material = bpy.data.materials.get(MEDIUM) or bpy.data.materials.new(MEDIUM)
    material.use_nodes = True
    tree = material.node_tree
    tree.nodes.clear()
    graph = _Graph(tree)
    basis = material_builder.world_basis()
    column = [tuple(basis[row][axis] for row in range(3)) for axis in range(3)]

    geometry = graph.node("ShaderNodeNewGeometry")
    camera = graph.node("ShaderNodeCameraData")
    height = graph.vector("DOT_PRODUCT", geometry.outputs["Position"], column[1])
    extinction = 0.0
    for layer_height, layer_density, layer_falloff in medium["layers"]:
        exponent = graph.math("MINIMUM", graph.math(
            "MULTIPLY", graph.math("SUBTRACT", float(layer_height), height), float(layer_falloff)), 127.0)
        extinction = graph.math("ADD", extinction, graph.math(
            "MULTIPLY", graph.math("POWER", 2.0, exponent), float(layer_density)))
    extinction = graph.math("MAXIMUM", graph.math("MULTIPLY", extinction, float(medium["density_scale"])), 0.0)

    start = float(medium["range"][0])
    distance = camera.outputs["View Distance"]
    travelled = graph.math("MULTIPLY", distance, graph.math(
        "SUBTRACT", 1.0, graph.math("DIVIDE", start, camera.outputs["View Z Depth"])))
    fade = graph.math("MULTIPLY", travelled, float(medium["near_fade"]), clamp=True)
    extinction = graph.math("MULTIPLY", extinction, fade)

    albedo = tuple(float(component) for component in medium["albedo"])
    anisotropy = float(medium["anisotropy"])
    tinted = tuple(component * share for component, share in zip(albedo, tint))
    scatter = graph.node("ShaderNodeVolumeScatter")
    scatter.inputs["Color"].default_value = tinted + (1.0,)
    scatter.inputs["Anisotropy"].default_value = anisotropy
    graph.link(extinction, scatter.inputs["Density"])
    absorption = graph.node("ShaderNodeVolumeAbsorption")
    absorption.inputs["Color"].default_value = tinted + (1.0,)
    graph.link(extinction, absorption.inputs["Density"])

    incoming = geometry.outputs["Incoming"]
    channels = []
    for channel, vector in enumerate(medium["ambient"]):
        toward = tuple(sum(basis[row][axis] * float(vector[axis]) for axis in range(3)) for row in range(3))
        along = graph.math("MULTIPLY", graph.vector("DOT_PRODUCT", incoming, toward), -anisotropy)
        radiance = graph.math("MAXIMUM", graph.math(
            "MULTIPLY", graph.math("ADD", along, float(vector[3])), float(medium["ambient_scale"])), 0.0)
        channels.append(graph.math("MULTIPLY", graph.math("MULTIPLY", radiance, albedo[channel]), extinction))
    emitted = graph.node("ShaderNodeCombineXYZ")
    for axis, value in zip("XYZ", channels):
        graph.link(value, emitted.inputs[axis])
    stated = graph.vector("SCALE", tuple(float(component) for component in medium["emission"]), fade)
    emission = graph.node("ShaderNodeEmission")
    emission.inputs["Strength"].default_value = 1.0
    graph.link(graph.vector("ADD", emitted.outputs["Vector"], stated), emission.inputs["Color"])

    joined = graph.node("ShaderNodeAddShader")
    tree.links.new(scatter.outputs[0], joined.inputs[0])
    tree.links.new(absorption.outputs[0], joined.inputs[1])
    total = graph.node("ShaderNodeAddShader")
    tree.links.new(joined.outputs[0], total.inputs[0])
    tree.links.new(emission.outputs[0], total.inputs[1])
    output = graph.node("ShaderNodeOutputMaterial")
    tree.links.new(total.outputs[0], output.inputs["Volume"])
    return material


def _sun_share(sun, medium):
    """Give the level sun its share of the medium and return the tint the medium's scattering
    carries per channel (see the module docstring). The stated light has to be the sun's own
    direction: it is the main light the source scatters, and a direction the level sun does not
    have means the medium and the environment were read for different phases."""
    stated = medium["light"]
    if sun is None:
        raise RuntimeError("[medium] the medium scatters the level's main light, and no level sun is stood up")
    data = sun.data
    basis = material_builder.world_basis()
    toward = Vector(tuple(sum(basis[row][axis] * float(stated["direction"][axis]) for axis in range(3))
                          for row in range(3))).normalized()
    facing = (sun.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
    if toward.dot(facing) < 1.0 - 1e-6:
        raise ValueError("[medium] the medium's light comes from {0}, the level sun from {1}".format(
            tuple(round(component, 5) for component in toward), tuple(round(component, 5) for component in facing)))
    if data.energy <= 0.0 or min(data.color) <= 0.0:
        raise ValueError("[medium] the level sun ({0}) emits nothing in some channel, so it cannot carry the "
                         "medium's colour".format(sun.name))
    ratio = [float(want) / float(have) for want, have in zip(stated["color"], data.color)]
    peak = max(ratio)
    data[STATED_SHARE] = data.volume_factor
    data.volume_factor = float(stated["intensity"]) * float(stated["scale"]) * peak / data.energy
    return tuple(component / peak for component in ratio)


def _lamp_copies(scene, medium, receivers, tint):
    shadowed = bool(medium["punctual_shadows"])
    copies = 0
    for obj in list(scene.objects):
        if obj.type != "LIGHT" or obj.data.type == "SUN" or TWIN_OF in obj or obj.data.volume_factor <= 0.0:
            continue
        share = obj.data.volume_factor
        data = obj.data.copy()
        data.name = obj.data.name + TWIN_SUFFIX
        data.volume_factor = share
        data.diffuse_factor = 0.0
        data.specular_factor = 0.0
        data.transmission_factor = 0.0
        data.use_shadow = shadowed and obj.data.use_shadow
        data.shadow_soft_size = TWIN_RADIUS
        untinted = [component / share_of for component, share_of in zip(obj.data.color, tint)]
        brightest = max(max(untinted), 1.0)
        data.color = tuple(component / brightest for component in untinted)
        data.energy = obj.data.energy * brightest
        copy = bpy.data.objects.new(obj.name + TWIN_SUFFIX, data)
        copy.matrix_world = obj.matrix_world.copy()
        copy[TWIN_OF] = obj.name
        copy.light_linking.receiver_collection = receivers
        scene.collection.objects.link(copy)
        obj.data[HANDED_SHARE] = share
        obj.data.volume_factor = 0.0
        copies += 1
    return copies


def _integration(scene, medium):
    start, end = (float(value) for value in medium["range"])
    slices, tile, distribution = medium["grid"]
    eevee = scene.eevee
    eevee.use_volume_custom_range = True
    eevee.volumetric_start = max(start, 1e-6)
    eevee.volumetric_end = end
    if str(int(tile)) not in TILE_SIZES:
        raise ValueError("[medium] the source's froxel tile of {0} px is not one EEVEE integrates at {1}"
                         .format(tile, TILE_SIZES))
    eevee.volumetric_tile_size = str(int(tile))
    eevee.volumetric_samples = int(slices)
    eevee.volumetric_sample_distribution = min(max(1.0 - float(distribution) / (4.0 * (int(slices) - 1)), 0.0), 1.0)
    eevee.use_volumetric_shadows = False
    eevee.clamp_volume_indirect = NO_INDIRECT


class _Graph:
    """Node wiring for one tree: a value is a constant or an output socket."""

    def __init__(self, tree):
        self.tree = tree

    def node(self, kind):
        return self.tree.nodes.new(kind)

    def link(self, value, socket):
        if isinstance(value, bpy.types.NodeSocket):
            self.tree.links.new(value, socket)
        else:
            socket.default_value = value

    def math(self, operation, first, second, clamp=False):
        node = self.node("ShaderNodeMath")
        node.operation = operation
        node.use_clamp = clamp
        self.link(first, node.inputs[0])
        self.link(second, node.inputs[1])
        return node.outputs[0]

    def vector(self, operation, first, second):
        node = self.node("ShaderNodeVectorMath")
        node.operation = operation
        self.link(first, node.inputs[0])
        if operation == "SCALE":
            self.link(second, node.inputs["Scale"])
        else:
            self.link(second, node.inputs[1])
        return node.outputs["Value" if operation == "DOT_PRODUCT" else "Vector"]
