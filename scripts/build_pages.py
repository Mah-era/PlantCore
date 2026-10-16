"""Package the interactive browser build for GitHub Pages."""

from pathlib import Path
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "dist"
if TARGET.exists():
    shutil.rmtree(TARGET)
TARGET.mkdir()

for filename in ("app.css", "app.js", "enterprise.js", "visualizations.js"):
    shutil.copy2(ROOT / "web" / filename, TARGET / filename)
shutil.copy2(ROOT / "examples" / "sample-orders.csv", TARGET / "sample-orders.csv")
for filename in ("browser-adapter.js", "python-worker.js"):
    shutil.copy2(ROOT / "site" / filename, TARGET / filename)

html = (ROOT / "web" / "index.html").read_text()
html = html.replace('href="/app.css"', 'href="./app.css"')
html = html.replace('<script src="/app.js"></script>',
                    '<script src="./browser-adapter.js"></script>\n    <script src="./app.js"></script>')
html = html.replace('src="/enterprise.js"', 'src="./enterprise.js"')
html = html.replace('src="/visualizations.js"', 'src="./visualizations.js"')
html = html.replace("PlantCore / Operations workspace <b>02</b>",
                    "PlantCore / Browser workspace <b>03</b>")
html = html.replace("Local planning workspace; authentication not configured",
                    "Private browser workspace; data stays on this device")
(TARGET / "index.html").write_text(html)
(TARGET / ".nojekyll").write_text("")

py = TARGET / "py"
files = sorted(
    [*(path.relative_to(ROOT) for path in (ROOT / "app").glob("*.py")),
     *(path.relative_to(ROOT) for path in (ROOT / "test-files").glob("*.json")),
     Path("examples/sample-orders.csv")],
    key=str,
)
for relative in files:
    destination = py / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / relative, destination)
(py / "manifest.json").write_text(json.dumps([str(path) for path in files]))
print(f"Built {TARGET} with {len(files)} Python and scenario files")
