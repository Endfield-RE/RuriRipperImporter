# Legacy 5.2 character shader snapshot

Shader runtime and generated node library, stamp `941c8817ab4011a2`.
The runtime is retained verbatim from the previously verified importer source
snapshot (integration checkpoint `2f5490c`); the matching character node library
was verified against the working Steam Blender 5.2.2 installation.
Original importer license is retained in `LICENSE` alongside these resources.

SHA-256:

- `runtime.py`: `13f242b03b03a2a9d3e5e68de1bd0b88137a4d23c68de4f7b16ae3a883037cc3`
- `ruri_character_uber_endfield.blend`: `f91e1b2e047c8585f334b439a70d12a0fdec68a0d2fea838326974ed0c6b1ef1`

Only the character manifest is activated by the compatibility adapter. The
runtime includes historical manifests for other stacks, but those stacks are
not registered and their libraries are intentionally not shipped here.
No game meshes, textures, animation fixtures or private decoding code are added.
Adapter changes belong in the sibling `compatibility.py`, not this snapshot.
