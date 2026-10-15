"""Roda o pipeline inteiro: maquete + (frames → COLMAP → treino) para cada vídeo + scene.json.

    python pipeline/run_all.py                    # todos os vídeos de capturas/videos
    python pipeline/run_all.py --room sala        # só um cômodo
    python pipeline/run_all.py --force            # refaz tudo do zero
    python pipeline/run_all.py --steps 7000       # treino curto, para testar o fluxo
    python pipeline/run_all.py --from sfm         # recomeça a partir do COLMAP

Cada etapa pula o que já foi feito; os logs ficam em work/<cômodo>/pipeline.log.
"""
from __future__ import annotations

import argparse
import shutil
import time

import frames
import model
import scene
import sfm
import train
from common import ASSETS, ROOMPLAN, SCANIVERSE, SPLATS, fail, list_videos, log, room_name

STAGES = ["frames", "sfm", "train"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--room", action="append", help="cômodo(s) a processar (nome do vídeo sem extensão)")
    ap.add_argument("--from", dest="start", choices=STAGES, help="refaz a partir desta etapa (as anteriores são reaproveitadas)")
    ap.add_argument("--force", action="store_true", help="refaz todas as etapas")
    ap.add_argument("--steps", type=int, help="passos de treino (padrão do config.json)")
    ap.add_argument("--matcher", choices=["auto", "exhaustive", "sequential"])
    a = ap.parse_args()

    t0 = time.time()
    # maquete
    usdz = model.find_usdz()
    if usdz:
        ASSETS.mkdir(parents=True, exist_ok=True)
        shutil.copy2(usdz, ASSETS / "apartamento.usdz")
        log(f"maquete: {usdz.name} → site/assets/apartamento.usdz")
    else:
        log(f"AVISO: nenhum USDZ em {ROOMPLAN}; o site vai funcionar só com os splats")

    # splats prontos do Scaniverse (opcional)
    SPLATS.mkdir(parents=True, exist_ok=True)
    if SCANIVERSE.exists():
        for f in sorted(SCANIVERSE.iterdir()):
            if f.suffix.lower() in (".spz", ".ply"):
                dst = SPLATS / f"{room_name(f)}-scaniverse{f.suffix.lower()}"
                if not dst.exists():
                    shutil.copy2(f, dst)
                    log(f"Scaniverse: {f.name} → {dst.name}")

    videos = list_videos()
    if a.room:
        wanted = set(a.room)
        videos = [v for v in videos if room_name(v) in wanted]
        missing = wanted - {room_name(v) for v in videos}
        if missing:
            fail(f"vídeo não encontrado para: {', '.join(sorted(missing))}")
    if not videos:
        log("nenhum vídeo em capturas/videos; só atualizando o scene.json")

    start = STAGES.index(a.start) if a.start else len(STAGES)

    def redo(stage: str) -> bool:
        return a.force or STAGES.index(stage) >= start
    results = []
    for v in videos:
        room = room_name(v)
        log(f"===== {room} ({v.name}) =====")
        r0 = time.time()
        try:
            frames.extract(v, room, force=redo("frames"))
            sfm.reconstruct(room, a.matcher, force=redo("sfm"))
            train.train(room, a.steps, force=redo("train"))
            results.append((room, "ok", time.time() - r0))
        except SystemExit as e:
            results.append((room, f"falhou (veja work/{room}/pipeline.log)", time.time() - r0))
            log(f"[{room}] erro, seguindo para o próximo cômodo")
            if len(videos) == 1:
                raise e

    scene.build()
    log("===== resumo =====")
    for room, status, dt in results:
        log(f"  {room:20s} {status:40s} {dt / 60:5.0f} min")
    log(f"total {(time.time() - t0) / 60:.0f} min. Abra o site com: python serve.py")


if __name__ == "__main__":
    main()
