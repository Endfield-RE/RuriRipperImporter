"""Keeping the generated shaders Painter runs the ones the generator last deployed.

Painter never reads a shader from where the generator writes it: putting a shader on a shelf
copies it there, and a project keeps its own copy of every shader its instances run -- the
one it was given when it was last switched, carried inside the project file. A deploy
therefore reaches a project only when something copies it twice: onto the shelf, and from the
shelf into the project's instances. A shelf or a project left holding an older generation
shades differently from Blender without saying so.

So every game's stack for this host is copied over any shelf that already carries it -- the
shader and its manifest together, they are one product -- when the plugin starts, whenever a
shelf finishes reading the disk (Painter then notices the new file and recompiles it), and
before an import wires a shader. A shelf that does not carry a stack is left alone: putting a
shader on a shelf is the person's choice, keeping it current is not.

And every instance of the open project that runs one of those shaders is moved onto the
shelf's copy when the project is ready and whenever a shelf finishes reading the disk -- a
file copied at start is not a resource until that crawl ends, and a project opened before it
ends finds nothing to move to. Painter keeps an instance's values across the move, by name; a
value the new generation no longer declares goes with the old one.
"""

from __future__ import annotations

import json
import os
import shutil

import substance_painter.event
import substance_painter.exception
import substance_painter.js
import substance_painter.project
import substance_painter.resource

from ...Kernel import host as host_port
from ...Kernel import shaderstack


def _products():
    """Every stack this host was given: its shader's name and the files that make it up."""
    for stack in shaderstack.stacks().values():
        name = stack.shader_name()
        yield name, [stack.asset(name + ".glsl"), stack.manifest_path()]


def sync(report):
    """Copy each stack's shader and manifest over the shelf copies that differ from them.
    Returns how many files were copied; what was copied, or failed to be, goes into ``report``."""
    copied = 0
    roots = [shelf.path() for shelf in substance_painter.resource.Shelves.all()]
    for name, product in _products():
        for root in roots:
            folder = os.path.join(root, "shaders")
            if not os.path.isfile(os.path.join(folder, name + ".glsl")):
                continue
            for source in product:
                target = os.path.join(folder, os.path.basename(source))
                with open(source, "rb") as handle:
                    wanted = handle.read()
                held = b""
                if os.path.isfile(target):
                    with open(target, "rb") as handle:
                        held = handle.read()
                if held == wanted:
                    continue
                try:
                    shutil.copyfile(source, target)
                except OSError as error:
                    report.append("!! shelf sync failed {0}: {1}".format(target, error))
                    continue
                copied += 1
                report.append("synced {0} into the shelf: {1}".format(os.path.basename(source), target))
    return copied


def _shelf_shader(name, shelves):
    """The url of a shelf's shader of this name, or None when no shelf carries it. A search
    also answers with the copies projects carry; a shelf's own copy has the shelf as context."""
    for found in substance_painter.resource.search("u:shader " + name):
        identifier = found.identifier()
        if identifier.name == name and identifier.context in shelves:
            return identifier.url()
    return None


def follow(report):
    """Move every instance of the open project that runs a generated shader onto the shelf's
    copy of it. Returns how many instances moved."""
    if not substance_painter.project.is_open():
        return 0
    shelves = {shelf.name() for shelf in substance_painter.resource.Shelves.all()}
    shelved = {}
    for name, _product in _products():
        url = _shelf_shader(name, shelves)
        if url is not None:
            shelved[name] = url
    moved = {}
    for instance in substance_painter.js.evaluate("alg.shaders.instances()"):
        url = shelved.get(str(instance.get("shader") or ""))
        if url is None or instance.get("url") == url:
            continue
        substance_painter.js.evaluate("alg.shaders.updateShaderInstance({0}, {1})".format(
            int(instance["id"]), json.dumps(url)))
        moved.setdefault(instance["shader"], []).append(str(instance.get("label") or instance["id"]))
    for name, labels in sorted(moved.items()):
        report.append("moved {0} instance(s) of {1} onto the shelf's generation: {2}".format(
            len(labels), name, ", ".join(sorted(labels))))
    return sum(len(labels) for labels in moved.values())


def _announce(report):
    host = host_port.current()
    for line in report:
        host.log(host_port.ERROR if line.startswith("!!") else host_port.INFO, line)


def _on_shelf_read(_event):
    """A shelf finished reading the disk: the copy a sync made earlier -- at start, before this
    crawl -- is a resource only now, so the open project follows it now too."""
    report = []
    sync(report)
    follow(report)
    _announce(report)


def _on_project_ready(_event):
    report = []
    follow(report)
    _announce(report)


def start():
    """Sync now if the shelves are up, and again each time one finishes reading the disk;
    follow the shelves with each project as it becomes ready."""
    substance_painter.event.DISPATCHER.connect(substance_painter.event.ShelfCrawlingEnded, _on_shelf_read)
    substance_painter.event.DISPATCHER.connect(substance_painter.event.ProjectEditionEntered, _on_project_ready)
    report = []
    try:
        sync(report)
    except substance_painter.exception.ServiceNotFoundError:
        report.append("the shelves are not up yet; the generated shaders are synced as each finishes reading")
    _announce(report)


def stop():
    substance_painter.event.DISPATCHER.disconnect(substance_painter.event.ShelfCrawlingEnded, _on_shelf_read)
    substance_painter.event.DISPATCHER.disconnect(substance_painter.event.ProjectEditionEntered, _on_project_ready)
