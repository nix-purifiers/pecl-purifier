"""Native graph changes, empty documents, tracked inputs and metadata binding."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

repo = Path(__file__).resolve().parent.parent
cli = (
    Path(
        subprocess.check_output(
            ["nix", "build", str(repo) + "#", "--no-link", "--print-out-paths"],
            text=True,
        ).strip()
    )
    / "bin/pecl-purifier"
)

with tempfile.TemporaryDirectory(prefix="pecl-capture-proof-") as temporary:
    temporary = Path(temporary)
    root = temporary / "project"
    root.mkdir()
    (root / "selection.txt").write_text("tracked input\n")
    companion = temporary / "external.json"

    def call(*args):
        return subprocess.run(
            [cli, *args, "--project", root, "--lock", companion],
            capture_output=True,
            text=True,
            check=True,
        )

    call("lock", "--input", "selection.txt")
    empty = json.loads(companion.read_text())
    assert empty["nodes"] == empty["entries"] == [] and empty["project"] is None
    call("prefetch")
    before = companion.read_bytes()
    call("lock")
    assert companion.read_bytes() == before
    shutil.copy2(repo / "examples/minimal/package.xml", root / "package.xml")
    assert subprocess.run(
        [cli, "prefetch", "--project", root, "--lock", companion], capture_output=True
    ).returncode
    call("lock", "--update")
    selected = json.loads(companion.read_text())
    assert selected["extraInputs"] == ["selection.txt"]
    assert {n["name"] for n in selected["nodes"]} == {"yaml", "msgpack"}
    assert selected["abi"]["php_api"] > 0
    call("prefetch")
    original = json.loads(json.dumps(selected))
    selected["abi"]["php_api"] += 1
    companion.write_text(json.dumps(selected))
    failed_abi = subprocess.run(
        [cli, "prefetch", "--project", root, "--lock", companion],
        capture_output=True,
        text=True,
    )
    assert failed_abi.returncode and "ABI changed" in failed_abi.stderr, failed_abi
    selected = original
    selected["nodes"][0]["native"]["state"] = "invalid"
    companion.write_text(json.dumps(selected))
    failed = subprocess.run(
        [cli, "prefetch", "--project", root, "--lock", companion],
        capture_output=True,
        text=True,
    )
    assert failed.returncode and "metadata differs" in failed.stderr, failed

print(
    "Native PECL empty graph, update, tracked inputs and archive metadata binding passed"
)
