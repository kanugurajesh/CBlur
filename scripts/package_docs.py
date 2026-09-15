"""Include usage instructions and installed dependency license files in the build."""
import importlib.metadata
from pathlib import Path
import shutil
import sys

root = Path(__file__).resolve().parents[1]
destination = root / (sys.argv[1] if len(sys.argv) > 1 else "dist/CBlur")
if not (destination / "CBlur.exe").exists():
    raise SystemExit("Build CBlur.exe first.")
for name in ("README.md", "THIRD_PARTY.md", "VALIDATION.md"):
    shutil.copyfile(root / name, destination / name)
for distribution in importlib.metadata.distributions():
    for entry in distribution.files or ():
        path = Path(str(entry))
        if not any(word in path.name.upper() for word in ("LICENSE", "COPYING", "NOTICE", "COPYRIGHT")):
            continue
        source = distribution.locate_file(entry)
        if not source.is_file() or source.suffix in (".py", ".pyc", ".pyd"):
            continue
        name = distribution.metadata.get("Name", "dependency")
        target = destination / "third_party_licenses" / name / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != source.read_bytes():
            target = target.with_name(path.parent.name + "_" + path.name)
        shutil.copyfile(source, target)
print("Usage instructions and component license files included.")
