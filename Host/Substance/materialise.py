"""Putting a stated selection into this application: one mesh file, and the
texture sets wired onto it.

Painter's entry point IS a file -- ``project.create`` takes a path and there is
no in-memory geometry API -- so materialising here writes one self-contained
glTF binary out of the statement, creates the project on it, splits every stated
texture into this application's engine channels, and wires the generated shader
onto each Texture Set.

That is not a lesser version of what the other host does; it is what this
application's project IS. A Texture Set is a material, so the geometry is
grouped by material rather than kept as a hierarchy, and a skinned mesh arrives
already baked to its rest -- which is the shape a painter wants anyway.

Nothing here decodes anything: the geometry is the statement's own arrays, and
every channel split is one named operation the kernel bakes.
"""

from __future__ import annotations

import os

import substance_painter.event
import substance_painter.project

from ...Kernel import statement as kernel_statement
from . import gltf_writer, planning, settings, shader, sp_apply

_UNSAFE = set('<>:"/\\|?*')

#: The one import in flight, carried from the click to the project-ready event.
#: Creating a project is asynchronous in this application, so the wiring stage
#: has to be reached from its own callback rather than inline.
_PENDING = [None]


def _safe(name):
    return "".join("_" if letter in _UNSAFE or ord(letter) < 32 else letter
                   for letter in str(name)).strip() or "model"


class _Job:
    """Everything one import needs, from the click to the wiring."""

    __slots__ = ("name", "statement", "options", "cache_dir", "glb_path",
                 "plans", "channels", "parameters", "mesh_maps", "report", "built")

    def __init__(self, name, statement, options):
        self.name = name
        self.statement = statement
        self.options = dict(options or {})
        self.cache_dir = os.path.join(settings.cache_dir(), _safe(name))
        self.glb_path = os.path.join(self.cache_dir, _safe(name) + ".glb")
        self.plans = {}
        self.channels = {}
        self.parameters = {}
        self.mesh_maps = {}
        self.report = []
        self.built = kernel_statement.Built()

    def texture_dir(self):
        return os.path.join(self.cache_dir, "Textures")


def materialise(context, statement, options, report=None):
    """Write the statement as one project and wire it. Returns
    :class:`Kernel.statement.Built`."""
    roots = statement.roots
    job = _Job(roots[0].label if roots else "model", statement, options)
    os.makedirs(job.cache_dir, exist_ok=True)
    if not _write_mesh(job):
        # Nothing DRAWN is an empty result, not a failure: a selection can be a
        # shader package, a config, a performance. The other host reports that
        # as nothing built, and so does this one -- a refusal would make one
        # click behave two ways depending on which application it was made in.
        job.built.missing.append(
            "{0} draws nothing this application can open -- a project here is a mesh "
            "file, and this selection states no mesh.".format(job.name))
        job.built.warnings.extend(job.report)
        if report is not None:
            report.extend(job.report)
        return job.built
    _plan(job)
    _bake(job)
    _launch(job)
    if report is not None:
        report.extend(job.report)
    job.built.warnings.extend(job.report)
    return job.built


# ---------------------------------------------------------------------------
# The mesh file
# ---------------------------------------------------------------------------
def _write_mesh(job):
    """One glTF binary holding every mesh the statement draws, each primitive
    named after the material it wears -- which is what becomes a Texture Set.

    False when the selection draws nothing: there is no project to open on a
    mesh file that has no meshes in it."""
    statement = job.statement
    builder = gltf_writer.GlbBuilder()
    materials = statement.materials
    slots = {}
    for node in statement.nodes:
        if not node.renders:
            continue
        mesh = statement.meshes.get(node.mesh)
        if mesh is None or not len(mesh.positions):
            job.built.missing.append(
                "{0}: the statement carries no geometry for {1}".format(node.name, node.mesh))
            continue
        primitives = []
        for first, count, slot in mesh.sections.tolist():
            key = node.materials[slot] if slot < len(node.materials) else ""
            stated = materials.get(key)
            name = (stated.name if stated is not None else key) or node.name
            index = slots.get(name)
            if index is None:
                index = slots[name] = builder.material(key, name)
            primitives.append({
                "positions": mesh.positions,
                "normals": mesh.normals,
                "uvs": mesh.uvs,
                "indices": mesh.triangles.reshape(-1)[first:first + count],
                "material": index,
            })
        if not primitives:
            continue
        made = builder.mesh(node.name, primitives)
        builder.node(node.name, mesh_index=made,
                     matrix=None if node.kind == kernel_statement.SKINNED else _matrix(node))
        job.built.imported += 1
    if builder.is_empty():
        return False
    builder.write(job.glb_path)
    job.report.append("mesh: {0}".format(job.glb_path))
    #: Texture Set name -> the material key behind it. A Texture Set IS a
    #: material here, and the name is what this application will call it.
    job.plans = {name: None for name in slots}
    job.built.objects = sorted(slots)
    return True


def _matrix(node):
    """One node's local transform as a row-major 4x4.

    A node whose mesh is baked to a skeleton's rest gets none at all: the
    geometry is already where it belongs, which is why a skinned one is written
    without a transform."""
    import numpy as np

    x, y, z, w = node.rotation
    rotation = np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ], dtype=np.float64)
    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, :3] = rotation * np.asarray(node.scale, dtype=np.float64)
    matrix[:3, 3] = node.position
    return matrix


# ---------------------------------------------------------------------------
# The texture sets
# ---------------------------------------------------------------------------
def _plan(job):
    """Plan every Texture Set the written model names: against the generated
    shader's own projection manifest where that shader claims the material, and
    against what the role layers say its textures mean where it does not."""
    materials = job.statement.materials
    textures = job.statement.textures
    by_name = {}
    for key, stated in materials.items():
        by_name.setdefault(stated.name or key, (key, stated))
    for name in list(job.plans):
        found = by_name.get(name)
        if found is None:
            continue
        key, stated = found
        plan = planning.plan_for(name, key, stated, texture_exists=lambda one: one in textures)
        job.plans[name] = plan
        for warning in plan.warnings:
            job.report.append("!! " + warning)
    planned = [plan for plan in job.plans.values() if plan is not None]
    shaded = sum(1 for plan in planned if plan.shaded)
    stack = shader.stack()
    job.report.append("materials: {0} of {1} wired to the generated shader, {2} by role{3}".format(
        shaded, len(planned), len(planned) - shaded,
        "" if stack is not None else " (" + shader.absence() + ")"))
    if stack is not None and not shaded and planned:
        # A stack that is here and claims nothing is a fact about the port, and
        # an invisible one unless it is said: the two vocabularies are printed
        # side by side so that WHICH of them has to grow is read off, not guessed.
        job.report.append(
            "!! {0} is here but claims none of them: it knows the surfaces {1}, and these "
            "materials point at {2}. Until its part vocabulary names them, every one of "
            "them is wired from its roles.".format(
                stack.shader_name(), planning.claimable_shaders() or "<none by name>",
                ", ".join(sorted({(stated.shader_name or "<unnamed>")
                                  for stated in materials.values()})) or "<nothing>"))


def _bake(job):
    """Split every planned source texture into this application's channels, shader parameters and
    baked mesh maps.

    The split itself is the KERNEL's: one named operation over the decoded
    image, done where the image already is. This side writes what comes back."""
    force = bool(job.options.get("force_rebuild", False))
    folder = job.texture_dir()
    os.makedirs(folder, exist_ok=True)
    textures = job.statement.textures
    written = 0
    reused = 0
    for name, plan in sorted(job.plans.items()):
        if plan is None:
            continue
        for destination, jobs in ((job.channels, plan.channel_jobs), (job.parameters, plan.param_jobs),
                                  (job.mesh_maps, plan.mesh_map_jobs)):
            done = {}
            for entry in jobs:
                # One file per texture and operation, whichever materials bind it.
                path = os.path.join(folder, _safe(entry.file_stem(textures[entry.guid].name)) + ".png")
                if force or not os.path.isfile(path):
                    # Asked of the STATEMENT, so the seeds and reading options
                    # of the selection being built go with it: the bake reads
                    # that selection's own texture, and a question without them
                    # flattens nothing at all.
                    payload = job.statement.payload(
                        "core.texture.bake", texture=entry.guid, operation=entry.op)
                    if not payload:
                        job.report.append(
                            "!! {0}: {1} could not be baked as {2}".format(
                                name, entry.source_property, entry.op))
                        continue
                    with open(path, "wb") as handle:
                        handle.write(payload)
                    written += 1
                else:
                    reused += 1
                done[entry.target] = path
            destination[name] = done
    job.report.append("textures: {0} written, {1} reused, into {2}".format(
        written, reused, folder))


# ---------------------------------------------------------------------------
# The project
# ---------------------------------------------------------------------------
def _launch(job):
    """Create the project on the written mesh (or reuse the open one) and wire
    everything up once it is ready.

    ``project.close()`` only POSTS the close, so creating the new project inline
    right after it hits "another project is already opened"; this application's
    own not-busy queue is how to sequence behind that, and creation itself is
    asynchronous too -- hence the edition-entered handler for the wiring."""
    _PENDING[0] = job
    substance_painter.event.DISPATCHER.connect(
        substance_painter.event.ProjectEditionEntered, _on_ready)

    def create():
        sp_apply.create_project(job.glb_path,
                                int(job.options.get("texture_resolution", 2048)))

    if substance_painter.project.is_open():
        substance_painter.project.close()
        substance_painter.project.execute_when_not_busy(create)
    else:
        create()


def _on_ready(_event):
    job = _PENDING[0]
    _PENDING[0] = None
    try:
        substance_painter.event.DISPATCHER.disconnect(
            substance_painter.event.ProjectEditionEntered, _on_ready)
    except Exception:
        pass
    if job is None:
        return
    sp_apply.apply(job.plans, job.channels, job.parameters, job.mesh_maps, job.report, job.options)

