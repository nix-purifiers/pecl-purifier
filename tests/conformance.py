"""Native registry, compiled modules, source edits, ABI and publication."""

import hashlib
import json
import os
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
    / "bin"
)


def command(args, root, expected=0, **kwargs):
    result = subprocess.run(
        [str(x) for x in args], cwd=root, capture_output=True, text=True, **kwargs
    )
    assert result.returncode == expected, (
        args,
        result.returncode,
        result.stdout,
        result.stderr,
    )
    return result


with tempfile.TemporaryDirectory(prefix="pecl-conformance-") as temporary:
    temporary = Path(temporary)
    root = temporary / "project with spaces"
    shutil.copytree(
        repo / "examples/minimal", root, ignore=shutil.ignore_patterns(".pecl-purifier")
    )
    poison = temporary / "poison.ini"
    poison.write_text("extension=nonexistent-poisoned-module.so\n")
    env = dict(
        os.environ,
        PHPRC=str(poison),
        PHP_INI_SCAN_DIR=str(temporary),
        PHP_PEAR_INSTALL_DIR=str(temporary / "poisoned-pear"),
    )
    listed = command([cli / "pecl", "list"], root, env=env)
    assert "yaml" in listed.stdout and "msgpack" in listed.stdout
    command([cli / "pecl", "install", "--force", "package.xml"], root, env=env)
    assert command([cli / "php", "test.php"], root, env=env).stdout.strip() == "42"
    reflected = command([cli / "php", "--rf", "yaml_parse"], root, env=env)
    assert "yaml_parse" in reflected.stdout and "internal" in reflected.stdout
    (root / "arguments.php").write_text(
        '<?php echo json_encode(array_slice($argv, 1)), "\\n";\n'
    )
    arguments = command(
        [cli / "php", "arguments.php", "-c", "application-argument"], root, env=env
    )
    assert json.loads(arguments.stdout) == ["-c", "application-argument"]
    assert (
        command(
            [
                cli / "php",
                "--define=memory_limit=96M",
                "-r",
                'echo ini_get("memory_limit");',
            ],
            root,
            env=env,
        ).stdout
        == "96M"
    )
    for replacement in [
        ["-n"],
        ["-nc", str(poison)],
        ["--define=extension=unlocked.so"],
        ["-z", "unlocked.so"],
    ]:
        bad = subprocess.run(
            [cli / "php", *replacement, "-v"],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
        )
        assert bad.returncode and "cannot be replaced" in bad.stderr, bad
    source = root / "purifierproof.c"
    original = source.read_text()
    source.write_text(original.replace("RETURN_LONG(42)", "RETURN_LONG(43)"))
    command([cli / "pecl", "install", "--force", "package.xml"], root, env=env)
    failed = subprocess.run(
        [cli / "php", "test.php"], cwd=root, env=env, capture_output=True, text=True
    )
    assert (
        failed.returncode and "native proof failed" in failed.stdout + failed.stderr
    ), failed
    source.write_text(original)
    command([cli / "pecl", "install", "--force", "package.xml"], root, env=env)
    assert command([cli / "php", "test.php"], root, env=env).stdout.strip() == "42"
    xml = root / "package.xml"
    saved = xml.read_text()
    xml.write_text(
        saved.replace("<release>0.1.0</release>", "<release>0.2.0</release>")
    )
    stale = subprocess.run(
        [cli / "php", "test.php"], cwd=root, env=env, capture_output=True, text=True
    )
    assert stale.returncode and "metadata changed" in stale.stderr, stale
    xml.write_text(saved)
    missing = subprocess.run(
        [cli / "pecl", "install", "absentpurifierextension"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )
    assert missing.returncode and "absent from the lock" in missing.stderr, missing
    companion = temporary / "external.json"
    (root / "pecl-purifier.lock.json").rename(companion)
    external = dict(
        env, PECL_PURIFIER_PROJECT=str(root), PECL_PURIFIER_LOCK=str(companion)
    )
    nested = root / "nested"
    nested.mkdir()
    assert (
        command([cli / "php", "../test.php"], nested, env=external).stdout.strip()
        == "42"
    )
    profile = root / ".pecl-purifier/environment-profile"
    references = subprocess.check_output(
        ["nix-store", "--query", "--requisites", profile.resolve()], text=True
    )
    assert (
        "pecl-purifier-" in references
        and "purified-php-msgpack" in references
        and "-dev" in references
    )
    fallback = temporary / "fallback"
    fallback.mkdir()
    ordinary = command([cli / "php", "-r", 'echo "ordinary-php";'], fallback)
    assert ordinary.stdout == "ordinary-php" and "impure" in ordinary.stderr
    ordinary_pecl = command([cli / "pecl", "version"], fallback)
    assert "PEAR Version" in ordinary_pecl.stdout and "impure" in ordinary_pecl.stderr
    streams = command(
        [
            cli / "pecl-purifier",
            "exec",
            "--project",
            fallback,
            "--",
            "python3",
            "-c",
            "import sys; print(sys.stdin.read().strip()); print('native-stderr',file=sys.stderr); sys.exit(7)",
        ],
        fallback,
        expected=7,
        input="native-stdin\n",
    )
    assert (
        streams.stdout.strip() == "native-stdin"
        and "native-stderr" in streams.stderr
        and "impure" in streams.stderr
    )
    bundle = command(
        [cli / "pecl-purifier", "bundle", "--project", root, "--lock", companion], root
    )
    artifacts = Path(bundle.stdout.strip().splitlines()[-1])
    archives = list(artifacts.glob("*.tgz"))
    assert len(archives) == 1
    fake = temporary / "fake-gh"
    record = temporary / "uploaded.json"
    fake.write_text(
        "#!/usr/bin/env python3\nimport hashlib,json,os,pathlib,sys\nfiles={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in map(pathlib.Path,sys.argv[4:-1])};pathlib.Path(os.environ['PUBLICATION_RECORD']).write_text(json.dumps({'args':sys.argv[1:],'files':files}))\n"
    )
    fake.chmod(0o755)
    publication = dict(
        os.environ, PECL_PURIFIER_GH=str(fake), PUBLICATION_RECORD=str(record)
    )
    command(
        [
            cli / "pecl-purifier",
            "publish",
            "--tag",
            "v0.1.0",
            "--project",
            root,
            "--lock",
            companion,
        ],
        root,
        env=publication,
    )
    uploaded = json.loads(record.read_text())
    assert uploaded["args"] == [
        "release",
        "upload",
        "v0.1.0",
        str(archives[0]),
        "--clobber",
    ]
    assert uploaded["files"] == {
        str(archives[0]): hashlib.sha256(archives[0].read_bytes()).hexdigest()
    }
    # Original PECL unpacks and compiles the actual native source package.
    state = next((root / ".pecl-purifier").glob("*/pearrc")).parent
    consumer = temporary / "consumer"
    consumer.mkdir()
    command(
        [
            cli / "pecl",
            "-c",
            state / "pearrc",
            "-C",
            state / "systemrc",
            "bundle",
            "--destination",
            consumer,
            archives[0],
        ],
        consumer,
    )
    source_xml = next(consumer.rglob("package.xml"))
    consumer_output = consumer / "compiled"
    command(
        [
            cli / "php",
            repo / "tests/native-consumer.php",
            state,
            source_xml,
            consumer_output,
        ],
        consumer,
    )
    assert (consumer_output / "purifierproof.so").is_file()
    environment_path = Path(json.loads(profile.resolve().read_text())["output"])
    manifest = json.loads((environment_path / "manifest.json").read_text())
    module_flags = [
        x for n in manifest["nodes"] for x in ["-d", "extension=" + n["module"]]
    ]
    result = command(
        [
            cli / "php",
            *module_flags,
            "-d",
            "extension=" + str(consumer_output / "purifierproof.so"),
            "-r",
            '$v=msgpack_unpack(msgpack_pack(yaml_parse("answer: ".purifier_answer())));if($v["answer"]!==42)exit(8);echo 42;',
        ],
        consumer,
    )
    assert result.stdout.strip() == "42"

print(
    "Native PECL/PHP, mutable C source, registry, ABI, isolation and publication proofs passed"
)
