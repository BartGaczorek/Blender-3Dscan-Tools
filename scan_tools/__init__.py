"""CadXpert Scan Tools 0.2.0. All heavy bpy operations run in a child Blender."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

import bpy
import numpy as np
from bpy.app.handlers import persistent
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from mathutils import Matrix, Vector
from . import core, geometry

ACTIVE_JOB = None


def redraw():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


def object_colors(context):
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.shading.color_type = 'OBJECT'


def clear_region(s):
    if s.region:
        geometry.remove_object(s.region)
        s.region = None
    s.region_info = ''


def create_live_mirror(context, s):
    """Exact S @ M using a reflected parent and LOCAL owner COPY_TRANSFORMS.

    No Euler inversion, Python transform handler, mesh rebuild or geometry copy.
    Native depsgraph updates during G/R/S, including quaternion rotations.
    """
    if s.mirror:
        geometry.remove_object(s.mirror)
    if s.mirror_root:
        geometry.remove_object(s.mirror_root)
    root = bpy.data.objects.new('SCAN_REFLECTION_X0', None)
    context.collection.objects.link(root)
    root.matrix_world = Matrix.Diagonal((-1, 1, 1, 1))
    root.empty_display_type = 'PLAIN_AXES'
    root.empty_display_size = 0.001
    root.hide_select = True
    root['scan_generated'] = True
    mirror = bpy.data.objects.new('SCAN_LIVE_MIRROR', s.preview.data)
    context.collection.objects.link(mirror)
    mirror.parent = root
    mirror.matrix_parent_inverse = Matrix.Identity(4)
    mirror.matrix_basis = Matrix.Identity(4)
    constraint = mirror.constraints.new('COPY_TRANSFORMS')
    constraint.target = s.preview
    constraint.target_space = 'WORLD'
    constraint.owner_space = 'LOCAL'
    constraint.mix_mode = 'REPLACE'
    mirror.color = (1.0, 0.24, 0.08, 1)
    mirror.hide_select = True
    mirror['scan_generated'] = True
    s.mirror_root, s.mirror = root, mirror
    object_colors(context)
    context.view_layer.update()


class ScanSettings(bpy.types.PropertyGroup):
    source: PointerProperty(type=bpy.types.Object)
    preview: PointerProperty(type=bpy.types.Object)
    mirror: PointerProperty(type=bpy.types.Object)
    mirror_root: PointerProperty(type=bpy.types.Object)
    region: PointerProperty(type=bpy.types.Object)
    region_info: StringProperty()
    auto_orientation: BoolProperty(name='Orientacja automatyczna (eksperymentalna)', default=False)
    symmetric: BoolProperty(name='Szukaj symetrii', default=True)
    plane: BoolProperty(name='Szukaj płaskiej ścianki', default=True)
    seed_axis: EnumProperty(name='Normalna symetrii', items=[
        ('AUTO', 'Auto (3 osie PCA)', ''), ('X', 'Bieżąca oś X', ''),
        ('Y', 'Bieżąca oś Y', ''), ('Z', 'Bieżąca oś Z', '')])
    proxy_faces: IntProperty(name='Trójkąty kopii roboczej', default=50000, min=1000, max=500000)
    samples: IntProperty(name='Próbki powierzchni', default=3000, min=500, max=20000)
    target: IntProperty(name='Docelowe trójkąty', default=1000000, min=100, max=20000000)
    keep: FloatProperty(name='Udział próbek do dopasowania', default=0.8, min=0.5, max=1.0)
    tolerance: FloatProperty(name='Auto: tolerancja / przekątna', default=0.006, min=0.0001, max=0.05, precision=4)
    region_angle: FloatProperty(name='Próg normalnych (stopnie)', default=25, min=1, max=75)
    region_distance: FloatProperty(name='Grubość pasa / przekątna', default=0.002, min=0.00001, max=0.05, precision=5)
    plane_direction: EnumProperty(name='Normalna po wyrównaniu', items=[
        ('DOWN', '-Z (dolna ścianka)', ''), ('UP', '+Z (górna ścianka)', '')])


class ScanRuntime(bpy.types.PropertyGroup):
    busy: BoolProperty(default=False, options={'SKIP_SAVE'})
    cancel_requested: BoolProperty(default=False, options={'SKIP_SAVE'})
    phase: StringProperty(default='', options={'SKIP_SAVE'})
    fraction: FloatProperty(default=0, min=0, max=1, options={'SKIP_SAVE'})
    indeterminate: BoolProperty(default=False, options={'SKIP_SAVE'})
    elapsed: FloatProperty(default=0, options={'SKIP_SAVE'})
    error: StringProperty(default='', options={'SKIP_SAVE'})


class BackgroundJob:
    def __init__(self, operation, context, source, s):
        self.operation = operation
        self.scene = context.scene
        self.collection = context.collection
        self.wm = context.window_manager
        self.source = source
        self.source_was_hidden = source.hide_get()
        self.directory = Path(tempfile.mkdtemp(prefix='cadxpert-scan-'))
        self.started = time.monotonic()
        self.process = self.log = None
        self.source_name = source.name
        self.job = {
            'operation': operation, 'source_name': source.name,
            'source_matrix': [list(row) for row in source.matrix_world],
            'source_vertices': len(source.data.vertices), 'source_polygons': len(source.data.polygons),
            **{key: str(self.directory/filename) for key, filename in (
                ('input', 'input.blend'), ('output', 'output.blend'),
                ('progress', 'progress.json'), ('result', 'result.json'))}}
        for key in ('proxy_faces', 'samples', 'auto_orientation', 'symmetric', 'plane',
                    'seed_axis', 'keep', 'tolerance', 'target'):
            self.job[key] = getattr(s, key)
        if operation == 'FINISH':
            self.job['report'] = json.loads(s.preview['scan_report'])
            initial = Matrix(self.job['report'].get('analysis_transform', Matrix.Identity(4)))
            self.job['transform'] = [list(row) for row in s.preview.matrix_world @ initial]
            self.job['report']['manual_transform'] = [list(row) for row in s.preview.matrix_world]
            if s.region_info:
                self.job['report']['selected_base'] = json.loads(s.region_info)

    def launch(self):
        # Snapshot IO is necessarily synchronous; costly decimation/fit are isolated.
        self.wm.scan_runtime.phase = 'Zapisywanie kopii skanu do obliczeń'
        bpy.data.libraries.write(self.job['input'], {self.source}, fake_user=True, compress=False)
        path = self.directory/'job.json'
        path.write_text(json.dumps(self.job), encoding='utf-8')
        self.log = (self.directory/'worker.log').open('w', encoding='utf-8')
        flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        self.process = subprocess.Popen([
            bpy.app.binary_path, '--background', '--factory-startup', '--threads', '2',
            '--disable-autoexec', '--python-exit-code', '1',
            '--python', str(Path(__file__).with_name('worker.py')), '--', str(path)],
            stdout=self.log, stderr=subprocess.STDOUT, creationflags=flags)

    def update(self):
        runtime = self.wm.scan_runtime
        runtime.elapsed = time.monotonic()-self.started
        try:
            payload = json.loads(Path(self.job['progress']).read_text(encoding='utf-8'))
        except (OSError, ValueError):
            payload = {}
        if payload:
            runtime.phase = payload['phase']
            runtime.indeterminate = payload.get('fraction') is None
            if not runtime.indeterminate:
                runtime.fraction = max(runtime.fraction, payload['fraction'])
            if payload.get('error'):
                runtime.error = payload['error']
        self.wm.progress_update(runtime.fraction*100)
        redraw()

    def complete(self, context):
        s = self.scene.scan_tools
        if self.source.name != self.source_name:
            raise RuntimeError('Nazwa źródła zmieniła się podczas obliczeń. Ponów operację.')
        if self.process.returncode != 0:
            message = self.wm.scan_runtime.error
            if not message:
                message = (self.directory/'worker.log').read_text(encoding='utf-8', errors='replace')[-6000:]
            raise RuntimeError(message or 'Proces Blendera zakończył się błędem')
        meta = json.loads(Path(self.job['result']).read_text(encoding='utf-8'))
        with bpy.data.libraries.load(self.job['output'], link=False) as (src, dst):
            dst.objects = [meta['object']]
        obj = dst.objects[0]
        self.collection.objects.link(obj)
        if self.operation == 'ANALYZE':
            s.source, s.preview = self.source, obj
            obj.color = (0.12, 0.55, 0.95, 1)
            self.source.hide_set(True)
            obj['scan_source_was_hidden'] = self.source_was_hidden
            create_live_mirror(context, s)
        else:
            s.preview.hide_set(True)
            for helper in (s.mirror, s.region):
                if helper:
                    helper.hide_set(True)
            text = bpy.data.texts.new(obj.name+'_report.json')
            text.write(json.dumps(meta['report'], ensure_ascii=False, indent=2))
        geometry.active_only(context, obj)
        if self.operation == 'FINISH':
            obj['scan_result'] = True
        self.wm.scan_runtime.phase = 'Gotowe'
        self.wm.scan_runtime.fraction = 1

    def close(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        if self.log:
            self.log.close()
        shutil.rmtree(self.directory, ignore_errors=True)
        self.wm.progress_end()
        self.wm.scan_runtime.busy = False
        self.wm.scan_runtime.cancel_requested = False


def start_job(operator, context, operation):
    global ACTIVE_JOB
    s = context.scene.scan_tools
    rt = context.window_manager.scan_runtime
    if rt.busy or ACTIVE_JOB is not None:
        operator.report({'ERROR'}, 'Operacja już trwa')
        return {'CANCELLED'}
    if context.mode != 'OBJECT':
        operator.report({'ERROR'}, 'Przejdź do Object Mode')
        return {'CANCELLED'}
    if operation == 'ANALYZE':
        source = context.active_object
        if source is None or source.type != 'MESH' or source.get('scan_generated'):
            operator.report({'ERROR'}, 'Zaznacz oryginalny skan')
            return {'CANCELLED'}
        if s.preview or s.mirror:
            operator.report({'ERROR'}, 'Najpierw usuń poprzedni podgląd')
            return {'CANCELLED'}
    else:
        source = s.source
        if not source or not s.preview:
            return {'CANCELLED'}
        report = json.loads(s.preview['scan_report'])
        if 'source_vertices' not in report or 'source_matrix' not in report:
            operator.report({'ERROR'}, 'Podgląd ze starszej wersji. Usuń go i przygotuj nową kopię.')
            return {'CANCELLED'}
        if ([list(row) for row in source.matrix_world] != report['source_matrix'] or
                len(source.data.vertices) != report['source_vertices'] or
                len(source.data.polygons) != report['source_polygons']):
            operator.report({'ERROR'}, 'Źródło zmieniono. Usuń podgląd i ponów analizę.')
            return {'CANCELLED'}
    if source.modifiers or source.constraints or source.parent or source.animation_data:
        operator.report({'ERROR'}, 'Źródło musi być samodzielną siatką bez modyfikatorów i constraints')
        return {'CANCELLED'}
    if source.library or len(source.data.polygons) < 4:
        operator.report({'ERROR'}, 'Wybierz lokalną siatkę z co najmniej 4 ściankami')
        return {'CANCELLED'}
    rt.busy, rt.cancel_requested, rt.error = True, False, ''
    rt.phase, rt.fraction, rt.elapsed, rt.indeterminate = 'Przygotowanie obliczeń', 0, 0, True
    context.window_manager.progress_begin(0, 100)
    try:
        job = BackgroundJob(operation, context, source, s)
        ACTIVE_JOB = job
        operator._job = job
        if bpy.app.background:
            # Test/CLI path drives the same worker. UI uses a non-blocking modal timer.
            job.launch()
            while job.process.poll() is None:
                job.update()
                time.sleep(0.1)
            job.update()
            job.complete(context)
            job.close()
            ACTIVE_JOB = None
            return {'FINISHED'}
        operator._timer = context.window_manager.event_timer_add(0.2, window=context.window)
        operator._started = False
        operator._ticks = 0
        context.window_manager.modal_handler_add(operator)
        redraw()
        return {'RUNNING_MODAL'}
    except Exception as exc:
        if ACTIVE_JOB:
            ACTIVE_JOB.close()
        ACTIVE_JOB = None
        rt.busy = False
        rt.error = str(exc)
        operator.report({'ERROR'}, str(exc)[-1000:])
        return {'CANCELLED'}


class BackgroundOperator:
    def modal(self, context, event):
        global ACTIVE_JOB
        if ACTIVE_JOB is not self._job:
            try:
                context.window_manager.event_timer_remove(self._timer)
            except (ReferenceError, RuntimeError):
                pass
            return {'CANCELLED'}
        if event.type == 'ESC' or self._job.wm.scan_runtime.cancel_requested:
            self._job.wm.scan_runtime.phase = 'Anulowano — źródło zachowane'
            self.cleanup(context)
            return {'CANCELLED'}
        if event.type != 'TIMER':
            # Keep UI readable/navigable; block edits in this viewport while a snapshot job runs.
            if context.area:
                for region in context.area.regions:
                    if region.type in {'UI', 'HEADER', 'TOOLS'} and (
                            region.x <= event.mouse_x < region.x+region.width and
                            region.y <= event.mouse_y < region.y+region.height):
                        return {'PASS_THROUGH'}
            if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'MOUSEMOVE'}:
                return {'PASS_THROUGH'}
            return {'RUNNING_MODAL'}
        self._ticks += 1
        if self._ticks < 2:
            return {'RUNNING_MODAL'}
        try:
            if not self._started:
                self._job.launch()
                self._started = True
            self._job.update()
            if self._job.process.poll() is None:
                return {'RUNNING_MODAL'}
            if context.scene != self._job.scene:
                raise RuntimeError('Aktywna scena zmieniła się podczas obliczeń. Ponów w oryginalnej scenie.')
            self._job.complete(context)
            self.cleanup(context)
            self.report({'INFO'}, 'Gotowe — wynik odebrany')
            return {'FINISHED'}
        except Exception as exc:
            context.window_manager.scan_runtime.error = str(exc)
            context.window_manager.scan_runtime.phase = 'Błąd — szczegóły w CX Scan Error'
            text = bpy.data.texts.new('CX Scan Error')
            text.write(str(exc))
            self.cleanup(context)
            self.report({'ERROR'}, str(exc)[-500:])
            return {'CANCELLED'}

    def cleanup(self, context):
        global ACTIVE_JOB
        context.window_manager.event_timer_remove(self._timer)
        self._job.close()
        ACTIVE_JOB = None
        redraw()

    def cancel(self, context):
        self.cleanup(context)


class SCAN_OT_analyze(BackgroundOperator, bpy.types.Operator):
    bl_idname = 'scan_tools.analyze'
    bl_label = '1. Przygotuj kopię roboczą'
    bl_description = 'Tworzy i redukuje kopię w osobnym procesie; źródło pozostaje zachowane'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        return start_job(self, context, 'ANALYZE')


class SCAN_OT_finish(BackgroundOperator, bpy.types.Operator):
    bl_idname = 'scan_tools.finish'
    bl_label = '4. Akceptuj i utwórz wynik'
    bl_description = 'Stosuje ustawienie kopii do oryginalnej geometrii i decymuje oddzielny wynik'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        return start_job(self, context, 'FINISH')


class SCAN_OT_cancel(bpy.types.Operator):
    bl_idname = 'scan_tools.cancel'
    bl_label = 'Anuluj obliczenia (Esc)'

    def execute(self, context):
        context.window_manager.scan_runtime.cancel_requested = True
        return {'FINISHED'}


class SCAN_OT_mirror(bpy.types.Operator):
    bl_idname = 'scan_tools.mirror'
    bl_label = 'Lustro na żywo: pokaż / ukryj'
    bl_description = 'Dokładne odbicie względem globalnego X=0 aktualizuje się podczas G/R/S'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.scan_tools
        if context.window_manager.scan_runtime.busy or not s.preview:
            return {'CANCELLED'}
        if s.mirror:
            s.mirror.hide_set(not s.mirror.hide_get())
        else:
            create_live_mirror(context, s)
        return {'FINISHED'}


def set_region(context, vertices, triangles, fit):
    s = context.scene.scan_tools
    clear_region(s)
    selected = triangles[fit['faces']]
    used, remap = np.unique(selected.reshape(-1), return_inverse=True)
    mesh = bpy.data.meshes.new('SCAN_BASE_PATCH')
    mesh.from_pydata(vertices[used].tolist(), [], remap.reshape(-1, 3).tolist())
    mesh.update()
    region = bpy.data.objects.new('SCAN_BASE_PATCH', mesh)
    context.collection.objects.link(region)
    region.parent = s.preview
    region.matrix_parent_inverse = Matrix.Identity(4)
    region.matrix_basis = Matrix.Identity(4)
    region.color = (0.05, 1.0, 0.18, 1)
    region.show_in_front = True
    region.hide_select = True
    region['scan_generated'] = True
    s.region, s.region_info = region, json.dumps(fit)
    object_colors(context)
    redraw()


class SCAN_OT_pick_plane(bpy.types.Operator):
    bl_idname = 'scan_tools.pick_plane'
    bl_label = '2. Kliknij płaską ściankę'
    bl_description = 'Kliknij kopię roboczą: spójny region wg normalnej i odległości od płaszczyzny'
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        s = context.scene.scan_tools
        if context.window_manager.scan_runtime.busy or not s.preview or context.mode != 'OBJECT':
            self.report({'ERROR'}, 'Przygotuj kopię i przejdź do Object Mode')
            return {'CANCELLED'}
        if not context.area or context.area.type != 'VIEW_3D':
            return {'CANCELLED'}
        self._area = context.area
        self._mirror = s.mirror
        self._mirror_hidden = self._mirror.hide_get() if self._mirror else True
        if self._mirror:
            self._mirror.hide_set(True)
        context.window.cursor_modal_set('CROSSHAIR')
        context.area.header_text_set('Kliknij wnętrze ścianki na kopii — Esc/PPM anuluje; środkowy przycisk obraca widok')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def cleanup(self, context):
        context.window.cursor_modal_restore()
        self._area.header_text_set(None)
        if self._mirror:
            self._mirror.hide_set(self._mirror_hidden)

    def modal(self, context, event):
        if event.type in {'ESC', 'RIGHTMOUSE'}:
            self.cleanup(context)
            return {'CANCELLED'}
        if event.type != 'LEFTMOUSE' or event.value != 'PRESS':
            return {'PASS_THROUGH'}
        from bpy_extras import view3d_utils
        region = next((r for r in self._area.regions if r.type == 'WINDOW'), None)
        coord = (event.mouse_x-region.x, event.mouse_y-region.y)
        if not (0 <= coord[0] < region.width and 0 <= coord[1] < region.height):
            return {'RUNNING_MODAL'}
        obj = context.scene.scan_tools.preview
        try:
            inv = obj.matrix_world.inverted()
            origin = view3d_utils.region_2d_to_origin_3d(region, self._area.spaces.active.region_3d, coord)
            direction = view3d_utils.region_2d_to_vector_3d(region, self._area.spaces.active.region_3d, coord)
            hit, _, _, polygon = obj.ray_cast(inv @ origin, (inv.to_3x3() @ direction).normalized())
            if not hit:
                return {'RUNNING_MODAL'}
            vertices, triangles = geometry.arrays(obj.data)
            seed = next(i for i, tri in enumerate(obj.data.loop_triangles) if tri.polygon_index == polygon)
            s = context.scene.scan_tools
            fit = core.planar_region(vertices, triangles, seed, s.region_angle, s.region_distance)
            set_region(context, vertices, triangles, fit)
            self.cleanup(context)
            self.report({'INFO'}, f"Obszar: {len(fit['faces'])} trójkątów. Oceń zaznaczenie i płaskość.")
            return {'FINISHED'}
        except Exception as exc:
            self.cleanup(context)
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}

    def cancel(self, context):
        self.cleanup(context)


class SCAN_OT_selected_plane(bpy.types.Operator):
    bl_idname = 'scan_tools.selected_plane'
    bl_label = 'Płaszczyzna z zaznaczonych ścianek'
    bl_description = 'W Edit Mode zaznacz region (np. Circle Select), a następnie dopasuj bazę'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.scan_tools
        if context.window_manager.scan_runtime.busy or not s.preview or context.active_object != s.preview:
            return {'CANCELLED'}
        obj = s.preview
        if context.mode != 'EDIT_MESH':
            self.report({'ERROR'}, 'Wejdź w Edit Mode kopii i zaznacz ścianki')
            return {'CANCELLED'}
        obj.update_from_editmode()
        verts, triangles = geometry.arrays(obj.data)
        indices = [i for i, tri in enumerate(obj.data.loop_triangles) if obj.data.polygons[tri.polygon_index].select]
        try:
            fit = core.triangle_plane(verts, triangles[indices])
            scale = np.linalg.norm(np.ptp(verts, axis=0))
            fit.update(faces=indices, rms_relative=fit['rms']/scale,
                       max_deviation_relative=fit['max_deviation']/scale)
            bpy.ops.object.mode_set(mode='OBJECT')
            set_region(context, verts, triangles, fit)
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}


class SCAN_OT_align_plane(bpy.types.Operator):
    bl_idname = 'scan_tools.align_plane'
    bl_label = '3. Wyrównaj bazę do XY / Z=0'
    bl_description = 'Dopasowana płaszczyzna trafia do Z=0; dół/góra wybiera kierunek normalnej'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.scan_tools
        if context.window_manager.scan_runtime.busy or not s.preview or not s.region_info or context.mode != 'OBJECT':
            return {'CANCELLED'}
        fit = json.loads(s.region_info)
        matrix = s.preview.matrix_world.copy()
        normal = (matrix.to_3x3().inverted().transposed() @ Vector(fit['normal'])).normalized()
        center = matrix @ Vector(fit['center'])
        target = Vector((0, 0, -1 if s.plane_direction == 'DOWN' else 1))
        rotate = normal.rotation_difference(target).to_matrix().to_4x4()
        correction = (Matrix.Translation((0, 0, -center.z)) @ Matrix.Translation(center) @
                      rotate @ Matrix.Translation(-center))
        s.preview.matrix_world = correction @ matrix
        fit['aligned_direction'] = s.plane_direction
        s.region_info = json.dumps(fit)
        geometry.active_only(context, s.preview)
        context.view_layer.update()
        self.report({'INFO'}, 'Baza w XY. Symetrię dopracuj G X i R Z, obserwując lustro.')
        return {'FINISHED'}


class SCAN_OT_clear_region(bpy.types.Operator):
    bl_idname = 'scan_tools.clear_region'
    bl_label = 'Usuń zaznaczenie bazy'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.window_manager.scan_runtime.busy:
            return {'CANCELLED'}
        clear_region(context.scene.scan_tools)
        return {'FINISHED'}


class SCAN_OT_clear(bpy.types.Operator):
    bl_idname = 'scan_tools.clear'
    bl_label = 'Usuń podgląd / wróć do źródła'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.scan_tools
        if context.window_manager.scan_runtime.busy or context.mode != 'OBJECT':
            return {'CANCELLED'}
        clear_region(s)
        for obj in (s.mirror, s.mirror_root, s.preview):
            if obj:
                geometry.remove_object(obj)
        s.mirror = s.mirror_root = s.preview = None
        if s.source:
            geometry.active_only(context, s.source)
        return {'FINISHED'}


class SCAN_PT_panel(bpy.types.Panel):
    bl_label = 'CadXpert Scan Tools 0.2.0'
    bl_idname = 'SCAN_PT_tools'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Scan Tools'

    def draw(self, context):
        layout = self.layout
        s, rt = context.scene.scan_tools, context.window_manager.scan_runtime
        if rt.busy:
            box = layout.box()
            box.label(text=rt.phase)
            box.progress(factor=rt.fraction, type='BAR', text=f'Etapy zadania: {rt.fraction:.0%}')
            if rt.indeterminate:
                box.progress(factor=(rt.elapsed % 2)/2, type='RING', text='Praca trwa — ETA nieznane')
            box.label(text=f'Czas pracy: {int(rt.elapsed)//60}:{int(rt.elapsed)%60:02d}')
            box.operator('scan_tools.cancel', icon='CANCEL')
            return
        if rt.error:
            layout.label(text='Błąd ostatniej operacji — sprawdź CX Scan Error', icon='ERROR')
        prep = layout.box()
        prep.prop(s, 'proxy_faces')
        prep.prop(s, 'auto_orientation')
        if s.auto_orientation:
            prep.prop(s, 'symmetric')
            prep.prop(s, 'seed_axis')
            prep.prop(s, 'plane')
            prep.prop(s, 'samples')
            prep.prop(s, 'keep')
            prep.prop(s, 'tolerance')
        prep.operator('scan_tools.analyze')
        if s.preview:
            base = layout.box()
            base.label(text='Baza: kliknij region lub zaznacz ścianki')
            base.prop(s, 'region_angle')
            base.prop(s, 'region_distance')
            base.operator('scan_tools.pick_plane')
            base.operator('scan_tools.selected_plane')
            if s.region_info:
                fit = json.loads(s.region_info)
                base.label(text=f"Obszar: {len(fit['faces'])} trójkątów")
                base.label(text=f"RMS: {fit['rms']:.6g} BU")
                base.label(text=f"Max odchyłka: {fit['max_deviation']:.6g} BU")
                base.label(text=f"RMS / przekątna: {fit['rms_relative']:.5%}")
                base.prop(s, 'plane_direction')
                base.operator('scan_tools.align_plane')
                base.operator('scan_tools.clear_region')
            layout.operator('scan_tools.mirror')
            layout.label(text='Lustro X=0 działa na żywo podczas G/R/S')
            layout.label(text='Po bazowaniu: G X i R Z zachowują XY')
            layout.prop(s, 'target')
            layout.operator('scan_tools.finish')
            layout.operator('scan_tools.clear')
        elif rt.phase:
            layout.label(text=rt.phase)


CLASSES = (ScanSettings, ScanRuntime, SCAN_OT_analyze, SCAN_OT_finish, SCAN_OT_cancel,
           SCAN_OT_mirror, SCAN_OT_pick_plane, SCAN_OT_selected_plane,
           SCAN_OT_align_plane, SCAN_OT_clear_region, SCAN_OT_clear, SCAN_PT_panel)


@persistent
def stop_on_load(_):
    global ACTIVE_JOB
    if ACTIVE_JOB:
        ACTIVE_JOB.close()
        ACTIVE_JOB = None


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.scan_tools = PointerProperty(type=ScanSettings)
    bpy.types.WindowManager.scan_runtime = PointerProperty(type=ScanRuntime)
    bpy.app.handlers.load_pre.append(stop_on_load)
    if hasattr(bpy.app.handlers, 'quit_pre'):
        bpy.app.handlers.quit_pre.append(stop_on_load)


def unregister():
    stop_on_load(None)
    for handlers in (bpy.app.handlers.load_pre, getattr(bpy.app.handlers, 'quit_pre', [])):
        if stop_on_load in handlers:
            handlers.remove(stop_on_load)
    del bpy.types.WindowManager.scan_runtime
    del bpy.types.Scene.scan_tools
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
