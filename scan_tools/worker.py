"""Executed by a separate Blender, never bpy from a Python thread."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import traceback

import bpy
import numpy as np
from mathutils import Matrix
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent


def module(name):
    spec = importlib.util.spec_from_file_location('cx_worker_'+name, HERE/(name+'.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


core = module('core')
geometry = module('geometry')


def run(job):
    progress_path = Path(job['progress'])
    def progress(phase, fraction=None, **extra):
        payload = {'phase': phase, 'fraction': fraction, 'updated': time.time(), **extra}
        temporary = progress_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        os.replace(temporary, progress_path)

    try:
        progress('Wczytywanie kopii skanu', 0.08)
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        with bpy.data.libraries.load(job['input'], link=False) as (src, dst):
            dst.objects = [job['source_name']]
        obj = dst.objects[0]
        bpy.context.scene.collection.objects.link(obj)
        geometry.active_only(bpy.context, obj)
        report = job.get('report', {})
        report.update(version='0.2.0', source=job['source_name'])
        if job['operation'] == 'ANALYZE':
            geometry.bake(obj, Matrix(job['source_matrix']))
            progress('Decymacja kopii roboczej — czas nieznany', None)
            before, after = geometry.decimate(bpy.context, obj, job['proxy_faces'])
            progress('Próbkowanie powierzchni', 0.4)
            verts, triangles = geometry.arrays(obj.data)
            points = core.sample_surface(verts, triangles, job['samples'])
            report.update(proxy_triangles=after, original_triangles=before,
                          source_matrix=job['source_matrix'],
                          source_vertices=job['source_vertices'], source_polygons=job['source_polygons'],
                          samples=job['samples'], auto_orientation=job['auto_orientation'])
            transform = np.eye(4)
            transform[:3, 3] = -(verts.min(axis=0)+verts.max(axis=0))*0.5
            if job['auto_orientation']:
                plane = None
                if job['plane']:
                    progress('Eksperymentalne wykrywanie ścianki', 0.45)
                    plane, _, support, rms = core.fit_plane(points, job['tolerance'])
                    report.update(plane_support=support, plane_rms_in_scene_units=rms)
                    if support < 0.12:
                        plane = None
                symmetry = None
                if job['symmetric']:
                    progress('Budowanie indeksu powierzchni', 0.5)
                    tree = BVHTree.FromPolygons(verts.tolist(), triangles.tolist(), all_triangles=True)
                    def distance(coords):
                        return np.array([tree.find_nearest(p)[3] for p in coords])
                    _, axes = core.pca(points)
                    starts = list(axes.T) if job['seed_axis'] == 'AUTO' else [np.eye(3)['XYZ'.index(job['seed_axis'])]]
                    def symmetry_progress(fraction, phase):
                        progress(phase, 0.52+fraction*0.38)
                    n, d, scores = core.symmetry_fit(points, distance, starts, job['keep'], symmetry_progress)
                    symmetry = (n, d)
                    report.update(scores, symmetry_normal=n.tolist(), symmetry_offset=d)
                transform = core.orientation(points, plane, symmetry)
            # Bake the initial suggestion into the proxy so its origin is at the
            # centered model, rather than at a transformed old world origin.
            report['analysis_transform'] = transform.tolist()
            geometry.bake(obj, Matrix(transform.tolist()))
            obj.name = job['source_name']+'_ANALYSIS'
        else:
            geometry.bake(obj, Matrix(job['transform']) @ Matrix(job['source_matrix']))
            progress('Końcowa decymacja oryginalnej geometrii — czas nieznany', None)
            before, after = geometry.decimate(bpy.context, obj, job['target'])
            report.update(transform_world=job['transform'], result_triangles=after,
                          original_triangles=before, target_triangles=job['target'],
                          metrics_note='Automatic fit scores, if present, precede manual corrections')
            obj.name = job['source_name']+'_READY'
        obj['scan_generated'] = True
        obj['scan_report'] = json.dumps(report, ensure_ascii=False)
        progress('Zapisywanie wyniku do odebrania', 0.95)
        bpy.data.libraries.write(job['output'], {obj}, fake_user=True, compress=False)
        Path(job['result']).write_text(json.dumps({'object': obj.name, 'report': report}), encoding='utf-8')
        progress('Gotowe do odebrania', 1.0, done=True)
    except Exception:
        message = traceback.format_exc()
        progress('Błąd obliczeń', None, error=message)
        print(message, file=sys.stderr)
        raise


if __name__ == '__main__':
    run(json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf-8')))
