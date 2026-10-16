"""Reuse a saved production response while its live source is unchanged."""
import json
import os
from datetime import datetime, timezone, timedelta
from .config import ROOT
from .upload_checkpoint import checkpoint

PATH = ROOT / 'validated_draft.json'


def load(focus, sources, used, avoid=''):
    if os.getenv('PUBLISH_UPLOAD_CHECKPOINTS') != '1' or not PATH.exists():
        return None
    saved = json.loads(PATH.read_text(encoding='utf-8'))
    data = saved.get('data', {})
    if (saved.get('focus') != focus or saved.get('model') != os.getenv('GROQ_MODEL', 'openai/gpt-oss-120b')
            or data.get('generation_mode') != 'prompt_first_v1'
            or data.get('topic') in used or (avoid and data.get('topic') in avoid)):
        return None
    age = datetime.now(timezone.utc) - datetime.fromisoformat(saved['saved_at'])
    if not timedelta(0) <= age <= timedelta(hours=24):
        return None
    source = data.get('reference_source')
    if not source or not any(s.get('id') == source.get('id') and s.get('text') == source.get('text') for s in sources):
        return None
    return data


def save(focus, data):
    if os.getenv('PUBLISH_UPLOAD_CHECKPOINTS') != '1':
        return
    PATH.write_text(json.dumps({'focus': focus, 'model': os.getenv('GROQ_MODEL', 'openai/gpt-oss-120b'),
                               'saved_at': datetime.now(timezone.utc).isoformat(), 'data': data}, ensure_ascii=False, indent=2), encoding='utf-8')
    checkpoint([PATH])


def clear():
    if os.getenv('PUBLISH_UPLOAD_CHECKPOINTS') == '1' and PATH.exists():
        PATH.write_text('{}', encoding='utf-8')
        checkpoint([PATH])
