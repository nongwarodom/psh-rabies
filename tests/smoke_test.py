"""Headless smoke test of every dashboard page and its main widget options.

Run:  python tests/smoke_test.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from streamlit.testing.v1 import AppTest  # noqa: E402

PAGES = ["views/overview.py", "views/map.py", "views/people.py", "views/animals.py",
         "views/osm.py", "views/area.py", "views/quality.py"]

failed = False


def report(at, label):
    global failed
    if at.exception:
        failed = True
        print(f"FAIL {label}:")
        for e in at.exception:
            print("   ", e.message, "\n", "\n".join(e.stack_trace[-6:]))
        return False
    return True


for page in PAGES:
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.run()
    at.switch_page(page).run()
    ok = report(at, page)

    # exercise every option of every radio / selectbox on the page
    n_variants = 0
    for kind in ("radio", "selectbox"):
        widgets = getattr(at, kind)
        for i in range(len(widgets)):
            w = getattr(at, kind)[i]
            for opt in list(w.options):
                getattr(at, kind)[i].set_value(opt).run()
                n_variants += 1
                ok &= report(at, f"{page} [{kind} '{w.label}' = {opt}]")
    for i in range(len(at.toggle)):
        at.toggle[i].set_value(not at.toggle[i].value).run()
        n_variants += 1
        ok &= report(at, f"{page} [toggle {at.toggle[i].label}]")
    if ok:
        print(f"OK   {page}  ({n_variants} widget variants tested)")

sys.exit(1 if failed else 0)
