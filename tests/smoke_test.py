"""Headless smoke test of every dashboard page (python tests/smoke_test.py)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from streamlit.testing.v1 import AppTest  # noqa: E402

PAGES = ["views/overview.py", "views/map.py", "views/people.py", "views/animals.py",
         "views/area.py", "views/quality.py"]

failed = False
for page in PAGES:
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90)
    at.run()
    at.switch_page(page).run()
    if at.exception:
        failed = True
        print(f"FAIL {page}:")
        for e in at.exception:
            print("   ", e.message, "\n", "\n".join(e.stack_trace[-6:]))
    else:
        print(f"OK   {page}  (titles: {[t.value for t in at.title]})")
sys.exit(1 if failed else 0)
