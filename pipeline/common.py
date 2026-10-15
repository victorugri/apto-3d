"""Funções compartilhadas pelo pipeline do Apê 3D."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAPTURAS = ROOT / "capturas"
VIDEOS = CAPTURAS / "videos"
ROOMPLAN = CAPTURAS / "roomplan"
SCANIVERSE = CAPTURAS / "scaniverse"
WORK = ROOT / "work"
SITE = ROOT / "site"
ASSETS = SITE / "assets"
SPLATS = ASSETS / "splats"
CONFIG_FILE = Path(__file__).resolve().parent / "config.json"

VIDEO_EXT = {".mov", ".mp4", ".m4v", ".mkv"}

DEFAULT_CONFIG = {
    "tools": {"ffmpeg": "ffmpeg", "ffprobe": "ffprobe", "colmap": "colmap", "brush": "brush"},
    "frames": {"sample_fps": 4, "max_frames": 260, "long_side": 1600, "min_sharpness_ratio": 0.35},
    "colmap": {"camera_model": "OPENCV", "matcher": "auto", "exhaustive_max_images": 320,
               "sequential_overlap": 20, "use_gpu": True, "orientation": "IMAGE-ORIENTATION"},
    "train": {"steps": 30000, "max_resolution": 1600, "extra_args": [], "command": ""},
}


def load_config() -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if CONFIG_FILE.exists():
        user = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    return cfg


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def fail(msg: str, code: int = 1) -> None:
    print(f"\nERRO: {msg}\n", file=sys.stderr, flush=True)
    sys.exit(code)


def find_tool(name: str, cfg: dict | None = None) -> str | None:
    """Acha um executável: caminho do config.json, PATH, ou variações do Windows (COLMAP.bat, brush_app.exe)."""
    cfg = cfg or load_config()
    configured = cfg["tools"].get(name, name)
    candidates = [configured]
    if name == "colmap":
        candidates += ["colmap", "COLMAP.bat", "colmap.bat", "COLMAP"]
    if name == "brush":
        candidates += ["brush", "brush_app", "brush-app"]
    for c in candidates:
        if not c:
            continue
        p = Path(c)
        if p.is_file():
            return str(p)
        w = shutil.which(c)
        if w:
            return w
    return None


def run(cmd: list[str], log_file: Path | None = None, check: bool = True, quiet: bool = False) -> subprocess.CompletedProcess:
    """Roda um comando mostrando a saída ao vivo e guardando tudo num log."""
    printable = " ".join(f'"{c}"' if " " in str(c) else str(c) for c in cmd)
    log(f"$ {printable}")
    fh = open(log_file, "a", encoding="utf-8") if log_file else None
    if fh:
        fh.write(f"\n$ {printable}\n")
    proc = subprocess.Popen([str(c) for c in cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace")
    out_lines = []
    assert proc.stdout
    for line in proc.stdout:
        out_lines.append(line)
        if fh:
            fh.write(line)
        if not quiet:
            sys.stdout.write("    " + line)
    proc.wait()
    if fh:
        fh.close()
    cp = subprocess.CompletedProcess(cmd, proc.returncode, "".join(out_lines), "")
    if check and proc.returncode != 0:
        tail = "".join(out_lines[-25:])
        fail(f"o comando falhou (código {proc.returncode}):\n{printable}\n--- últimas linhas ---\n{tail}")
    return cp


def capture(cmd: list[str]) -> str:
    """Roda e devolve stdout+stderr (para ler --help)."""
    try:
        r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        return (r.stdout or "") + (r.stderr or "")
    except Exception as e:  # noqa: BLE001
        return f"<falhou: {e}>"


def room_name(video: Path) -> str:
    import re
    import unicodedata
    s = unicodedata.normalize("NFD", video.stem.lower())
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "comodo"


def list_videos() -> list[Path]:
    if not VIDEOS.exists():
        return []
    return sorted(p for p in VIDEOS.iterdir() if p.suffix.lower() in VIDEO_EXT)


def room_dirs(room: str) -> dict[str, Path]:
    base = WORK / room
    return {
        "base": base,
        "raw": base / "frames_raw",
        "images": base / "images",
        "colmap": base / "colmap",
        "db": base / "colmap" / "database.db",
        "sparse": base / "colmap" / "sparse",
        "dataset": base / "dataset",
        "train": base / "train",
        "log": base / "pipeline.log",
    }


def pick_option(help_text: str, *candidates: str) -> str | None:
    """Devolve o primeiro nome de opção que aparece no --help (as versões do COLMAP renomeiam opções)."""
    for c in candidates:
        if c in help_text:
            return c
    return None


def model_path_hint() -> str | None:
    files = sorted(ROOMPLAN.glob("*.usd*")) if ROOMPLAN.exists() else []
    return files[0].name if files else None
