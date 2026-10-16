"""Content fingerprint for P2 conversions; callers retain immutable inputs."""
import hashlib
import json


COMPONENTS = frozenset({"input", "parser", "converter", "config", "profile", "schema", "mapping"})


def fingerprint(components):
    """Every component is a SHA256 of bytes or a canonical configuration value.

    Require the complete set: silently omitting conversion code was a historical
    stale-cache failure. Names/paths/mtime alone are not content fingerprints.
    """
    if set(components) != COMPONENTS:
        raise ValueError("cache fingerprint requires input/parser/converter/config/profile/schema/mapping")
    import re
    if not all(isinstance(value, str) and re.fullmatch("[a-f0-9]{64}", value) for value in components.values()):
        raise ValueError("cache components must be SHA256 fingerprints")
    canonical = json.dumps({"cache_schema": "baram.p2.cache/1", "components": components},
                           sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
