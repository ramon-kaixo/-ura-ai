import sys
from pathlib import Path

# Guard: remove editable install finder to guarantee single import source.
for _f in list(sys.meta_path):
    if "__editable" in str(_f):
        sys.meta_path.remove(_f)
for _h in list(sys.path_hooks):
    if "__editable" in str(_h):
        sys.path_hooks.remove(_h)
_repo = str(Path(__file__).resolve().parent.parent)
if _repo not in sys.path:
    sys.path.insert(0, _repo)
del _f, _h, _repo
