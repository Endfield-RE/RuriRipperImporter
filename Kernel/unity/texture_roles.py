"""Which material property is which surface input -- as DATA, in layers.

A game's shaders name their properties however their authors typed them, so
"which texture is the base colour" is a mapping, and a mapping is configuration,
not code. This module holds the mechanism only: a role vocabulary, a table built
from JSON layers, a resolution of one material's property tables against it, and
the writer that records the choices a user makes. Which names mean what is stated
in the layer files:

* the DEFAULT layer the reader embeds (``TextureRoles.json`` in its statement
  kernel) -- Unity's own pipelines' vocabulary, plus the vocabulary the Ruri
  converters write when they have read a material's roles off its compiled shader
  (``_PackedMap`` and its channel floats, and the keyword that says the roles are
  proven);
* a GAME layer, kept in that game's own folder by the host that ships one;
* a USER layer, written by the host into its own workspace for a game that ships
  no folder, from the choices its user makes in front of the unmapped names.

Later layers override earlier ones property by property. A texture property no
layer names is UNMAPPED -- it is reported, never guessed at -- unless the material
carries the proven keyword, which says a converter already read every role off
the shader and what is left unnamed is unused.

Entry shapes, per texture property::

    {"role": "base_color"}                         a colour role: base_color, normal, emission
    {"role": "none"}                               known, and deliberately not wired
    {"channels": {"metallic": 0, "smoothness": 3}} scalar roles read from channel 0-3
    {"channels_from": {"metallic": "_PackedMapMetallic"}}
                                                   scalar roles whose channel a float
                                                   property of the material states
    {"role": "normal", "encoding": "hair_split"}   a decode the host knows by name

``colors`` and ``floats`` map a property name to the one role its value is.
"""
from __future__ import annotations

import json
import os

DEFAULT_LAYER_NAME = "TextureRoles.json"

COLOR_ROLES = ("base_color", "normal", "emission")
CHANNEL_ROLES = ("metallic", "roughness", "smoothness", "occlusion", "specular", "opacity", "height")
NONE_ROLE = "none"

# (role id, label, what it feeds) -- the vocabulary a host offers its user.
ROLES = (
    ("base_color", "Base Color", "The surface colour (albedo)"),
    ("normal", "Normal", "A tangent-space normal map"),
    ("emission", "Emission", "Light the surface gives off"),
    ("metallic", "Metallic", "One channel: 0 dielectric, 1 metal"),
    ("roughness", "Roughness", "One channel: 0 mirror, 1 matte"),
    ("smoothness", "Smoothness", "One channel: 1 mirror, 0 matte (roughness = 1 - x)"),
    ("occlusion", "Occlusion", "One channel of ambient occlusion"),
    ("specular", "Specular", "One channel of specular level"),
    ("opacity", "Opacity", "One channel of alpha"),
    ("height", "Height", "One channel of surface height"),
    (NONE_ROLE, "Not an input", "Known, and deliberately not wired"),
)

CHANNEL_NAMES = ("R", "G", "B", "A")


def is_channel_role(role):
    return role in CHANNEL_ROLES


class TextureRole:
    """One texture property's resolved part: ``role`` is a colour role or None,
    ``channels`` maps each scalar role to the channel index (0-3) it is read
    from, ``encoding`` names a decode the host knows."""
    __slots__ = ("name", "guid", "role", "channels", "encoding")

    def __init__(self, name, guid, role, channels, encoding):
        self.name = name
        self.guid = guid
        self.role = role
        self.channels = channels
        self.encoding = encoding

    def __repr__(self):
        return "<TextureRole {0} role={1} channels={2}>".format(self.name, self.role, self.channels)


class Resolution:
    """One material against a table: every texture whose part is stated, the
    colour and float values by role, the property names no layer states, and
    whether the material's roles were proven by a converter."""
    __slots__ = ("textures", "colors", "floats", "unmapped", "proven")

    def __init__(self, textures, colors, floats, unmapped, proven):
        self.textures = textures
        self.colors = colors
        self.floats = floats
        self.unmapped = unmapped
        self.proven = proven

    def first(self, role):
        """The first texture (in the material's own order) carrying a colour role."""
        for texture in self.textures:
            if texture.role == role:
                return texture
        return None

    def with_channel(self, role):
        """(texture, channel) for the first texture carrying a scalar role in a channel."""
        for texture in self.textures:
            channel = texture.channels.get(role)
            if channel is not None:
                return texture, channel
        return None, None

    def packed(self):
        """Every texture that carries at least one scalar role."""
        return [texture for texture in self.textures if texture.channels]


def read_layer(path):
    with open(path, "r", encoding="utf-8") as handle:
        layer = json.load(handle)
    if not isinstance(layer, dict):
        raise ValueError("texture role layer is not an object: {0}".format(path))
    return layer


def entry_for(role, channel):
    """The layer entry one user choice becomes: a colour role, an ignore, or one
    scalar role read from one channel."""
    if role == NONE_ROLE:
        return {"role": NONE_ROLE}
    if role in COLOR_ROLES:
        return {"role": role}
    if role in CHANNEL_ROLES:
        return {"channels": {role: int(channel)}}
    raise ValueError("not a role: {0!r}".format(role))


def save_entries(path, entries):
    """Merge ``entries`` ({property name: entry}) into the layer at ``path``,
    creating it as a version-1 layer when there is none. Returns the layer."""
    layer = read_layer(path) if os.path.isfile(path) else {"version": 1, "textures": {}}
    textures = layer.setdefault("textures", {})
    for name, entry in entries.items():
        textures[str(name)] = entry
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(layer, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    return layer
