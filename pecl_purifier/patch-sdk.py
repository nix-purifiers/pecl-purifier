from pathlib import Path
import re


def change(filename, before, after):
    p = Path(filename)
    s = p.read_text()
    assert s.count(before) == 1, (filename, before)
    p.write_text(s.replace(before, after))


for filename in ["peclcmd.php", "pearcmd.php"]:
    p = Path(filename)
    s = p.read_text()
    pattern = r"ini_set\('include_path', trim\('[^']*'\)\. PATH_SEPARATOR \.  get_include_path\(\)\);"
    s, count = re.subn(
        pattern,
        "ini_set('include_path', __DIR__ . PATH_SEPARATOR . get_include_path());",
        s,
    )
    assert count == 1
    p.write_text(s)
for filename, method in [
    ("PEAR/REST.php", "downloadHttp"),
    ("PEAR/Downloader.php", "_downloadHttp"),
]:
    p = Path(filename)
    s = p.read_text()
    pattern = r"(function " + method + r"\([^)]*\)\s*\{)"
    guard = "\n        if (getenv('PECL_PURIFIER_FROZEN') === '1') { if (!defined('PECL_PURIFIER_MISSING_REPORTED')) { define('PECL_PURIFIER_MISSING_REPORTED', true); fwrite(STDERR, \"pecl-purifier: network resolution is disabled in a locked session; update the lock\\n\"); } return PEAR::raiseError('pecl-purifier: network resolution is disabled in a locked session'); }\n"
    s, count = re.subn(pattern, lambda m: m.group(1) + guard, s, count=1)
    assert count == 1
    p.write_text(s)
change(
    "PEAR/PackageFile/Generator/v2.php",
    "        $this->_packagefile->setDate(date('Y-m-d'));\n        $this->_packagefile->setTime(date('H:i:s'));",
    "        $epoch = getenv('SOURCE_DATE_EPOCH');\n        $this->_packagefile->setDate($epoch !== false ? gmdate('Y-m-d', (int)$epoch) : date('Y-m-d'));\n        $this->_packagefile->setTime($epoch !== false ? gmdate('H:i:s', (int)$epoch) : date('H:i:s'));",
)
p = Path("Archive/Tar.php")
s = p.read_text()
before = "        $v_binary_data_first = pack("
assert s.count(before) == 3
prefix = """        if (getenv('SOURCE_DATE_EPOCH') !== false) {
            $v_uid = sprintf("%07s", 0);
            $v_gid = sprintf("%07s", 0);
            $v_mtime = sprintf("%011s", decoct((int)getenv('SOURCE_DATE_EPOCH')));
            $v_uname = '';
            $v_gname = '';
        }
"""
p.write_text(s.replace(before, prefix + before))

change(
    "PEAR/Installer.php",
    "            $dest = $ext['dest'];",
    "            $dest = $ext['dest'];\n            if (getenv('PECL_PURIFIER_FROZEN') === '1' && in_array($_ext_suff, array('so', 'dll'))) {\n                $dest = $this->config->get('ext_dir', null, $filelist->getChannel()) . DIRECTORY_SEPARATOR . $bn;\n            }",
)

p = Path("PEAR/Builder.php")
s = p.read_text()
before = "/^\\s+(\\S[^:]+):\\s+(\\d{8})/"
after = "/^\\s*(\\S[^:]+):\\s+(\\d{8,})/"
assert s.count(before) == 1
p.write_text(s.replace(before, after))
