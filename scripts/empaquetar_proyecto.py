#!/usr/bin/env python3
"""Genera proyecto_completo.txt con todo el codigo fuente del repo (sin deps ni caches)."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "proyecto_completo.txt"

# Directorios/archivos a ignorar por nombre (segmento de ruta)
SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    ".venv312",
    "venv",
    "env",
    "__pycache__",
    ".vscode",
    ".cursor",
    ".pytest_cache",
    "node_modules",
    "data",
}

SKIP_FILE_NAMES = {
    "proyecto_completo.txt",
}

SKIP_EXTENSIONS = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pyc",
    ".pyo",
    ".so",
    ".dylib",
    ".dll",
    ".exe",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
}

# Solo extensiones de texto / codigo propio
ALLOW_EXTENSIONS = {
    ".py",
    ".js",
    ".html",
    ".css",
    ".json",
    ".toml",
    ".txt",
    ".md",
    ".yml",
    ".yaml",
    ".gitignore",
    ".env.example",
}

# Archivos en raiz sin extension
ALLOW_ROOT_FILES = {"Procfile", ".gitignore"}


def should_skip(path: Path, rel: Path) -> bool:
    if rel.name in SKIP_FILE_NAMES:
        return True
    if rel.name.startswith(".env") and rel.name != ".env.example":
        return True
    parts = rel.parts
    for part in parts:
        if part in SKIP_DIR_NAMES:
            return True
    if path.suffix.lower() in SKIP_EXTENSIONS:
        return True
    if path.suffix.lower() in ALLOW_EXTENSIONS:
        return False
    if rel.parent == Path(".") and rel.name in ALLOW_ROOT_FILES:
        return False
    if rel.name == ".gitignore":
        return False
    return True


def collect_files() -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        rel_dir = Path(dirpath).relative_to(ROOT)
        # Podar directorios ignorados in-place
        dirnames[:] = sorted(
            d for d in dirnames if d not in SKIP_DIR_NAMES and not d.startswith(".venv")
        )
        for name in sorted(filenames):
            full = Path(dirpath) / name
            rel = full.relative_to(ROOT)
            if should_skip(full, rel):
                continue
            files.append(rel)
    return sorted(files, key=lambda p: str(p).lower())


def build_tree(files: list[Path]) -> str:
    """Arbol ASCII a partir de rutas relativas."""
    tree: dict = {}
    for rel in files:
        parts = rel.parts
        node = tree
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                node.setdefault("__files__", []).append(part)
            else:
                node = node.setdefault(part, {})

    lines = [f"{ROOT.name}/"]

    def walk(node: dict, prefix: str = "") -> None:
        dirs = sorted(k for k in node if k != "__files__")
        files_list = sorted(node.get("__files__", []))
        entries = [(d, True) for d in dirs] + [(f, False) for f in files_list]
        for idx, (name, is_dir) in enumerate(entries):
            last = idx == len(entries) - 1
            branch = "└── " if last else "├── "
            lines.append(f"{prefix}{branch}{name}{'/' if is_dir else ''}")
            if is_dir:
                ext = "    " if last else "│   "
                walk(node[name], prefix + ext)

    walk(tree)
    return "\n".join(lines)


def read_file_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1", errors="replace")


def main() -> None:
    files = collect_files()
    sep = "=" * 41
    parts: list[str] = [
        "PROYECTO COMPLETO - BODEGA MINERA",
        f"Raiz: {ROOT}",
        f"Archivos incluidos: {len(files)}",
        "",
        "ESTRUCTURA DE DIRECTORIOS",
        "-" * 41,
        build_tree(files),
        "",
    ]
    for rel in files:
        full = ROOT / rel
        parts.append(sep)
        parts.append(f"ARCHIVO: {rel.as_posix()}")
        parts.append(sep)
        parts.append(read_file_safe(full))
        if not parts[-1].endswith("\n"):
            parts.append("")
        parts.append("")

    OUTPUT.write_text("\n".join(parts), encoding="utf-8")
    print(f"Generado: {OUTPUT}")
    print(f"Archivos: {len(files)}")
    print(f"Tamanio: {OUTPUT.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
