"""Tag Rules node.

Receives the tag string produced by the Gelbooru nodes (``imgtags``: comma
separated tags, one post per line) and rewrites it with a user defined rule
table:

* **Replace** - every row has a "find" side and a "replace with" side. Both
  sides may hold several comma separated tags, so one tag can become many
  (``1girl -> 1boy, male_focus``) and many can become one
  (``1girl, solo -> 1boy``). An empty "replace with" side simply deletes the
  matched tags.
* **Remove** - every row is a tag (or a wildcard such as ``*_background``)
  that is dropped from the result, e.g. ``censored``.

The rule table is edited in the node UI (``web/tag_rules.js``) and stored as
JSON inside the ``rules_json`` widget.  That widget is a plain STRING, so a
workflow keeps working - and can be driven from the API - even when the
JavaScript UI is not loaded.
"""

import json
import re

RULES_VERSION = 1
DEFAULT_RULES_JSON = json.dumps({"version": RULES_VERSION, "replace": [], "remove": []})

MATCH_MODE_ANY = "All tags (any order)"
MATCH_MODE_SEQUENCE = "Exact sequence"
MATCH_MODES = [MATCH_MODE_ANY, MATCH_MODE_SEQUENCE]

_BRACKET_PAIRS = {"(": ")", "[": "]", "{": "}"}
_WEIGHT_SUFFIX = re.compile(r"^(?P<inner>.*?)\s*:\s*-?[0-9]*\.?[0-9]+\s*$")
_TAG_SPLIT = re.compile(r"[,\n\r]+")


def _unwrap_tag(tag):
    """Strip wrapping ``()`` / ``[]`` / ``{}`` used for prompt weights."""
    value = str(tag).strip()
    for _ in range(16):
        if len(value) >= 2 and value[0] in _BRACKET_PAIRS and value[-1] == _BRACKET_PAIRS[value[0]]:
            value = value[1:-1].strip()
        else:
            break
    return value


def _strip_weight(tag):
    """``(long_hair:1.2)`` -> ``long_hair``; plain tags are returned as-is."""
    value = _unwrap_tag(tag)
    match = _WEIGHT_SUFFIX.match(value)
    if match:
        value = match.group("inner").strip()
    return value


def _normalize(value, case_sensitive=False, underscore_equivalent=True):
    """Build the comparison key used by every rule."""
    text = _strip_weight(value)
    if underscore_equivalent:
        text = text.replace("_", " ")
    text = " ".join(text.split())
    return text if case_sensitive else text.lower()


class _TagPattern:
    """One entry of a rule; ``*`` matches any run of characters."""

    __slots__ = ("value", "_regex")

    def __init__(self, value):
        self.value = value
        self._regex = None
        if "*" in value:
            self._regex = re.compile("^" + re.escape(value).replace(r"\*", ".*") + "$")

    @property
    def is_wildcard(self):
        return self._regex is not None

    def matches(self, key):
        if self._regex is not None:
            return self._regex.match(key) is not None
        return key == self.value


def _split_tags(value):
    """Split a cell into individual tags (commas and newlines separate them)."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        parts = []
        for item in value:
            parts.extend(_split_tags(item))
        return parts
    return [part.strip() for part in _TAG_SPLIT.split(str(value)) if part.strip()]


def _parse_rules(rules_json):
    """Return ``([(find_tags, replace_tags), ...], remove_tags)``."""
    raw = {}
    if isinstance(rules_json, dict):
        raw = rules_json
    elif isinstance(rules_json, str) and rules_json.strip():
        try:
            raw = json.loads(rules_json)
        except Exception as exc:  # noqa: BLE001 - never break a workflow over bad JSON
            print(f"[TagRules] Ignoring malformed rules JSON ({exc}); text passed through unchanged.")
            return [], []
    if isinstance(raw, list):
        raw = {"replace": raw}
    if not isinstance(raw, dict):
        return [], []

    replace_raw = raw.get("replace")
    if replace_raw is None:
        replace_raw = raw.get("replacements")
    if replace_raw is None:
        replace_raw = raw.get("rules")
    if isinstance(replace_raw, dict):
        replace_raw = [{"from": key, "to": value} for key, value in replace_raw.items()]
    elif isinstance(replace_raw, str):
        replace_raw = [replace_raw]
    if not isinstance(replace_raw, (list, tuple)):
        replace_raw = []

    replacements = []
    for item in replace_raw:
        if isinstance(item, str):
            if "=>" not in item:
                continue
            find_side, replace_side = item.split("=>", 1)
        elif isinstance(item, dict):
            find_side = item.get("from", item.get("find", ""))
            replace_side = item.get("to", item.get("replace", ""))
        else:
            continue
        find_tags = _split_tags(find_side)
        if find_tags:
            replacements.append((find_tags, _split_tags(replace_side)))

    remove_raw = raw.get("remove")
    if remove_raw is None:
        remove_raw = raw.get("removals")
    if remove_raw is None:
        remove_raw = raw.get("delete")
    if isinstance(remove_raw, dict):
        remove_raw = list(remove_raw.keys())
    elif isinstance(remove_raw, str):
        remove_raw = [remove_raw]
    if not isinstance(remove_raw, (list, tuple)):
        remove_raw = []

    remove_tags = []
    for item in remove_raw:
        if isinstance(item, dict):
            item = item.get("tag", item.get("from", ""))
        remove_tags.extend(_split_tags(item))

    return replacements, remove_tags


def _replace_in_line(tags, normalize, patterns, replace_tags, sequence):
    """Apply one replace rule to a single list of tags."""
    if not patterns or not tags:
        return tags

    keys = [normalize(tag) for tag in tags]

    if sequence:
        width = len(patterns)
        total = len(tags)
        result = []
        index = 0
        while index < total:
            if index + width <= total and all(
                pattern.matches(keys[index + offset]) for offset, pattern in enumerate(patterns)
            ):
                result.extend(replace_tags)
                index += width
            else:
                result.append(tags[index])
                index += 1
        return result

    positions = []
    for pattern in patterns:
        found = next((i for i, key in enumerate(keys) if pattern.matches(key)), None)
        if found is None:
            return tags
        positions.append(found)
    positions = sorted(set(positions))
    first = positions[0]
    removed = set(positions)

    result = []
    for index, tag in enumerate(tags):
        if index == first:
            result.extend(replace_tags)
        if index in removed:
            continue
        result.append(tag)
    return result


def apply_rules(text, rules_json, match_mode=MATCH_MODE_ANY, case_sensitive=False,
                treat_underscore_as_space=True, remove_duplicates=True):
    """Apply the replace/remove rules to a tag string and return the result."""
    text = "" if text is None else str(text)
    replacements, remove_tags = _parse_rules(rules_json)
    if not replacements and not remove_tags:
        return text

    def normalize(value):
        return _normalize(value, case_sensitive, treat_underscore_as_space)

    compiled = []
    for find_tags, replace_tags in replacements:
        patterns = []
        seen = set()
        for tag in find_tags:
            pattern = _TagPattern(normalize(tag))
            if not pattern.is_wildcard and pattern.value in seen:
                continue
            seen.add(pattern.value)
            patterns.append(pattern)
        if patterns:
            compiled.append((patterns, replace_tags))

    remove_patterns = [_TagPattern(normalize(tag)) for tag in remove_tags]
    sequence = str(match_mode).strip().lower().startswith("exact")

    output_lines = []
    for line in text.split("\n"):
        tags = _split_tags(line)
        if not tags:
            output_lines.append("")
            continue

        for patterns, replace_tags in compiled:
            tags = _replace_in_line(tags, normalize, patterns, replace_tags, sequence)

        if remove_patterns:
            kept = []
            for tag in tags:
                key = normalize(tag)
                if any(pattern.matches(key) for pattern in remove_patterns):
                    continue
                kept.append(tag)
            tags = kept

        if remove_duplicates:
            seen_keys = set()
            deduped = []
            for tag in tags:
                key = normalize(tag)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                deduped.append(tag)
            tags = deduped

        output_lines.append(", ".join(tags))

    return "\n".join(output_lines)


class TagRules:
    """Rewrite / remove tags with a table of rules edited inside the node."""

    CATEGORY = "Gelbooru"
    FUNCTION = "apply"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("tags",)
    OUTPUT_TOOLTIPS = ("The tag string after the replace and remove rules were applied",)
    DESCRIPTION = (
        "Rewrites tags coming from the Gelbooru nodes. Edit the rule table in the node: "
        "the left column is what to find (several tags = all of them), the right column is "
        "what to put instead (several tags = all of them). A second table removes tags you "
        "never want in the result."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {
                    "forceInput": True,
                    "default": "",
                    "multiline": True,
                    "tooltip": "Tags to process - connect imgtags (or any STRING) here. "
                               "One post per line, tags separated by commas.",
                }),
                "rules_json": ("STRING", {
                    "default": DEFAULT_RULES_JSON,
                    "multiline": False,
                    "tooltip": "Rule table, edited through the node UI. Stored as JSON so the "
                               "workflow and the API keep working without the JavaScript UI.",
                }),
                "match_mode": (MATCH_MODES, {
                    "default": MATCH_MODE_ANY,
                    "tooltip": "How the 'find' column matches several tags. "
                               "All tags (any order): every listed tag must be somewhere on the line. "
                               "Exact sequence: the listed tags must appear next to each other, in that order.",
                }),
                "case_sensitive": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Match tags case-sensitively",
                }),
                "treat_underscore_as_space": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Treat '_' and spaces as the same character, so 'long hair' matches 'long_hair'",
                }),
                "remove_duplicates": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Drop duplicated tags from each line after the rules ran",
                }),
            },
        }

    def apply(self, text, rules_json, match_mode=MATCH_MODE_ANY, case_sensitive=False,
              treat_underscore_as_space=True, remove_duplicates=True):
        result = apply_rules(
            text=text,
            rules_json=rules_json,
            match_mode=match_mode,
            case_sensitive=case_sensitive,
            treat_underscore_as_space=treat_underscore_as_space,
            remove_duplicates=remove_duplicates,
        )
        return (result,)
