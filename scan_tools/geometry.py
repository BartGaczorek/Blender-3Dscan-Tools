"""Blender mesh helpers, shared by the UI and the isolated worker."""
import bpy
import numpy as np
from mathutils import Matrix


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
    # Triangulate explicitly so BVH face indices and clicked regions are stable.
    tri = obj.modifiers.new('Scan triangles', 'TRIANGULATE')
    bpy.ops.object.modifier_apply(modifier=tri.name)
    obj.data.calc_loop_triangles()
    return before, len(obj.data.loop_triangles)


def remove_object(obj):
    if obj is None:
        return
    mesh = obj.data if obj.type == 'MESH' else None
    bpy.data.objects.remove(obj, do_unlink=True)
    if mesh is not None and mesh.users == 0:
        bpy.data.meshes.remove(mesh)
