"""CadXpert Scan Tools 0.1.0 — experimental Blender extension."""
import json
import bpy
import numpy as np
from mathutils import Matrix
from mathutils.bvhtree import BVHTree
from bpy.props import BoolProperty, IntProperty, FloatProperty, EnumProperty, PointerProperty
from . import core


def active_only(context, obj):
    for other in context.selected_objects:
        other.select_set(False)
    obj.hide_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj


def arrays(mesh):
    mesh.calc_loop_triangles()
    vertices = np.empty(len(mesh.vertices)*3, dtype=np.float64)
    mesh.vertices.foreach_get('co', vertices)
    triangles = np.empty(len(mesh.loop_triangles)*3, dtype=np.int32)
    mesh.loop_triangles.foreach_get('vertices', triangles)
    return vertices.reshape(-1, 3), triangles.reshape(-1, 3)


def bake(obj, matrix):
    obj.data.transform(matrix)
    # Negative determinants need winding reversal, not a guessed normals repair.
    if matrix.determinant() < 0:
        for poly in obj.data.polygons:
            poly.flip()
    obj.data.update()
    obj.matrix_world = Matrix.Identity(4)


def decimate(context, obj, target):
    active_only(context, obj)
    obj.data.calc_loop_triangles()
    before = len(obj.data.loop_triangles)
    if before > target:
        mod = obj.modifiers.new('Scan reduction', 'DECIMATE')
        mod.decimate_type = 'COLLAPSE'
        mod.ratio = max(0.000001, target/before)
        mod.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=mod.name)
    obj.data.calc_loop_triangles()
    return before, len(obj.data.loop_triangles)


def mesh_copy(context, source, name):
    result = bpy.data.objects.new(name, source.data.copy())
    context.collection.objects.link(result)
    return result


class ScanSettings(bpy.types.PropertyGroup):
    source: PointerProperty(type=bpy.types.Object)
    preview: PointerProperty(type=bpy.types.Object)
    mirror: PointerProperty(type=bpy.types.Object)
    symmetric: BoolProperty(name='Szukaj symetrii', default=True)
    plane: BoolProperty(name='Szukaj płaskiej ścianki', default=True)
    seed_axis: EnumProperty(name='Normalna symetrii', items=[
        ('AUTO', 'Auto (3 osie PCA)', ''), ('X', 'Bieżąca oś X', ''),
        ('Y', 'Bieżąca oś Y', ''), ('Z', 'Bieżąca oś Z', '')])
    proxy_faces: IntProperty(name='Trójkąty kopii roboczej', default=100000, min=1000, max=500000)
    samples: IntProperty(name='Próbki powierzchni', default=3000, min=500, max=20000)
    target: IntProperty(name='Docelowe trójkąty', default=1000000, min=100, max=20000000)
    keep: FloatProperty(name='Udział próbek do dopasowania', default=0.8, min=0.5, max=1.0)
    tolerance: FloatProperty(name='Tolerancja płaszczyzny / przekątna', default=0.006, min=0.0001, max=0.05, precision=4)


class SCAN_OT_analyze(bpy.types.Operator):
    bl_idname = 'scan_tools.analyze'
    bl_label = '1. Analizuj zaznaczony skan'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.scan_tools
        source = context.active_object
        if context.mode != 'OBJECT' or source is None or source.type != 'MESH':
            self.report({'ERROR'}, 'Wybierz siatkę w Object Mode')
            return {'CANCELLED'}
        if source.get('scan_generated'):
            self.report({'ERROR'}, 'Wybierz oryginalny skan, nie wygenerowany podgląd')
            return {'CANCELLED'}
        if source.modifiers or source.constraints or source.parent or source.animation_data:
            self.report({'ERROR'}, 'v0.1 wymaga samodzielnej siatki bez modyfikatorów, constraints i animacji')
            return {'CANCELLED'}
        if len(source.data.polygons) < 4:
            self.report({'ERROR'}, 'Za mało powierzchni')
            return {'CANCELLED'}
        if s.preview or s.mirror:
            self.report({'ERROR'}, 'Najpierw usuń poprzedni podgląd przyciskiem poniżej')
            return {'CANCELLED'}
        preview = None
        try:
            preview = mesh_copy(context, source, source.name+'_ANALYSIS')
            preview['scan_generated'] = True
            bake(preview, source.matrix_world.copy())
            decimate(context, preview, s.proxy_faces)
            verts, triangles = arrays(preview.data)
            points = core.sample_surface(verts, triangles, s.samples)
            if np.linalg.norm(np.ptp(points, axis=0)) < 1e-12:
                raise ValueError('Zerowy rozmiar skanu')
            report = {'version': '0.1.0', 'source': source.name,
                      'source_matrix': [list(row) for row in source.matrix_world],
                      'source_vertices': len(source.data.vertices),
                      'source_polygons': len(source.data.polygons),
                      'samples': s.samples, 'proxy_triangles': len(triangles)}
            plane_n = None
            if s.plane:
                plane_n, _, support, rms = core.fit_plane(points, s.tolerance)
                report.update(plane_support=support, plane_rms_in_scene_units=rms)
                # A weak RANSAC consensus on a curved scan is not treated as a face.
                if support < 0.12:
                    plane_n = None
            symmetry = None
            if s.symmetric:
                tree = BVHTree.FromPolygons(verts.tolist(), triangles.tolist(), all_triangles=True)
                def distances(coords):
                    return np.array([tree.find_nearest(p)[3] for p in coords])
                _, axes = core.pca(points)
                starts = list(axes.T) if s.seed_axis == 'AUTO' else [np.eye(3)['XYZ'.index(s.seed_axis)]]
                n, d, scores = core.symmetry_fit(points, distances, starts, s.keep)
                symmetry = (n, d)
                report.update(scores)
                report.update(symmetry_normal=n.tolist(), symmetry_offset=d)
            transform = core.orientation(points, plane_n, symmetry)
            preview.matrix_world = Matrix(transform.tolist())
            preview.color = (0.12, 0.55, 0.95, 1)
            preview['scan_report'] = json.dumps(report)
            s.source, s.preview = source, preview
            source.hide_set(True)
            active_only(context, preview)
            self.report({'INFO'}, 'Podgląd gotowy. Oceń osie; obracaj/przesuwaj podgląd przed akceptacją.')
            return {'FINISHED'}
        except Exception as exc:
            if preview is not None:
                mesh = preview.data
                bpy.data.objects.remove(preview, do_unlink=True)
                if mesh.users == 0:
                    bpy.data.meshes.remove(mesh)
            active_only(context, source)
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}


class SCAN_OT_mirror(bpy.types.Operator):
    bl_idname = 'scan_tools.mirror'
    bl_label = '2. Odśwież lustro kontrolne X=0'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.scan_tools
        if not s.preview:
            return {'CANCELLED'}
        if s.mirror:
            old = s.mirror.data
            bpy.data.objects.remove(s.mirror, do_unlink=True)
            if old.users == 0:
                bpy.data.meshes.remove(old)
        mirror = mesh_copy(context, s.preview, 'SCAN_MIRROR_CHECK')
        mirror['scan_generated'] = True
        bake(mirror, Matrix.Diagonal((-1, 1, 1, 1)) @ s.preview.matrix_world)
        mirror.color = (1, 0.24, 0.1, 1)
        mirror.hide_select = True
        s.mirror = mirror
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.shading.color_type = 'OBJECT'
        self.report({'INFO'}, 'Lustro jest statyczne. Odśwież po ręcznej zmianie podglądu.')
        return {'FINISHED'}


class SCAN_OT_finish(bpy.types.Operator):
    bl_idname = 'scan_tools.finish'
    bl_label = '3. Akceptuj i utwórz wynik'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.scan_tools
        if context.mode != 'OBJECT' or not s.preview or not s.source:
            return {'CANCELLED'}
        report = json.loads(s.preview['scan_report'])
        source = s.source
        if ([list(row) for row in source.matrix_world] != report['source_matrix'] or
                len(source.data.vertices) != report['source_vertices'] or
                len(source.data.polygons) != report['source_polygons']):
            self.report({'ERROR'}, 'Oryginał zmieniono. Usuń podgląd i ponów analizę.')
            return {'CANCELLED'}
        result = mesh_copy(context, source, source.name+'_READY')
        result['scan_generated'] = True
        transform = s.preview.matrix_world.copy()
        bake(result, transform @ source.matrix_world)
        before, after = decimate(context, result, s.target)
        report.update(transform_world=[list(row) for row in transform],
                      result_triangles=after, original_triangles=before,
                      target_triangles=s.target,
                      note='Scores describe automatic proxy fit, before manual corrections.')
        result['scan_report'] = json.dumps(report, ensure_ascii=False)
        text = bpy.data.texts.new(result.name+'_report.json')
        text.write(json.dumps(report, indent=2, ensure_ascii=False))
        s.preview.hide_set(True)
        if s.mirror:
            s.mirror.hide_set(True)
        active_only(context, result)
        self.report({'INFO'}, f'Wynik: {after:,} trójkątów. Oryginał zachowany; eksport STL z menu Blendera.')
        return {'FINISHED'}


class SCAN_OT_clear(bpy.types.Operator):
    bl_idname = 'scan_tools.clear'
    bl_label = 'Usuń podgląd / wróć do oryginału'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.scan_tools
        for obj in (s.mirror, s.preview):
            if obj:
                mesh = obj.data
                bpy.data.objects.remove(obj, do_unlink=True)
                if mesh.users == 0:
                    bpy.data.meshes.remove(mesh)
        s.mirror = s.preview = None
        if s.source:
            active_only(context, s.source)
        return {'FINISHED'}


class SCAN_PT_panel(bpy.types.Panel):
    bl_label = 'CadXpert Scan Tools (experimental)'
    bl_idname = 'SCAN_PT_tools'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Scan Tools'

    def draw(self, context):
        layout = self.layout
        s = context.scene.scan_tools
        for key in ('symmetric', 'seed_axis', 'plane', 'target'):
            layout.prop(s, key)
        box = layout.box()
        box.label(text='Parametry analizy')
        for key in ('proxy_faces', 'samples', 'keep', 'tolerance'):
            box.prop(s, key)
        layout.operator('scan_tools.analyze')
        layout.operator('scan_tools.mirror')
        layout.label(text='Lustro statyczne — odśwież po zmianach')
        layout.operator('scan_tools.finish')
        layout.operator('scan_tools.clear')
        if s.preview:
            report = json.loads(s.preview.get('scan_report', '{}'))
            if 'trimmed_rms_relative' in report:
                layout.label(text=f"RMS / przekątna: {report['trimmed_rms_relative']:.5f}")
                layout.label(text=f"P95 / przekątna: {report['p95_relative']:.5f}")
            layout.label(text='Wyniki metryk sprzed korekty ręcznej')


CLASSES = (ScanSettings, SCAN_OT_analyze, SCAN_OT_mirror, SCAN_OT_finish, SCAN_OT_clear, SCAN_PT_panel)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.scan_tools = PointerProperty(type=ScanSettings)


def unregister():
    del bpy.types.Scene.scan_tools
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
