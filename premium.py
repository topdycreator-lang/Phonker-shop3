import re


def _compile(mapping):
    keys = sorted((k.replace("\ufe0f", "") for k in mapping), key=len, reverse=True)
    if not keys:
        return None
    return re.compile("|".join(re.escape(k) + "\ufe0f?" for k in keys))


def _lookup(mapping):
    return {k.replace("\ufe0f", ""): v for k, v in mapping.items()}


def find_spans(text, mapping):
    rx = _compile(mapping)
    if not rx or not text:
        return []
    ids = _lookup(mapping)
    out = []
    for m in rx.finditer(text):
        offset = len(text[:m.start()].encode("utf-16-le")) // 2
        length = len(m.group(0).encode("utf-16-le")) // 2
        out.append((offset, length, ids[m.group(0).replace("\ufe0f", "")]))
    return out


def split_button_text(text, mapping):
    rx = _compile(mapping)
    if not rx:
        return None
    m = rx.match(text)
    if not m:
        return None
    rest = text[m.end():].lstrip()
    if not rest:
        return None
    return rest, _lookup(mapping)[m.group(0).replace("\ufe0f", "")]
