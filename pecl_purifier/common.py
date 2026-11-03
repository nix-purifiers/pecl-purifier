"""Native PECL metadata, ABI identity and project input validation."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent.parent
LOCK = "pecl-purifier.lock.json"


def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, **kwargs)


def environment():
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(("PHP_", "PECL_", "PEAR_")) or key in (
            "PHPRC",
            "CPATH",
            "C_INCLUDE_PATH",
            "CPLUS_INCLUDE_PATH",
            "LIBRARY_PATH",
            "LD_LIBRARY_PATH",
        ):
            env.pop(key, None)
    return env


def script(name, args, **kwargs):
    env = dict(kwargs.pop("env", os.environ))
    env.pop("PHPRC", None)
    env.pop("PHP_INI_SCAN_DIR", None)
    kwargs["env"] = env
    return run(
        [
            os.environ["PECL_PURIFIER_BOOTSTRAP_PHP"],
            "-d",
            "error_reporting=8191",
            "-d",
            "include_path=" + os.environ["PECL_PURIFIER_NATIVE_PEAR"] + "/lib/php",
            HERE / "pecl_purifier" / name,
            *args,
        ],
        **kwargs,
    )


def abi():
    with tempfile.TemporaryDirectory(prefix="pecl-abi-") as temporary:
        output = Path(temporary) / "abi.json"
        script(
            "phpize-meta.php",
            [output, os.environ["PECL_PURIFIER_PHPIZE"]],
            env=environment(),
            capture_output=True,
            text=True,
        )
        return json.loads(output.read_text())


def metadata(path):
    with tempfile.TemporaryDirectory(prefix="pecl-metadata-") as temporary:
        temporary = Path(temporary)
        output = temporary / "metadata.json"
        script(
            "read-package.php",
            [path, output, temporary / "state"],
            env=environment(),
            capture_output=True,
            text=True,
        )
        return json.loads(output.read_text())


def relative(name):
    return (
        isinstance(name, str)
        and bool(name)
        and not Path(name).is_absolute()
        and ".." not in Path(name).parts
    )


def inputs(root, extra=()):
    names = sorted(
        set([*(["package.xml"] if (root / "package.xml").exists() else []), *extra])
    )
    result = {}
    for name in names:
        path = root / name
        if not relative(name) or path.resolve() != path or not path.is_file():
            raise ValueError("Lock inputs must be regular files inside the project")
        blob = path.read_bytes()
        result[name] = {
            "content": blob.decode(),
            "sha256": hashlib.sha256(blob).hexdigest(),
        }
    return result


def load(root, companion):
    data = json.loads(companion.read_text())
    if data.get("version") != 1 or data.get("purifier") != "pecl":
        raise ValueError("Invalid PECL lock")
    if (
        data.get("sdk") != os.environ["PECL_PURIFIER_SDK_VERSION"]
        or data.get("abi") != abi()
    ):
        raise ValueError(
            "PHP SDK or module ABI changed; run pecl-purifier lock --update"
        )
    if data["inputs"] != inputs(root, data.get("extraInputs", [])):
        raise ValueError("PECL metadata changed; run pecl-purifier lock --update")
    if (
        data["project"] is not None
        and metadata(root / "package.xml") != data["project"]
    ):
        raise ValueError("Native PECL project metadata changed; update the lock")
    return data


def locate():
    selected = os.environ.get("PECL_PURIFIER_LOCK")
    if selected:
        companion = Path(selected).resolve()
        return Path(
            os.environ.get("PECL_PURIFIER_PROJECT", companion.parent)
        ).resolve(), companion
    root = next(
        (p for p in (Path.cwd(), *Path.cwd().parents) if (p / LOCK).exists()),
        Path.cwd(),
    )
    return root, root / LOCK
