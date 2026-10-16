"""Run: blender --background --factory-startup --python-exit-code 1 --python tests/blender_smoke.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Matrix
import scan_tools

scan_tools.register()
bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24)
source = bpy.context.object
source.scale = (1.1, 2.2, 0.8)
source.location = (3, -2, 4)
source.rotation_euler = (0.1, 0.2, 0.3)
bpy.context.view_layer.update()
snapshot = [tuple(v.co) for v in source.data.vertices]
source_matrix = source.matrix_world.copy()
s = bpy.context.scene.scan_tools
s.samples = 500
s.proxy_faces = 1000
s.target = 300
assert bpy.ops.scan_tools.analyze() == {'FINISHED'}
assert s.preview and s.source == source
assert s.mirror is not None  # Live mirror is created automatically
assert bpy.ops.scan_tools.mirror() == {'FINISHED'}
assert s.mirror is not None
assert bpy.ops.scan_tools.finish() == {'FINISHED'}
result = bpy.context.object
assert result != source and 'scan_report' in result
result.data.calc_loop_triangles()
assert len(result.data.loop_triangles) <= 330
assert result.matrix_world == Matrix.Identity(4)
assert snapshot == [tuple(v.co) for v in source.data.vertices]
assert source_matrix == source.matrix_world
assert bpy.ops.scan_tools.clear() == {'FINISHED'}
assert not source.hide_get()
scan_tools.unregister()
print('BLENDER SMOKE OK')
