"""Audit saved EM/AF logs without making model calls."""

import json
import sys
from collections import Counter
from pathlib import Path

from zipfile_zstd import ZipFile


root = Path(sys.argv[1])
rows = []
for path in sorted(root.rglob("*.eval")):
    with ZipFile(path) as archive:
        header = json.loads(archive.read("header.json"))
        samples = [json.loads(archive.read(name)) for name in archive.namelist()
                   if name.startswith("samples/") and name.endswith(".json")]
    row = dict(model=header["eval"]["model"], task=header["eval"]["task"],
               status=header["status"], path=str(path), saved=len(samples),
               errors=sum(bool(s.get("error")) for s in samples), scores={})
    for score in header.get("results", {}).get("scores", []):
        name = score["name"]
        scorer = score.get("scorer", name)
        values = [s.get("scores", {}).get(scorer) for s in samples if not s.get("error")]
        reasons = Counter(value.get("reason") for value in values if value is not None)
        row["scores"][name] = dict(
            scored=sum(value is not None and not value.get("reason") for value in values),
            exclusions={k: v for k, v in reasons.items() if k},
            metrics={k: v["value"] for k, v in score["metrics"].items()},
        )
    rows.append(row)
(root / "summary.json").write_text(json.dumps(rows, indent=2) + "\n")
print(json.dumps(rows, indent=2))
