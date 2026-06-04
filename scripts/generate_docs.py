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


def inject_sdk_module_sidebar(package_page: Path, modules: list[str]) -> None:
    if not package_page.exists():
        return

    content = package_page.read_text(encoding="utf-8")
    marker = "<h2>API Documentation</h2>"
    if marker not in content or "SDK Modules" in content:
        return

    links = []
    for module in modules:
        if module == "tjbot":
            continue

        leaf = module.split(".", 1)[1]
        links.append(f'<li><a class="module" href="tjbot/{leaf}.html">{leaf}</a></li>')

    if not links:
        return

    sdk_nav = (
        "\n<h3>SDK Modules</h3>\n"
        '<ul class="memberlist">\n' + "\n".join(links) + "\n</ul>\n"
    )

    content = content.replace(marker, marker + sdk_nav, 1)
    package_page.write_text(content, encoding="utf-8")


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

    # Mirror node-tjbotlib docs breadth by documenting key SDK subpackages.
    modules = [
        "tjbot",
        "tjbot.camera",
        "tjbot.config",
        "tjbot.led",
        "tjbot.microphone",
        "tjbot.rpi_drivers",
        "tjbot.servo",
        "tjbot.speaker",
        "tjbot.stt",
        "tjbot.tts",
        "tjbot.utils",
        "tjbot.vision",
    ]

    command = [
        sys.executable,
        "-m",
        "pdoc",
        "--output-directory",
        str(out_dir),
        *modules,
    ]

    print(f"Generating docs to {out_dir}")
    subprocess.run(command, cwd=repo_root, env=env, check=True)

    inject_sdk_module_sidebar(out_dir / "tjbot.html", modules)

    # Keep generated docs behavior aligned with static docs hosting patterns.
    (out_dir / ".nojekyll").touch(exist_ok=True)
    print("Docs generation complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
