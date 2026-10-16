"""Build an installable extension ZIP, with files directly at its root."""
from pathlib import Path
import zipfile
import tomllib
root = Path(__file__).resolve().parents[1]
source = root/'scan_tools'
manifest = tomllib.loads((source/'blender_manifest.toml').read_text())
out = root/'dist'/f"{manifest['id']}-{manifest['version']}.zip"
out.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(source.iterdir()):
        if path.is_file() and path.suffix in ('.py', '.toml'):
            archive.write(path, path.name)
    archive.write(root/'LICENSE', 'LICENSE')
print(out)
