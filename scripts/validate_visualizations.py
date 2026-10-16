"""Reconcile visual aggregates against full and order-only analytical fixtures."""
import json
from pathlib import Path
import subprocess
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.analytics import analyze
from app.seed import seed_data
from app.importers import import_file

full = seed_data()
full['_meta'] = {'as_of': '2026-10-14', 'name': 'Visual regression', 'synthetic': True, 'holidays': ['2026-10-20']}
upload = import_file((ROOT / 'examples/sample-orders.csv').read_bytes(), 'sample-orders.csv')
small = upload['data']
small['_meta'] = upload['meta']
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / 'fixtures.json'
    path.write_text(json.dumps([analyze(full), analyze(small)]))
    subprocess.run(['node', str(ROOT / 'tests/visualizations.cjs'), str(path)], check=True)
