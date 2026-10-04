"""Queue an ingest job for specific images only (used for the 3-image smoke test).

    .venv\\Scripts\\python scripts/enqueue_ingest.py --only red_fox_01.jpg gray_wolf_01.jpg ambiguous_02.jpg

This is deliberately a CLI script, not an API parameter: the public API always processes the whole
corpus. The job is created through the same repository the API uses, and the worker runs it exactly
like any other ingest job.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402
from app.db.session import session_scope  # noqa: E402
from app.repositories import jobs as jobs_repo  # noqa: E402


def enqueue_only(filenames: list[str], images_dir: Path) -> int:
    missing = [name for name in filenames if not (images_dir / name).is_file()]
    if missing:
        raise SystemExit(f"Not found in {images_dir}: {', '.join(missing)}")
    with session_scope() as s:
        job, _ = jobs_repo.create_job(s, jobs_repo.INGEST_IMAGES, {"only": sorted(set(filenames))})
        return job.id


def main() -> None:
    parser = argparse.ArgumentParser(description="Queue an ingest job for specific images.")
    parser.add_argument("--only", nargs="+", required=True, metavar="FILENAME")
    args = parser.parse_args()
    job_id = enqueue_only(args.only, get_settings().images_dir)
    print(f"Queued job {job_id} for: {', '.join(sorted(set(args.only)))}")


if __name__ == "__main__":
    main()
