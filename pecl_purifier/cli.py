"""Native PECL and PHP workflows with compiled Nix-resolved extensions."""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from .capture import capture
from .common import HERE, environment, load, locate, metadata, run, script


def realize(root, companion, target="environment"):
    state = root / ".pecl-purifier"
    state.mkdir(exist_ok=True)
    result = run(
        [
            "nix-build",
            HERE / "nix/realize.nix",
            "--argstr",
            "project",
            root,
            "--argstr",
            "companion",
            companion,
            "--argstr",
            "target",
            target,
            "--argstr",
            "sdk",
            os.environ["PECL_PURIFIER_SDK"],
            "--arg",
            "profile",
            "true",
            "--out-link",
            state / (target + "-profile"),
        ],
        capture_output=True,
        text=True,
    )
    return Path(
        json.loads(Path(result.stdout.strip().splitlines()[-1]).read_text())["output"]
    )


def pecl_program():
    return [
        os.environ["PECL_PURIFIER_BOOTSTRAP_PHP"],
        "-d",
        "error_reporting=8191",
        "-d",
        "include_path=" + os.environ["PECL_PURIFIER_NATIVE_PEAR"] + "/lib/php",
        Path(os.environ["PECL_PURIFIER_NATIVE_PEAR"]) / "lib/php/peclcmd.php",
    ]


def prepare(root, companion, data):
    prepared = realize(root, companion)
    manifest = json.loads((prepared / "manifest.json").read_text())
    digest = hashlib.sha256(
        str(root).encode() + companion.read_bytes() + str(prepared).encode()
    ).hexdigest()
    state = root / ".pecl-purifier" / digest
    state.mkdir(parents=True, exist_ok=True)
    env = environment()
    env.update(PECL_PURIFIER_FROZEN="1")
    temporary = (
        Path(tempfile.gettempdir()) / ("pecl-purifier-" + str(os.getuid())) / digest
    )
    temporary.mkdir(parents=True, exist_ok=True, mode=0o700)
    env["PECL_PURIFIER_BUILD_TEMP"] = str(temporary)
    for key, leaf in (
        ("HOME", "home"),
        ("XDG_CONFIG_HOME", "config"),
        ("XDG_CACHE_HOME", "cache"),
    ):
        directory = state / leaf
        directory.mkdir(exist_ok=True)
        env[key] = str(directory)
    env["CPATH"] = os.pathsep.join(n["headers"] + "/include" for n in manifest["nodes"])
    if not (state / "ready").exists():
        script("configure.php", [state], env=env, capture_output=True, text=True)
        archives = [n["archive"] for n in manifest["nodes"]]
        if archives:
            run(
                [
                    *pecl_program(),
                    "-c",
                    state / "pearrc",
                    "-C",
                    state / "systemrc",
                    "install",
                    "--offline",
                    "--register-only",
                    "--nobuild",
                    "--force",
                    *archives,
                ],
                env=env,
                capture_output=True,
                text=True,
            )
        (state / "ready").write_text("native registry prepared\n")
    ini = (prepared / "php.ini").read_text()
    if data["project"] is not None:
        module = state / "extensions" / (data["project"]["extension"] + ".so")
        if module.exists():
            option = (
                "zend_extension"
                if data["project"]["type"] == "zendextsrc"
                else "extension"
            )
            ini += f"\n{option}={json.dumps(str(module))}\n"
    active = state / "active.ini"
    active.write_text(ini)
    env.update(
        PHP_INI_SCAN_DIR="",
        PHPRC=str(active),
        PECL_PURIFIER_PROJECT=str(root),
        PECL_PURIFIER_LOCK=str(companion),
    )
    if data["project"] is not None:
        project = data["project"]
        env["SOURCE_DATE_EPOCH"] = str(
            int(
                datetime.datetime.fromisoformat(
                    project["date"] + "T" + (project["time"] or "00:00:00") + "+00:00"
                ).timestamp()
            )
        )
    return prepared, manifest, state, env


def request(value, parsed, root, data, manifest):
    path = Path(value)
    if path.exists():
        path = path.resolve()
        if data["project"] is not None and metadata(path) == data["project"]:
            return path, True
        for node in manifest["nodes"]:
            if path == Path(node["archive"]).resolve():
                return path, False
        raise ValueError("Source archive is absent from the PECL lock")
    if (
        data["project"] is not None
        and parsed
        and parsed.get("package", "").lower() == data["project"]["name"].lower()
    ):
        if parsed.get("version") not in (None, data["project"]["version"]):
            raise ValueError("PECL project version differs from its lock")
        return root / "package.xml", True
    for node in manifest["nodes"]:
        if (
            parsed
            and parsed.get("channel", "pecl.php.net") == "pecl.php.net"
            and parsed.get("package", "").lower() == node["name"].lower()
        ):
            if parsed.get("version") not in (
                None,
                node["native"]["version"],
            ) or parsed.get("state") not in (None, node["native"]["state"]):
                raise ValueError(
                    "PECL version selection differs from the lock; update the lock"
                )
            return Path(node["archive"]), False
    raise ValueError("PECL package is absent from the lock; update the lock")


def check_php_options(args):
    valued = {
        "define",
        "file",
        "run",
        "process-begin",
        "process-code",
        "process-file",
        "process-end",
        "server",
        "docroot",
        "rf",
        "rc",
        "re",
        "rz",
        "ri",
        "repeat",
    }
    index = 0
    while index < len(args):
        argument = args[index]
        if argument == "--" or argument == "-" or not argument.startswith("-"):
            break
        option = None
        value = None
        if argument.startswith("--"):
            name, separator, attached = argument[2:].partition("=")
            if name in ("php-ini", "no-php-ini", "zend-extension"):
                raise ValueError("Locked PHP configuration cannot be replaced")
            if name in valued:
                option = "d" if name == "define" else name
                if separator:
                    value = attached
                else:
                    index += 1
                    value = args[index] if index < len(args) else ""
        else:
            for position, name in enumerate(argument[1:], 1):
                if name in "ncz":
                    raise ValueError("Locked PHP configuration cannot be replaced")
                if name in "dfrBRFESt":
                    option = name
                    value = argument[position + 1 :]
                    if not value:
                        index += 1
                        value = args[index] if index < len(args) else ""
                    break
        if option == "d" and value.split("=", 1)[0].strip().lower() in (
            "extension",
            "zend_extension",
            "extension_dir",
        ):
            raise ValueError("Locked PHP extension paths cannot be replaced")
        index += 1


def native(tool, args):
    root, companion = locate()
    if not companion.exists():
        print(
            f"warning: pecl-purifier: no lockfile; using ordinary impure {tool} resolution",
            file=sys.stderr,
        )
        env = os.environ.copy()
        if tool == "pecl":
            env.setdefault(
                "PHP_PEAR_PHP_BIN", os.environ["PECL_PURIFIER_BOOTSTRAP_PHP"]
            )
        os.execve(
            os.environ["PECL_PURIFIER_ORIGINAL_" + tool.upper()], [tool, *args], env
        )
    data = load(root, companion)
    _, manifest, state, env = prepare(root, companion, data)
    if tool == "php":
        check_php_options(args)
        os.execve(
            os.environ["PECL_PURIFIER_RUNTIME_PHP"],
            ["php", "-c", str(state / "active.ini"), *args],
            env,
        )
    with tempfile.TemporaryDirectory(prefix="pecl-options-") as temporary:
        output = Path(temporary) / "plan.json"
        script(
            "plan.php", [state, output, *args], env=env, capture_output=True, text=True
        )
        plan = json.loads(output.read_text())
    command = plan["command"]
    # The package manager uses its SDK bootstrap; application modules load in PHP.
    env.pop("PHPRC", None)
    env.pop("PHP_INI_SCAN_DIR", None)
    if command in (
        "upgrade",
        "upgrade-all",
        "config-set",
        "config-create",
        "channel-delete",
        "channel-update",
        "channel-discover",
        "uninstall",
    ):
        raise ValueError(
            "Change locked PECL selection with pecl-purifier lock --update"
        )
    if (
        command in ("help", "version")
        or not args
        or any(x[0] in ("h", "?", "V") for x in plan["global"])
    ):
        os.execve(
            pecl_program()[0],
            [
                str(x)
                for x in [
                    *pecl_program(),
                    "-c",
                    state / "pearrc",
                    "-C",
                    state / "systemrc",
                    *args,
                ]
            ],
            env,
        )
    options = dict(plan["options"] or {})
    if any(key in options for key in ("installroot", "packagingroot", "ignore-errors")):
        raise ValueError("Locked PECL installation paths cannot be replaced")
    params = plan["params"]
    if command in ("install", "download", "bundle"):
        selected = [
            request(value, parsed, root, data, manifest)
            for value, parsed in zip(params, plan["packages"])
        ]
        projects = [is_project for _, is_project in selected]
        if any(projects) and not all(projects):
            raise ValueError(
                "Install the PECL project separately from its prepared dependencies"
            )
        params = [str(path) for path, _ in selected]
        if command == "install":
            options["offline"] = True
            if not any(projects):
                options.update({"register-only": True, "nobuild": True})
            elif data["project"] is not None:
                generated = (
                    Path(env["PECL_PURIFIER_BUILD_TEMP"]) / data["project"]["name"]
                )
                if generated.exists():
                    shutil.rmtree(generated)
    opts = [
        part
        for key, value in options.items()
        for part in (["--" + key] if value is True else ["--" + key, str(value)])
    ]
    global_options = ["-" + option for option, _ in plan["global"]]
    invocation = [
        *pecl_program(),
        "-c",
        state / "pearrc",
        "-C",
        state / "systemrc",
        *global_options,
        command,
        *opts,
        *params,
    ]
    os.execve(invocation[0], [str(x) for x in invocation], env)


def main():
    try:
        args = sys.argv[1:]
        if args and args[0].startswith("--native="):
            native(args[0].split("=", 1)[1], args[1:])
            return
        before, after = args, []
        if "--" in args:
            index = args.index("--")
            before, after = args[:index], args[index + 1 :]
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument(
            "command", choices=["lock", "prefetch", "bundle", "publish", "exec"]
        )
        parser.add_argument("requirements", nargs="*")
        parser.add_argument("--update", action="store_true")
        parser.add_argument("--input", action="append", default=[])
        parser.add_argument("--project", type=Path, default=Path.cwd())
        parser.add_argument("--lock", type=Path)
        parser.add_argument("--tag")
        options = parser.parse_args(before)
        root = options.project.resolve()
        companion = options.lock.resolve() if options.lock else root / LOCK_NAME
        if options.command == "lock":
            capture(
                root, companion, options.requirements, options.update, options.input
            )
        elif options.command == "exec":
            if not after:
                raise ValueError("Use pecl-purifier exec -- command")
            if not companion.exists():
                print(
                    "warning: pecl-purifier: no lockfile; using ordinary impure resolution",
                    file=sys.stderr,
                )
                os.execvpe(after[0], after, os.environ)
            data = load(root, companion)
            _, _, _, env = prepare(root, companion, data)
            env["PATH"] = (
                os.environ["PECL_PURIFIER_SDK"] + "/bin:" + env.get("PATH", "")
            )
            os.execvpe(after[0], after, env)
        else:
            load(root, companion)
            output = realize(
                root,
                companion,
                "environment" if options.command == "prefetch" else "release",
            )
            if options.command == "publish":
                if not options.tag:
                    raise ValueError("Publication requires --tag")
                run(
                    [
                        os.environ.get("PECL_PURIFIER_GH", "gh"),
                        "release",
                        "upload",
                        options.tag,
                        *sorted(output.iterdir()),
                        "--clobber",
                    ],
                    cwd=root,
                )
            print(output)
    except (
        ValueError,
        KeyError,
        OSError,
        TypeError,
        subprocess.CalledProcessError,
    ) as error:
        if isinstance(error, subprocess.CalledProcessError) and error.stdout:
            print(error.stdout, file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            print(error.stderr, file=sys.stderr)
        print("pecl-purifier: " + str(error), file=sys.stderr)
        raise SystemExit(1)


LOCK_NAME = "pecl-purifier.lock.json"
