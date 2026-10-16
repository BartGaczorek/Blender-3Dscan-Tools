# Development rules
- Experimental Blender extension; preserve original mesh and source transforms.
- Use relative imports. No network calls, external services, AI models or runtime pip installation.
- Geometry math belongs in scan_tools/core.py; Blender interaction in __init__.py.
- Algorithm changes require synthetic regression tests and Blender smoke checks.
- Never equate a low symmetry residual with proof of intended design symmetry.
- Count triangles, not only polygons. Decimation target is approximate, not a dimensional tolerance.
- Do not add user scans to Git. Use procedural fixtures or approved small public samples.
- Update README and CHANGELOG when behavior changes. Do not claim unexecuted tests passed.
