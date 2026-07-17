#!/usr/bin/env python3
"""Offline sanity check for the ESPHome config.

ESPHome itself is the real validator, but a round trip through the dashboard is
slow and a YAML typo does not deserve one. This catches, locally:

  * YAML syntax errors (ESPHome's custom tags are stubbed out)
  * `${foo}` / `$foo` references with no matching substitution
  * substitutions that are defined but never used (dead config)
  * duplicate component `id:` values

    pip install pyyaml
    python validate.py ../base/core.yaml

Exit code is 1 if anything failed, so it works in a pre-commit hook.
"""
import re
import sys
from pathlib import Path

import yaml

# ESPHome tags carry no meaning for us; keep the value, drop the tag.
for tag in ("!secret", "!lambda", "!include", "!extend", "!remove", "!force"):
    yaml.SafeLoader.add_constructor(
        tag, lambda loader, node, t=tag: f"<{t[1:]}>"
    )
yaml.SafeLoader.add_multi_constructor(
    "!", lambda loader, suffix, node: f"<{suffix}>"
)

# Substitutions ESPHome injects itself, so an unresolved reference is expected.
BUILTIN_SUBS = {"name", "friendly_name", "device_name", "esphome_version"}

SUB_REF = re.compile(r"\$\{(\w+)\}|\$(\w+)")


def collect_ids(node, out, path="root", in_action=False):
    """Collect id: DECLARATIONS only.

    Every ESPHome action is a dotted key (`script.execute`, `light.turn_on`,
    `mixer_speaker.apply_ducking`, ...) and an `id:` underneath one is a
    reference to a component declared elsewhere, not a second declaration.
    Component declarations never sit under a dotted key.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "id" and isinstance(value, str) and not value.startswith("<"):
                if not in_action:
                    out.setdefault(value, []).append(path)
            collect_ids(
                value,
                out,
                f"{path}.{key}",
                in_action or ("." in str(key)),
            )
    elif isinstance(node, list):
        for i, item in enumerate(node):
            collect_ids(item, out, f"{path}[{i}]", in_action)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2

    problems = 0
    for arg in sys.argv[1:]:
        path = Path(arg)
        text = path.read_text(encoding="utf-8")
        print(f"\n=== {path} ===")

        # 1. Does it parse?
        try:
            doc = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            print(f"  FAIL  YAML does not parse:\n{exc}")
            problems += 1
            continue
        print("  OK    YAML parses")

        if not isinstance(doc, dict):
            print("  FAIL  top level is not a mapping")
            problems += 1
            continue

        subs = doc.get("substitutions") or {}

        # 2. References vs definitions. Strip the substitutions block itself so
        #    a default that quotes another key does not count as a use.
        body = re.sub(
            r"^substitutions:.*?(?=^\S)", "", text, flags=re.S | re.M
        )
        used = {m.group(1) or m.group(2) for m in SUB_REF.finditer(body)}

        undefined = sorted(used - set(subs) - BUILTIN_SUBS)
        if undefined:
            print(f"  FAIL  used but never defined: {', '.join(undefined)}")
            problems += 1
        else:
            print("  OK    every ${...} has a substitution")

        # A thin config exists precisely to define substitutions for a remote
        # package, so "unused here" says nothing. Only flag it on a standalone.
        if "packages" in doc:
            print("  SKIP  unused substitutions (this file feeds a package)")
        else:
            unused = sorted(set(subs) - used - BUILTIN_SUBS)
            if unused:
                print(f"  WARN  defined but never used: {', '.join(unused)}")

        # 3. Duplicate ids
        ids = {}
        collect_ids(doc, ids)
        dupes = {k: v for k, v in ids.items() if len(v) > 1}
        if dupes:
            for dupe, where in dupes.items():
                print(f"  FAIL  duplicate id '{dupe}': {'; '.join(where)}")
            problems += 1
        else:
            print(f"  OK    {len(ids)} unique ids, no collisions")

    print("\n" + ("FAILED" if problems else "ALL GOOD"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
