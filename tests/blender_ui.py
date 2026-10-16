"""Real-window regression. Run without --background, with --enable-event-simulate.

Main-loop heartbeat and panel redraw must continue while the child works.
Exercises region picking via a simulated viewport click, alignment and Esc cancel.
"""
import os
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
from mathutils import Quaternion
import scan_tools as addon

addon.register()
state = {'phase': 0, 'ticks': 0, 'deadline': time.monotonic()+90, 'max_elapsed': 0,
         'saw_busy': False, 'draws': 0, 'busy_draws': 0, 'job_phases': set()}


class CX_TEST_PT_STATUS(bpy.types.Panel):
    bl_label = 'CX modal test status'
    bl_idname = 'CX_TEST_PT_STATUS'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Item'

    def draw(self, context):
        state['draws'] += 1
        if context.window_manager.scan_runtime.busy:
            state['busy_draws'] += 1
        addon.SCAN_PT_panel.draw(self, context)


bpy.utils.register_class(CX_TEST_PT_STATUS)


def tick():
    try:
        assert time.monotonic() < state['deadline'], 'UI test timeout'
        state['ticks'] += 1
        rt = bpy.context.window_manager.scan_runtime
        area = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
        region = next(r for r in area.regions if r.type == 'WINDOW')
        area.spaces.active.show_region_ui = True
        area.tag_redraw()
        with bpy.context.temp_override(area=area, region=region):
            if state['phase'] == 0:
                bpy.ops.object.select_all(action='SELECT')
                bpy.ops.object.delete(use_global=False)
                bpy.ops.mesh.primitive_cube_add()
                state['source'] = bpy.context.object
                bpy.context.scene.scan_tools.proxy_faces = 1000
                bpy.context.scene.scan_tools.samples = 500
                assert bpy.ops.scan_tools.analyze() == {'RUNNING_MODAL'}
                state['phase'] = 1
            elif state['phase'] == 1:
                if rt.busy:
                    state['saw_busy'] = True
                    state['max_elapsed'] = max(rt.elapsed, state['max_elapsed'])
                    state['job_phases'].add(rt.phase)
                else:
                    assert bpy.context.scene.scan_tools.preview, rt.error
                    assert state['saw_busy'] and state['ticks'] > 5
                    assert not rt.error, rt.error
                    assert state['max_elapsed'] > 0
                    rv3d = area.spaces.active.region_3d
                    rv3d.view_rotation = Quaternion((1,0,0,0))
                    rv3d.view_perspective = 'ORTHO'
                    rv3d.view_distance = 8
                    rv3d.view_location = (0,0,0)
                    # Let region matrices update before raycasting next tick.
                    state['phase'] = 2
            elif state['phase'] == 2:
                assert bpy.ops.scan_tools.pick_plane('INVOKE_DEFAULT') == {'RUNNING_MODAL'}
                state['phase'] = 3
            elif state['phase'] == 3:
                from bpy_extras import view3d_utils
                from mathutils import Vector
                pixel = view3d_utils.location_3d_to_region_2d(region, area.spaces.active.region_3d, Vector((0.2,0.1,1)))
                assert pixel is not None
                bpy.context.window.event_simulate(type='LEFTMOUSE', value='PRESS',
                    x=int(region.x+pixel.x), y=int(region.y+pixel.y))
                state['phase'] = 4
            elif state['phase'] == 4:
                s = bpy.context.scene.scan_tools
                if s.region_info:
                    assert s.region is not None
                    assert bpy.ops.scan_tools.align_plane() == {'FINISHED'}
                    assert bpy.ops.scan_tools.clear() == {'FINISHED'}
                    assert bpy.ops.scan_tools.analyze() == {'RUNNING_MODAL'}
                    state['phase'] = 5
            elif state['phase'] == 5:
                if addon.ACTIVE_JOB and addon.ACTIVE_JOB.process is not None:
                    bpy.context.window.event_simulate(type='ESC', value='PRESS')
                    state['phase'] = 6
            elif state['phase'] == 6 and not rt.busy:
                assert addon.ACTIVE_JOB is None
                assert not bpy.context.scene.scan_tools.preview
                assert not state['source'].hide_get()
                assert state['busy_draws'] > 0, 'Progress panel was never drawn'
                print('BLENDER UI MODAL OK:', state['ticks'], 'heartbeats;',
                      state['busy_draws'], 'busy panel redraws; raycast click + align + Esc passed', flush=True)
                bpy.utils.unregister_class(CX_TEST_PT_STATUS)
                addon.unregister()
                bpy.ops.wm.quit_blender()
                return None
        return 0.1
    except Exception as exc:
        print('UI TEST FAILED:', repr(exc), flush=True)
        os._exit(1)


bpy.app.timers.register(tick, first_interval=1)
