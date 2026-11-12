"""Reading/writing the evaluation's CSV and JSONL files."""

import csv
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Outlet:
    name: str
    domain: str
    allsides_rating: str = ""  # e.g. "Lean Left"; filled by hand from allsides.com
    allsides_accessed: str = ""
    allsides_url: str = ""  # page the rating was read from
    adfontes_bias: float | None = None  # numeric bias score; filled from adfontesmedia.com
    adfontes_accessed: str = ""
    adfontes_url: str = ""


def load_outlets(path: Path) -> list[Outlet]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    outlets = []
    for row in rows:
        adfontes = (row.get("adfontes_bias") or "").strip()
        outlets.append(
            Outlet(
                name=row["name"].strip(),
                domain=row["domain"].strip().lower(),
                allsides_rating=(row.get("allsides_rating") or "").strip(),
                allsides_accessed=(row.get("allsides_accessed") or "").strip(),
                allsides_url=(row.get("allsides_url") or "").strip(),
                adfontes_bias=float(adfontes) if adfontes else None,
                adfontes_accessed=(row.get("adfontes_accessed") or "").strip(),
                adfontes_url=(row.get("adfontes_url") or "").strip(),
            )
        )
    return outlets


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def append_jsonl(path: Path, records: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
