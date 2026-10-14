"""Retain real received text and validation feedback without changing content."""
import json
import logging
import os
from pathlib import Path
import time
from .config import OUTPUT_DIR
from .upload_checkpoint import checkpoint

log = logging.getLogger(__name__)


def received(package, sources, attempt):
    if os.getenv('PUBLISH_UPLOAD_CHECKPOINTS') != '1':
        return None
    try:
        folder = OUTPUT_DIR / 'text-audit'
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f'{time.time_ns()}-attempt-{attempt}.json'
        document = {'run_id': os.getenv('GITHUB_RUN_ID', 'local'), 'attempt': attempt,
                    'stage': 'received_unvalidated', 'raw_groq_package': package,
                    'reference_sources': sources}
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding='utf-8')
        update(path, 'received_unvalidated')
        return path
    except (OSError, ValueError) as exc:
        log.warning('Text audit not saved: %s', type(exc).__name__)
        return None


def update(path, stage, *, error=None, verdict=None):
    if path is None:
        return
    try:
        document = json.loads(Path(path).read_text(encoding='utf-8'))
        document.update(stage=stage, error=str(error) if error is not None else None)
        if verdict is not None:
            document['editorial_review'] = verdict
        Path(path).write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding='utf-8')
        # This is a diagnostic snapshot, never an upload receipt or fallback script.
        progress = Path('script_progress.json')
        progress.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding='utf-8')
        checkpoint([progress], log)
    except (OSError, ValueError) as exc:
        log.warning('Text audit progress not saved: %s', type(exc).__name__)
