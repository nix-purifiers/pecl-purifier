"""Resolve with PECL's downloader and retain its exact source archives."""

import base64
import hashlib
import json
from pathlib import Path
import re
import tempfile

from .common import abi, environment, inputs, load, metadata, script


def snapshot(node):
    return {
        k: node[k]
        for k in (
            "name",
            "channel",
            "version",
            "type",
            "state",
            "extension",
            "dependencies",
            "date",
            "time",
        )
    }


def edges(node, provided=None):
    required = (node["dependencies"] or {}).get("required", {}).get("package", [])
    if isinstance(required, dict):
        required = [required]
    result = [d["name"] for d in required if d.get("channel") == "pecl.php.net"]
    extensions = (node["dependencies"] or {}).get("required", {}).get("extension", [])
    if isinstance(extensions, dict):
        extensions = [extensions]
    if provided:
        result.extend(
            provided[d["name"].lower()]
            for d in extensions
            if d["name"].lower() in provided
        )
    return result


def capture(root, companion, requirements=(), update=False, extra=()):
    if companion.exists() and not update:
        load(root, companion)
        return
    previous = {}
    if companion.exists() and update:
        try:
            previous = json.loads(companion.read_text())
            if not isinstance(previous, dict):
                previous = {}
        except ValueError:
            pass
    extra = extra or previous.get("extraInputs", [])
    requirements = list(requirements or previous.get("requirements", []))
    project = (
        metadata(root / "package.xml") if (root / "package.xml").exists() else None
    )
    selected = [*([root / "package.xml"] if project is not None else []), *requirements]
    if not selected:
        # An application with no extension requirements is a valid empty graph.
        nodes = []
    with tempfile.TemporaryDirectory(prefix="pecl-capture-") as temporary:
        temporary = Path(temporary)
        state = temporary / "state"
        state.mkdir()
        output = temporary / "graph.json"
        if selected:
            script(
                "resolve.php", [state, output, *selected], env=environment(), cwd=root
            )
            nodes = json.loads(output.read_text())
        entries, retained = [], []
        for node in nodes:
            if (
                project is not None
                and node["url"] is None
                and Path(node["file"]).resolve() == root / "package.xml"
            ):
                if snapshot(node) != project:
                    raise ValueError(
                        "Native PECL project metadata changed during resolution"
                    )
                continue
            if node["channel"] != "pecl.php.net" or node["type"] not in (
                "extsrc",
                "zendextsrc",
            ):
                raise ValueError(
                    "This integration currently supports compiled PECL source packages"
                )
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", node["name"]) or not re.fullmatch(
                r"[A-Za-z0-9_]+", node["extension"]
            ):
                raise ValueError("Unsupported PECL package or extension name")
            if not isinstance(node["url"], str) or not node["url"].startswith(
                "https://"
            ):
                raise ValueError("Native PECL must retain an HTTPS source archive URL")
            archive = Path(node["file"])
            if metadata(archive) != snapshot(node):
                raise ValueError(
                    "Native PECL source archive metadata differs from resolution"
                )
            entry = f"archives/{node['name']}/{node['version']}.tgz"
            digest = base64.b64encode(
                hashlib.sha256(archive.read_bytes()).digest()
            ).decode()
            entries.append(
                {
                    "path": entry,
                    "url": node["url"],
                    "hash": "sha256-" + digest,
                    "mirrors": [],
                }
            )
            retained.append(
                {
                    "name": node["name"],
                    "entry": entry,
                    "native": snapshot(node),
                    "dependencies": edges(node),
                }
            )
        names = {n["name"] for n in retained}
        canonical = {n.lower(): n for n in names}
        provided = {n["native"]["extension"].lower(): n["name"] for n in retained}
        for node in retained:
            node["dependencies"] = list(
                dict.fromkeys(
                    canonical.get(d.lower(), d) for d in edges(node["native"], provided)
                )
            )
        if any(d not in names for n in retained for d in n["dependencies"]):
            raise ValueError("The native PECL package graph is incomplete")
        if project is not None and any(
            d.lower() not in canonical for d in edges(project, provided)
        ):
            raise ValueError("The native PECL project graph is incomplete")
        ordered, visited, active = [], set(), set()
        by_name = {n["name"]: n for n in retained}

        def visit(name):
            if name in active:
                raise ValueError("The native PECL graph contains a dependency cycle")
            if name in visited:
                return
            active.add(name)
            for dependency in by_name[name]["dependencies"]:
                visit(dependency)
            active.remove(name)
            visited.add(name)
            ordered.append(by_name[name])

        for node in retained:
            visit(node["name"])
        retained = ordered
        import os

        data = {
            "version": 1,
            "purifier": "pecl",
            "sdk": os.environ["PECL_PURIFIER_SDK_VERSION"],
            "abi": abi(),
            "project": project,
            "requirements": requirements,
            "extraInputs": list(extra),
            "inputs": inputs(root, extra),
            "nodes": retained,
            "entries": entries,
        }
        companion.parent.mkdir(parents=True, exist_ok=True)
        pending = companion.with_suffix(companion.suffix + ".tmp")
        pending.write_text(json.dumps(data, indent=2) + "\n")
        pending.replace(companion)
