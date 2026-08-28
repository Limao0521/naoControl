"""Create a NAO deployment archive with portable POSIX permissions.

Windows bsdtar records source directories as read-only, which prevents GNU tar
on the robot from creating their children.  This builder writes predictable
Linux modes into the archive instead.
"""
from __future__ import annotations

import argparse
import tarfile
from pathlib import Path


EXCLUDED_NAMES = {".git", ".venv", ".pytest_cache", "__pycache__"}
EXCLUDED_PATHS = {
    Path("config") / "robot_gateway.secret",
    Path("config") / "nvidia_api_key",
}


def include_member(info: tarfile.TarInfo) -> tarfile.TarInfo | None:
    relative = Path(info.name)
    if any(part in EXCLUDED_NAMES for part in relative.parts):
        return None
    if relative in EXCLUDED_PATHS or relative.name == ".env":
        return None
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mode = 0o755 if info.isdir() else 0o644
    return info


def build_archive(repo_root: Path, archive: Path) -> None:
    with tarfile.open(archive, "w:gz", format=tarfile.GNU_FORMAT) as output:
        for relative in (
            Path("nao"),
            Path("config"),
            Path("pc_gateway"),
            Path("NaoControlReact") / "build",
        ):
            output.add(repo_root / relative, arcname=relative.as_posix(), filter=include_member)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("repo_root", type=Path)
    arguments = parser.parse_args()
    build_archive(arguments.repo_root.resolve(), arguments.archive.resolve())


if __name__ == "__main__":
    main()
