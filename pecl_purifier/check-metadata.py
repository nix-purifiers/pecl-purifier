import json
from pathlib import Path
import sys

if json.loads(Path(sys.argv[1]).read_text()) != json.loads(
    Path(sys.argv[2]).read_text()
):
    raise SystemExit("Native PECL metadata differs from its lock")
