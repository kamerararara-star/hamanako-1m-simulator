from __future__ import annotations
"""Player-behaviour layer for Hamanako Ver.2.

Profiles are deliberately conservative.  A profile is only applied when real
history has been supplied.  Otherwise the engine falls back to course/class
priors instead of inventing a player's 'quirk'.

Expected profile keys (0..1): attack, defend, resist, retreat, reaction,
start, change_after_failure, pickup, inside, outside.
"""
import json
from pathlib import Path

PROFILE_PATH = Path(__file__).with_name('data') / 'player_profiles.json'

DEFAULT = {
    'attack': 0.50, 'defend': 0.50, 'resist': 0.50, 'retreat': 0.50,
    'reaction': 0.50, 'start': 0.50, 'change_after_failure': 0.50,
    'pickup': 0.50, 'inside': 0.50, 'outside': 0.50,
    'confidence': 0.0,
}


def _clamp(v):
    try:
        return max(0.0, min(1.0, float(v)))
    except Exception:
        return 0.5


def load_profiles():
    if not PROFILE_PATH.exists():
        return {}
    try:
        data = json.loads(PROFILE_PATH.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


PROFILES = load_profiles()


def get_profile(registration_no=None, racer_name=None, racer_class=None):
    key = str(registration_no or '').strip()
    p = PROFILES.get(key) or PROFILES.get(str(racer_name or '').strip()) or {}
    out = dict(DEFAULT)
    for k, v in p.items():
        if k in out:
            out[k] = _clamp(v)
    # Weak course/class prior only; never treated as a player-specific quirk.
    cls = str(racer_class or '')
    if out['confidence'] <= 0:
        if cls == 'A1':
            out.update({'attack':0.54,'defend':0.56,'reaction':0.54,'start':0.56})
        elif cls == 'A2':
            out.update({'attack':0.52,'defend':0.53,'reaction':0.52,'start':0.53})
        elif cls in ('B2','B3'):
            out.update({'attack':0.48,'defend':0.48,'reaction':0.48,'start':0.48})
    return out
