#!/usr/bin/env python3

# Copyright 2026-present TJBot Contributors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def read_version(pyproject_path: Path) -> str:
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)
    project = data.get("project", {})
    version = project.get("version")
    if not isinstance(version, str) or not version.strip():
        raise RuntimeError("Missing [project].version in pyproject.toml")
    return version.strip()


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    docs_repo = (repo_root / "../tjbot-ce.github.io").resolve()

    if not docs_repo.is_dir():
        print("Skipping docs generation: ../tjbot-ce.github.io not found")
        return 0

    version = read_version(repo_root / "pyproject.toml")
    out_dir = docs_repo / "docs" / "python-tjbotlib" / version
    out_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    src_dir = str((repo_root / "src").resolve())
    env["PYTHONPATH"] = (
        src_dir if not env.get("PYTHONPATH") else f"{src_dir}:{env['PYTHONPATH']}"
    )

    command = [
        sys.executable,
        "-m",
        "pdoc",
        "--output-directory",
        str(out_dir),
        "tjbot",
    ]

    print(f"Generating docs to {out_dir}")
    subprocess.run(command, cwd=repo_root, env=env, check=True)

    # Keep generated docs behavior aligned with static docs hosting patterns.
    (out_dir / ".nojekyll").touch(exist_ok=True)
    print("Docs generation complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
