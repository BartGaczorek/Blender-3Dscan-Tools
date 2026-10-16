"""Integration regressions for live reflection, plane alignment and background jobs."""
import json
from pathlib import Path
import sys
import time
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Matrix, Quaternion, Vector
import scan_tools as addon
from scan_tools import core, geometry

addon.register()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add()
source = bpy.context.object
source.name = 'TEST_SCAN'
source.rotation_euler = (0.4, -0.2, 0.3)
source.location = (5,-3,4)
source.scale = (1.3, 2.4, 0.8)
bpy.context.view_layer.update()
original = [tuple(v.co) for v in source.data.vertices]
original_matrix = source.matrix_world.copy()
s = bpy.context.scene.scan_tools
s.samples = 500
s.target = 100
assert bpy.ops.scan_tools.analyze() == {'FINISHED'}
assert not bpy.context.window_manager.scan_runtime.busy
preview, mirror = s.preview, s.mirror
assert mirror.data == preview.data, 'Live mirror must share proxy mesh'
assert mirror.constraints[0].type == 'COPY_TRANSFORMS'
assert preview.matrix_world == Matrix.Identity(4), 'Proxy starts with centered origin and baked preparation transform'
assert source.hide_get()
reflection = Matrix.Diagonal((-1,1,1,1))
for i in range(24):
    # Includes quaternion rotations and nonuniform positive scales.
    preview.rotation_mode = 'QUATERNION'
    preview.rotation_quaternion = Quaternion(Vector((0.3,1,0.2)).normalized(), i*0.19)
    preview.location = (i*0.1, -i*0.2, 3-i*0.05)
    preview.scale = (1+i*0.01, 0.8+i*0.02, 1.3)
    bpy.context.view_layer.update()
    np.testing.assert_allclose(np.array(mirror.matrix_world), np.array(reflection @ preview.matrix_world), atol=2e-5)
print('LIVE MIRROR: 24 transforms passed')
# Reset to rigid transform for dimensional plane fit.
preview.scale = (1,1,1)
bpy.context.view_layer.update()
verts, triangles = geometry.arrays(preview.data)
# Find the most numerous local plane by selecting one seed triangle on cube.
fit = core.planar_region(verts, triangles, 0, 25, 0.002)
assert len(fit['faces']) == 2
addon.set_region(bpy.context, verts, triangles, fit)
s.plane_direction = 'DOWN'
assert bpy.ops.scan_tools.align_plane() == {'FINISHED'}
normal = (preview.matrix_world.to_3x3().inverted().transposed() @ Vector(fit['normal'])).normalized()
center = preview.matrix_world @ Vector(fit['center'])
assert abs(normal.z+1) < 1e-5 and abs(center.z) < 1e-5
selected = verts[triangles[fit['faces']].reshape(-1)]
coords = np.column_stack((selected, np.ones(len(selected)))) @ np.array(preview.matrix_world).T
assert np.abs(coords[:,2]).max() < 1e-5
np.testing.assert_allclose(np.array(mirror.matrix_world), np.array(reflection @ preview.matrix_world), atol=2e-5)
print('BASE ALIGNMENT: world Z=0, normal -Z passed')
# Fit from Edit Mode selected faces through the actual Blender operator.
geometry.active_only(bpy.context, preview)
for poly in preview.data.polygons:
    poly.select = poly.index in fit['faces']
bpy.ops.object.mode_set(mode='EDIT')
assert bpy.ops.scan_tools.selected_plane() == {'FINISHED'}
assert bpy.context.mode == 'OBJECT'
# Final output reads original mesh snapshot rather than proxy geometry.
assert bpy.ops.scan_tools.finish() == {'FINISHED'}
result = bpy.context.object
assert result['scan_result']
assert original == [tuple(v.co) for v in source.data.vertices]
assert source.matrix_world == original_matrix
assert result.matrix_world == Matrix.Identity(4)
report = json.loads(result['scan_report'])
assert report['version'] == '0.2.0' and 'selected_base' in report
# With a small cube there was no reduction: final points must match the
# complete preparation + manual + original-world matrix composition.
expected_matrix = Matrix(report['transform_world']) @ original_matrix
expected = np.array([tuple(expected_matrix @ Vector(point)) for point in original])
actual = np.array([tuple(v.co) for v in result.data.vertices])
from mathutils.kdtree import KDTree
tree = KDTree(len(actual))
for i, point in enumerate(actual):
    tree.insert(point, i)
tree.balance()
assert max(tree.find(point)[2] for point in expected) < 1e-4
assert bpy.ops.scan_tools.clear() == {'FINISHED'}
assert not source.hide_get() and result.name in bpy.data.objects
print('OUTPUT AND SOURCE PRESERVATION passed')
# Cancellation really terminates the worker and removes job temp files.
geometry.active_only(bpy.context, source)
job = addon.BackgroundJob('ANALYZE', bpy.context, source, s)
job.launch()
folder = job.directory
job.close()
assert job.process.poll() is not None and not folder.exists()
assert original == [tuple(v.co) for v in source.data.vertices]
print('CANCELLATION: child exited and temp files removed')
# Failure does not silently succeed and logs remain available until cleanup.
job = addon.BackgroundJob('ANALYZE', bpy.context, source, s)
job.job['samples'] = -1
job.launch()
while job.process.poll() is None:
    job.update()
    time.sleep(0.1)
try:
    job.complete(bpy.context)
    raise AssertionError('Invalid worker job unexpectedly succeeded')
except RuntimeError:
    pass
assert job.process.returncode != 0
job.close()
assert original == [tuple(v.co) for v in source.data.vertices]
addon.unregister()
print('BLENDER FEATURE TESTS OK')
