"""Etapa 1: extrai os frames mais nítidos de um vídeo.

    python pipeline/frames.py capturas/videos/sala.mov
    python pipeline/frames.py capturas/videos/sala.mov --max-frames 300 --sample-fps 5

Saída: work/<cômodo>/images/00001.jpg ...
"""
from __future__ import annotations

import argparse
import json
import shutil
import statistics
from pathlib import Path

from common import capture, fail, find_tool, load_config, log, room_dirs, room_name, run

HDR_TRANSFERS = {"arib-std-b67", "smpte2084"}


def probe(ffprobe: str, video: Path) -> dict:
    out = capture([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
                   "stream=width,height,avg_frame_rate,color_transfer,color_primaries:format=duration",
                   "-of", "json", str(video)])
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        fail(f"ffprobe não conseguiu ler {video}:\n{out}")
    st = (data.get("streams") or [{}])[0]
    dur = float((data.get("format") or {}).get("duration") or 0)
    return {"width": st.get("width"), "height": st.get("height"), "duration": dur,
            "transfer": st.get("color_transfer"), "primaries": st.get("color_primaries")}


def has_filter(ffmpeg: str, name: str) -> bool:
    return f" {name} " in capture([ffmpeg, "-hide_banner", "-filters"])


def sharpness(path: Path) -> float:
    import cv2
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 0.0
    h, w = img.shape
    scale = 640 / max(h, w)
    if scale < 1:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return float(cv2.Laplacian(img, cv2.CV_64F).var())


def extract(video: Path, room: str | None = None, sample_fps: float | None = None, max_frames: int | None = None,
            long_side: int | None = None, force: bool = False) -> Path:
    cfg = load_config()
    fcfg = cfg["frames"]
    sample_fps = sample_fps or fcfg["sample_fps"]
    max_frames = max_frames or fcfg["max_frames"]
    long_side = long_side or fcfg["long_side"]
    room = room or room_name(video)
    d = room_dirs(room)
    if d["images"].exists() and any(d["images"].iterdir()) and not force:
        log(f"[{room}] frames já existem em {d['images']} (use --force para refazer)")
        return d["images"]

    ffmpeg, ffprobe = find_tool("ffmpeg", cfg), find_tool("ffprobe", cfg)
    if not ffmpeg or not ffprobe:
        fail("ffmpeg/ffprobe não encontrados. Instale com: winget install Gyan.FFmpeg  (depois reabra o terminal)")

    info = probe(ffprobe, video)
    log(f"[{room}] vídeo {info['width']}x{info['height']}, {info['duration']:.0f}s, transferência de cor: {info['transfer']}")
    if info["duration"] and info["duration"] * sample_fps < max_frames:
        sample_fps = min(10, max_frames / info["duration"] * 1.5)
        log(f"[{room}] vídeo curto: amostrando a {sample_fps:.1f} fps")

    for k in ("raw", "images"):
        if d[k].exists():
            shutil.rmtree(d[k])
        d[k].mkdir(parents=True)

    # filtros: amostragem, escala do lado maior e, se o vídeo for HDR, conversão para SDR
    vf = [f"fps={sample_fps}"]
    if info["transfer"] in HDR_TRANSFERS:
        if has_filter(ffmpeg, "zscale"):
            log(f"[{room}] vídeo HDR detectado: convertendo para SDR (tonemap)")
            vf += ["zscale=t=linear:npl=100", "format=gbrpf32le", "zscale=p=bt709",
                   "tonemap=tonemap=hable:desat=0", "zscale=t=bt709:m=bt709:r=tv", "format=yuv420p"]
        else:
            log(f"[{room}] AVISO: vídeo HDR e este ffmpeg não tem zscale; as cores podem sair lavadas. "
                "Use o build 'full' do ffmpeg (Gyan.FFmpeg) ou regrave com Vídeo HDR desligado.")
            vf += ["colorspace=all=bt709:iall=bt2020:fast=1"]
    vf.append(f"scale='if(gt(iw,ih),{long_side},-2)':'if(gt(iw,ih),-2,{long_side})':flags=lanczos")
    run([ffmpeg, "-hide_banner", "-loglevel", "error", "-stats", "-i", str(video), "-vf", ",".join(vf),
         "-q:v", "2", str(d["raw"] / "f_%05d.jpg")], log_file=d["log"])

    raw = sorted(d["raw"].glob("f_*.jpg"))
    if not raw:
        fail(f"nenhum frame extraído de {video}")
    log(f"[{room}] {len(raw)} frames amostrados; medindo nitidez…")
    scores = [sharpness(p) for p in raw]
    med = statistics.median(scores) or 1.0
    min_ok = med * fcfg["min_sharpness_ratio"]

    # divide em janelas consecutivas e fica com o frame mais nítido de cada uma
    n_out = min(max_frames, len(raw))
    chosen = []
    for i in range(n_out):
        a = round(i * len(raw) / n_out)
        b = max(a + 1, round((i + 1) * len(raw) / n_out))
        j = max(range(a, b), key=lambda k: scores[k])
        if scores[j] >= min_ok:
            chosen.append(j)
    dropped = n_out - len(chosen)
    for n, j in enumerate(chosen, 1):
        shutil.copy2(raw[j], d["images"] / f"{n:05d}.jpg")
    shutil.rmtree(d["raw"])
    log(f"[{room}] {len(chosen)} frames escolhidos ({dropped} janelas descartadas por borrão) → {d['images']}")
    if len(chosen) < min(80, 0.6 * max_frames):
        log(f"[{room}] AVISO: poucos frames nítidos. Considere regravar mais devagar ou aumentar sample_fps.")
    return d["images"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path)
    ap.add_argument("--room", help="nome do cômodo (padrão: nome do arquivo)")
    ap.add_argument("--sample-fps", type=float)
    ap.add_argument("--max-frames", type=int)
    ap.add_argument("--long-side", type=int)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if not a.video.exists():
        fail(f"vídeo não encontrado: {a.video}")
    extract(a.video, a.room, a.sample_fps, a.max_frames, a.long_side, a.force)


if __name__ == "__main__":
    main()
