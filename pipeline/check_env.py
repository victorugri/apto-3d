"""Confere se tudo que o pipeline precisa está instalado.

    python pipeline/check_env.py
"""
from __future__ import annotations

import importlib
import shutil
import sys

from common import ROOT, capture, find_tool, list_videos, load_config, model_path_hint

OK, WARN, BAD = "OK  ", "AVISO", "FALTA"


def line(status, what, detail=""):
    print(f"  [{status}] {what}" + (f" — {detail}" if detail else ""))


def main():
    cfg = load_config()
    bad = 0
    print(f"Projeto: {ROOT}\n")

    print("Python")
    v = sys.version_info
    if v >= (3, 10):
        line(OK, f"Python {v.major}.{v.minor}")
    else:
        line(BAD, f"Python {v.major}.{v.minor}", "use 3.10 ou mais novo"); bad += 1
    for mod, pkg, required in [("cv2", "opencv-python-headless", True), ("numpy", "numpy", True),
                               ("pxr", "usd-core", False), ("trimesh", "trimesh", False)]:
        try:
            importlib.import_module(mod)
            line(OK, pkg)
        except ImportError:
            if required:
                line(BAD, pkg, f"pip install {pkg}"); bad += 1
            else:
                line(WARN, pkg, "opcional (só para converter USDZ em GLB)")

    print("\nFerramentas")
    for name, hint in [("ffmpeg", "winget install Gyan.FFmpeg"), ("ffprobe", "vem junto com o ffmpeg"),
                       ("colmap", "build windows-cuda: github.com/colmap/colmap/releases"),
                       ("brush", "github.com/ArthurBrussee/brush/releases")]:
        p = find_tool(name, cfg)
        if not p:
            line(BAD, name, hint + " → depois ajuste pipeline/config.json se não estiver no PATH"); bad += 1
            continue
        ver = ""
        if name == "ffmpeg":
            ver = capture([p, "-version"]).splitlines()[0][:60]
            if " zscale " not in capture([p, "-hide_banner", "-filters"]):
                line(WARN, "ffmpeg sem zscale", "vídeos HDR não serão convertidos direito; use o build full do Gyan")
        elif name == "colmap":
            h = capture([p, "help"])
            ver = (h.splitlines() or [""])[0][:70]
            if "global_mapper" not in h:
                line(WARN, "COLMAP sem global_mapper", "funciona, mas o mapper incremental é mais lento (COLMAP 4+ recomendado)")
            if "with CUDA" not in h and "CUDA" not in h:
                line(WARN, "COLMAP pode estar sem CUDA", "baixe o build *-windows-cuda para usar a GPU")
        elif name == "brush":
            ver = (capture([p, "--version"]).strip().splitlines() or [""])[0][:60]
        line(OK, name, f"{p}  {ver}")

    print("\nGPU")
    smi = shutil.which("nvidia-smi")
    if smi:
        out = capture([smi, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"]).strip()
        line(OK, out or "nvidia-smi encontrado")
    else:
        line(WARN, "nvidia-smi não encontrado", "o driver NVIDIA está instalado?")

    print("\nCapturas")
    vids = list_videos()
    line(OK if vids else WARN, f"{len(vids)} vídeo(s) em capturas/videos", ", ".join(v.name for v in vids)[:120])
    line(OK if model_path_hint() else WARN, "USDZ do RoomPlan", model_path_hint() or "nenhum em capturas/roomplan")
    free = shutil.disk_usage(ROOT).free / 1e9
    line(OK if free > 20 else WARN, f"{free:.0f} GB livres no disco", "cada cômodo usa de 1 a 3 GB durante o processamento")

    print("\n" + ("Tudo pronto." if not bad else f"{bad} item(ns) faltando. Resolva e rode de novo."))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
