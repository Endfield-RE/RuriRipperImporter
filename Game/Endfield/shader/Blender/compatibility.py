"""Opt-in Endfield character shading from the verified 5.2 snapshot.

Only shading changes: the Statement reader, meshes, rigs and actions stay native.
Legacy template names and parameter tables are isolated from the current stack.
"""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import bpy
from bpy.app.handlers import persistent
from bpy.props import EnumProperty

from .....Host.Blender import material_builder as host
from .legacy52 import runtime as legacy

MODE = 'ruri_endfield_shader_mode'
NATIVE_KEY = 'ruri_character_uber_endfield'
LEGACY_KEY = NATIVE_KEY + '_legacy52'
_stack = None
_groups = {}


class StableGraph(legacy.G):
    """5.3 inserts LightIndex before Vector; never address that input by index."""
    def vtrans(self, v, frm, to, kind='VECTOR'):
        key = ('vt', frm, to, kind, self._ck(v))
        hit = self._cse.get(key)
        if hit is not None:
            return hit
        node = self._nd('ShaderNodeVectorTransform')
        node.vector_type = kind
        node.convert_from = frm
        node.convert_to = to
        self._set(node.inputs['Vector'], v)
        self._cse[key] = node.outputs['Vector']
        return node.outputs['Vector']


# Override only the adapter seam, retaining the SHA-locked vendor snapshot.
legacy.G = StableGraph


def repair_vector_inputs():
    """Migrate graphs made by the initial compatibility adapter, in place."""
    repaired = 0
    for mat in bpy.data.materials:
        if mat.library is not None or mat.get('ruri_uber_stack') != LEGACY_KEY or not mat.node_tree:
            continue
        for node in mat.node_tree.nodes:
            if node.bl_idname != 'ShaderNodeVectorTransform':
                continue
            # Implicit light sockets appear in iteration but are deliberately
            # omitted by Blender's name lookup in this 5.3 build.
            wrong = next((s for s in node.inputs if s.identifier == 'LightIndex'), None)
            right = node.inputs.get('Vector')
            if wrong is None or right is None or not wrong.is_linked or right.is_linked:
                continue
            link = wrong.links[0]
            source = link.from_socket
            mat.node_tree.links.remove(link)
            mat.node_tree.links.new(source, right)
            repaired += 1
    return repaired


def plain(value):
    if hasattr(value, 'to_dict'):
        return {k: plain(v) for k, v in value.to_dict().items()}
    if hasattr(value, 'to_list'):
        return value.to_list()
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    return value


class LegacyStack(legacy.Stack):
    def __init__(self):
        manifest = copy.deepcopy(next(m for m in legacy.MANIFESTS
                                     if m['names']['panel_key'] == NATIVE_KEY))
        manifest['names']['panel_key'] = LEGACY_KEY
        manifest['names']['panel_title'] = 'Endfield Legacy 5.2'
        manifest['host']['registry_module'] = host.__name__
        manifest['host']['rig_identity_module'] = host.__package__ + '.rig_identity'
        for key in ('mat_table', 'template_mat', 'vtx_modifier',
                    'vtx_tree_prefix', 'outline_template'):
            manifest['names'][key] = 'Legacy52 ' + manifest['names'][key]
        super().__init__(str(Path(__file__).parent / 'legacy52'), manifest)

    def group(self, name):
        if name.startswith('Legacy52 '):
            name = name[len('Legacy52 '):]
        got = _groups.get(name)
        if got is not None and legacy._alive(got):
            return got
        # Append, never rename/replace the current stack's same-named groups.
        requested = list(dict.fromkeys(self.group_names))
        with bpy.data.libraries.load(self.path, link=False) as (src, dst):
            missing = set(requested) - set(src.node_groups)
            if missing:
                raise RuntimeError('Legacy52 library missing groups: ' + str(missing))
            dst.node_groups = list(requested)
        for key, group in zip(requested, dst.node_groups):
            if group is None or group.get('ruri_stamp') != self.STAMP:
                raise RuntimeError('Legacy52 shader library stamp mismatch: ' + key)
            group.name = 'Legacy52 ' + key
            host.plugin_data(group)
            _groups[key] = group
        return _groups[name]

    def _template(self, *args):
        return host.plugin_data(super()._template(*args))

    def instantiate(self, *args, **kwargs):
        mat, count = super().instantiate(*args, **kwargs)
        return host.content(mat), count

    def _mat_table_image(self):
        return host.plugin_data(super()._mat_table_image())


def stack():
    global _stack
    if _stack is None:
        _stack = LegacyStack()
        legacy.STACKS[:] = [_stack]
        legacy.LIGHT_TABLE = 'Legacy52 RuriLightTable'
    return _stack


def provide(builder, props):
    mode = builder.options.get('endfield_shader_mode')
    if mode is None:
        mode = getattr(bpy.context.scene, MODE, 'NATIVE')
    if mode != 'LEGACY52':
        return None
    result = stack().provider(builder, props)
    if result is not None:
        result['ruri_endfield_shader_mode'] = 'LEGACY52'
        result['ruri_legacy_keywords'] = list(getattr(props, 'keywords', ()))
        result['ruri_legacy_passes'] = json.dumps(list(getattr(props, 'shader_passes', ())))
        # The legacy runtime uses names internally. Keep actual image references
        # too, so even vertex-only textures survive a save and image rename.
        result['ruri_legacy_images'] = {k: builder._load_image(v)
                                        for k, v in props.textures.items()
                                        if builder._load_image(v) is not None}
        stack()._param_flush()
    return result


def source_adapter(mat):
    images = {}
    retained = mat.get('ruri_legacy_images', {})
    for key, value in dict(mat.get('ruri_uber_images') or {}).items():
        image = value if isinstance(value, bpy.types.Image) else bpy.data.images.get(value)
        image = image if image is not None else retained.get(key)
        if image is not None:
            images[key] = image
    props = SimpleNamespace(
        name=mat.name + '.shading-build', shader_name=mat.get('ruri_uber_shader', ''),
        shader_ref={}, floats=plain(mat.get('ruri_uber_floats', {})),
        colors=plain(mat.get('ruri_uber_colors', {})),
        texture_st=plain(mat.get('ruri_uber_st', {})), textures=images,
        keywords=list(mat.get('ruri_legacy_keywords', ())),
        disabled_passes=list(mat.get('ruri_uber_disabled_passes', ())),
        shader_passes=json.loads(mat['ruri_legacy_passes']) if 'ruri_legacy_passes' in mat
        else [(str(p), str(p)) for p in mat.get('ruri_uber_shader_passes', ())])
    builder = SimpleNamespace(options={'endfield_shader_mode': 'LEGACY52'},
                              shader_display_name=lambda p: p.shader_name,
                              _load_image=lambda image, **kw: image)
    return builder, props


def rebuild_material(mat, mode):
    builder, props = source_adapter(mat)
    if mode == 'LEGACY52':
        new = provide(builder, props)
    else:
        from . import ruri_endfield as native
        target = next(s for s in native.STACKS if s.PANEL_KEY == NATIVE_KEY)
        # Preserve the current edited keyword uniforms on a round trip.
        record = {
            'ruri_uber_part': str(mat['ruri_uber_part']),
            'ruri_uber_images': dict(props.textures),
            'ruri_uber_floats': props.floats, 'ruri_uber_colors': props.colors,
            'ruri_uber_st': props.texture_st,
            'ruri_uber_disabled_passes': props.disabled_passes,
            'ruri_uber_shader_passes': [str(mode or name) for name, mode in props.shader_passes],
            'ruri_uber_shader_guid': str(mat.get('ruri_uber_shader_guid', '')),
            'ruri_uber_shader': props.shader_name,
        }
        new = target._compile(props.name, record)
    if new is None:
        raise RuntimeError('Shader mode does not claim material: ' + mat.name)
    for key in mat.keys():
        if key not in new and not key.startswith('ruri_uber_') and key not in (
                'ruri_shading', 'ruri_param_col', 'ruri_closure_engine',
                'ruri_endfield_shader_mode', 'ruri_capability_state'):
            new[key] = plain(mat[key])
    return new


def replace_all(materials, mode):
    replacements = []
    try:
        for mat in materials:
            replacements.append((mat, rebuild_material(mat, mode)))
    except Exception:
        for _, new in replacements:
            bpy.data.materials.remove(new)
        raise
    for old, new in replacements:
        name = old.name
        old.user_remap(new)
        old.name = name + '.previous-shading'
        new.name = name
    # Batch retirement avoids stale depsgraph entries while iterating.
    if replacements:
        bpy.data.batch_remove([old for old, _ in replacements])
    return [new for _, new in replacements]


def compile_all():
    repair_vector_inputs()
    s = stack()
    mats = [m for m in bpy.data.materials if m.library is None
            and m.get('ruri_uber_stack') == LEGACY_KEY and m.get(s.TEMPLATE_KEY) is None]
    pending = [m for m in mats if not m.node_tree or any(
        n.type == 'GROUP' and n.node_tree is None for n in m.node_tree.nodes)]
    return replace_all(pending, 'LEGACY52')


def vertices(objects=None, camera=None, refill=False):
    s = stack()
    objects = list(objects) if objects is not None else list(bpy.context.scene.objects)
    relevant = [o for o in objects if o.type == 'MESH' and any(
        m and m.get('ruri_uber_stack') == LEGACY_KEY for m in o.data.materials)]
    if not relevant:
        return 0
    count = s.apply_vertex_stage(objects=relevant, camera=camera)
    for obj in relevant:
        mod = obj.modifiers.get(s.VTX_MODIFIER)
        if mod is not None and mod.node_group is not None:
            host.plugin_data(mod.node_group)
    return count


def refresh_lights():
    if any(m.get('ruri_uber_stack') == LEGACY_KEY for m in bpy.data.materials):
        legacy.refresh_light_tables()
    # The host's role registry also coordinates the native stacks' shadow lamp.
    # This adapter refreshes a table, not an independent native-light identity.
    from . import ruri_endfield as native
    return native.refresh_main_light_role()


@persistent
def update_rig(*args):
    if _stack is not None:
        _stack.push_rig_basis(*args)


def purge():
    _groups.clear()
    legacy.RIG_DRIVEN.clear()
    legacy.RIG_SCANNED[0] = False
    if _stack is not None:
        _stack._mirror = None
        _stack._next_col[0] = 1
    return 0


def apply_scene(scene, mode):
    wanted = NATIVE_KEY if mode == 'LEGACY52' else LEGACY_KEY
    materials = {slot.material for obj in scene.objects if obj.type == 'MESH'
                 for slot in obj.material_slots if slot.material
                 and slot.material.library is None
                 and slot.material.get('ruri_uber_stack') == wanted}
    made = replace_all(sorted(materials, key=lambda m: m.name), mode)
    from . import ruri_endfield as native
    current = next(s for s in native.STACKS if s.PANEL_KEY == NATIVE_KEY)
    for obj in scene.objects:
        if obj.type != 'MESH':
            continue
        is_legacy = any(m and m.get('ruri_uber_stack') == LEGACY_KEY for m in obj.data.materials)
        mod = obj.modifiers.get(current.VTX_MODIFIER)
        saved = 'ruri_legacy_modifier_state'
        if is_legacy and mod is not None:
            if saved not in obj:
                obj[saved] = [int(mod.show_viewport), int(mod.show_render)]
            mod.show_viewport = mod.show_render = False
        elif not is_legacy:
            old = obj.modifiers.get(stack().VTX_MODIFIER)
            if old is not None:
                obj.modifiers.remove(old)
            if saved in obj:
                if mod is not None:
                    mod.show_viewport, mod.show_render = map(bool, obj[saved])
                del obj[saved]
    if mode == 'LEGACY52':
        vertices(objects=scene.objects, camera=scene.camera)
        stack().rig_rescan()
        stack().push_rig_basis()
    else:
        current.apply_vertex_stage(objects=scene.objects, camera=scene.camera)
    return len(made)


class RURI_OT_endfield_shader_compat(bpy.types.Operator):
    bl_idname = 'ruri.endfield_shader_compat'
    bl_label = 'Apply Mode to Scene Characters'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            count = apply_scene(context.scene, getattr(context.scene, MODE))
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, 'Rebuilt %d Endfield character materials' % count)
        return {'FINISHED'}


class RURI_PT_endfield_shader_compat(bpy.types.Panel):
    bl_label = 'Endfield Shader Compatibility'
    bl_idname = 'RURI_PT_endfield_shader_compat'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'RuriRipper'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        self.layout.prop(context.scene, MODE, text='Shader Mode')
        self.layout.label(text='New imports use this mode. Existing materials:')
        self.layout.operator(RURI_OT_endfield_shader_compat.bl_idname)
        self.layout.label(text='Character shading only; rigs/actions are unchanged.')


def register():
    setattr(bpy.types.Scene, MODE, EnumProperty(name='Endfield Shader Mode',
        items=[('NATIVE', 'Native 5.3', 'Current native-light shader'),
               ('LEGACY52', 'Legacy 5.2 Compatible', 'Pinned legacy character shader on Blender 5.3')],
        default='NATIVE'))
    for cls in (RURI_OT_endfield_shader_compat, RURI_PT_endfield_shader_compat):
        bpy.utils.register_class(cls)
    host.register_graph_provider(provide)
    host.register_vertex_stage(vertices)
    host.register_material_compile(compile_all)
    host.register_plugin_purge(purge)
    host.register_light_role_refresh(refresh_lights)
    host.register_capability_rewire(stack().rewire_capabilities)
    host.register_material_panel(stack())
    for handlers in (bpy.app.handlers.frame_change_post, bpy.app.handlers.depsgraph_update_post):
        if update_rig not in handlers:
            handlers.append(update_rig)


def unregister():
    for handlers in (bpy.app.handlers.frame_change_post, bpy.app.handlers.depsgraph_update_post):
        if update_rig in handlers:
            handlers.remove(update_rig)
    host.unregister_material_panel(stack())
    host.unregister_capability_rewire(stack().rewire_capabilities)
    host.unregister_light_role_refresh(refresh_lights)
    host.unregister_plugin_purge(purge)
    host.unregister_material_compile(compile_all)
    host.unregister_vertex_stage(vertices)
    host.unregister_graph_provider(provide)
    for cls in (RURI_PT_endfield_shader_compat, RURI_OT_endfield_shader_compat):
        bpy.utils.unregister_class(cls)
    delattr(bpy.types.Scene, MODE)
