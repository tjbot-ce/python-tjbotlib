#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
import shutil


SYNC_MAPPINGS = (
    (
        "config schema",
        Path("vendor/tjbot-config/tjbot-config.schema.yaml"),
        Path("src/tjbot/config/vendor/tjbot-config.schema.yaml"),
    ),
    (
        "model registry",
        Path("vendor/tjbot-config/model-registry.yaml"),
        Path("src/tjbot/config/vendor/model-registry.yaml"),
    ),
    (
        "default config",
        Path("vendor/tjbot-config/tjbot.default.toml"),
        Path("src/tjbot/config/vendor/tjbot.default.toml"),
    ),
)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]

    for name, source_rel, target_rel in SYNC_MAPPINGS:
        source_path = repo_root / source_rel
        target_path = repo_root / target_rel
        target_path.parent.mkdir(parents=True, exist_ok=True)

        if source_path.exists():
            shutil.copy2(source_path, target_path)
            print(f"Synced {name} to {target_path}")
        else:
            print(
                f"{name} source not found at {source_path}. "
                f"Using existing bundled snapshot at {target_path}."
            )

    # Note: config/config_types.py is manually maintained.
    # When the schema changes, manually update config_types.py to match.
    print(
        "\nNote: Update src/tjbot/config/config_types.py manually if the schema has changed."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
