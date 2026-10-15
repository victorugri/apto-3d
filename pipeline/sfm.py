"""Etapa 2: COLMAP — descobre a posição da câmera em cada frame e prepara o dataset do treino.

    python pipeline/sfm.py sala
    python pipeline/sfm.py sala --matcher exhaustive --force

Entrada: work/<cômodo>/images
Saída:   work/<cômodo>/dataset/{images, sparse/0}  (formato COLMAP sem distorção, pronto para o Brush)
"""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from common import capture, fail, find_tool, load_config, log, pick_option, room_dirs, run


def registered_images(colmap: str, model_dir: Path) -> int:
    out = capture([colmap, "model_analyzer", "--path", str(model_dir)])
    m = re.search(r"Registered images:\s*(\d+)", out)
    return int(m.group(1)) if m else 0


def reconstruct(room: str, matcher: str | None = None, force: bool = False) -> Path:
    cfg = load_config()
    ccfg = cfg["colmap"]
    d = room_dirs(room)
    ds_sparse = d["dataset"] / "sparse" / "0"
    if ds_sparse.exists() and any(ds_sparse.iterdir()) and not force:
        log(f"[{room}] dataset já existe em {d['dataset']} (use --force para refazer)")
        return d["dataset"]
    images = sorted(d["images"].glob("*.jpg"))
    if not images:
        fail(f"sem frames em {d['images']}. Rode antes: python pipeline/frames.py capturas/videos/{room}.mov")

    colmap = find_tool("colmap", cfg)
    if not colmap:
        fail("COLMAP não encontrado. Baixe o build 'windows-cuda' em https://github.com/colmap/colmap/releases, "
             "extraia (ex.: C:\\tools\\colmap) e coloque o caminho do COLMAP.bat em pipeline/config.json → tools.colmap")

    for k in ("colmap", "dataset"):
        if d[k].exists():
            shutil.rmtree(d[k])
    d["sparse"].mkdir(parents=True)

    top_help = capture([colmap, "help"])
    fe_help = capture([colmap, "feature_extractor", "-h"])
    gpu = "1" if ccfg["use_gpu"] else "0"

    # 1) features (nomes de opção variam entre versões; lemos o --help)
    cmd = [colmap, "feature_extractor", "--database_path", d["db"], "--image_path", d["images"],
           "--ImageReader.single_camera", "1", "--ImageReader.camera_model", ccfg["camera_model"]]
    opt = pick_option(fe_help, "--FeatureExtraction.use_gpu", "--SiftExtraction.use_gpu")
    if opt:
        cmd += [opt, gpu]
    run(cmd, log_file=d["log"])

    # 2) correspondências
    n = len(images)
    matcher = matcher or ccfg["matcher"]
    if matcher == "auto":
        matcher = "exhaustive" if n <= ccfg["exhaustive_max_images"] else "sequential"
    m_cmd = f"{matcher}_matcher"
    m_help = capture([colmap, m_cmd, "-h"])
    cmd = [colmap, m_cmd, "--database_path", d["db"]]
    opt = pick_option(m_help, "--FeatureMatching.use_gpu", "--SiftMatching.use_gpu")
    if opt:
        cmd += [opt, gpu]
    if matcher == "sequential":
        if "--SequentialMatching.overlap" in m_help:
            cmd += ["--SequentialMatching.overlap", str(ccfg["sequential_overlap"])]
        if "--SequentialMatching.quadratic_overlap" in m_help:
            cmd += ["--SequentialMatching.quadratic_overlap", "1"]
    log(f"[{room}] {n} imagens, matcher {matcher}")
    run(cmd, log_file=d["log"])

    # 3) reconstrução: mapeador global (COLMAP 4+, mais rápido) ou incremental
    use_global = "global_mapper" in top_help
    mapper = "global_mapper" if use_global else "mapper"
    run([colmap, mapper, "--database_path", d["db"], "--image_path", d["images"], "--output_path", d["sparse"]],
        log_file=d["log"], check=not use_global)
    models = [p for p in d["sparse"].iterdir() if p.is_dir()]
    if use_global and not models:
        log(f"[{room}] global_mapper não gerou modelo; tentando o mapper incremental")
        run([colmap, "mapper", "--database_path", d["db"], "--image_path", d["images"], "--output_path", d["sparse"]], log_file=d["log"])
        models = [p for p in d["sparse"].iterdir() if p.is_dir()]
    if not models:
        fail(f"[{room}] o COLMAP não conseguiu reconstruir. Veja {d['log']}. Causas comuns: vídeo rápido demais, "
             "paredes lisas sem textura, pouca sobreposição. Tente --matcher exhaustive ou regrave mais devagar.")
    counts = {m: registered_images(colmap, m) for m in models}
    best = max(counts, key=counts.get)
    reg = counts[best]
    log(f"[{room}] modelos: " + ", ".join(f"{m.name}={c}" for m, c in counts.items()) + f" → usando {best.name}")
    pct = 100 * reg / n if n else 0
    log(f"[{room}] {reg}/{n} imagens registradas ({pct:.0f}%)")
    if pct < 70:
        log(f"[{room}] AVISO: menos de 70% das imagens entraram. O splat pode ficar com buracos. "
            "Se o resultado ficar ruim, tente --matcher exhaustive ou regrave o cômodo.")

    # 4) endireita o modelo (gravidade) — opcional; se falhar segue sem
    model = best
    if ccfg.get("orientation"):
        oriented = d["colmap"] / "oriented"
        oriented.mkdir(exist_ok=True)
        r = run([colmap, "model_orientation_aligner", "--image_path", d["images"], "--input_path", best,
                 "--output_path", oriented, "--method", ccfg["orientation"]], log_file=d["log"], check=False)
        if r.returncode == 0 and any(oriented.iterdir()):
            model = oriented
        else:
            log(f"[{room}] orientação automática falhou; seguindo sem (o site alinha depois)")

    # 5) remove distorção da lente e monta o dataset
    run([colmap, "image_undistorter", "--image_path", d["images"], "--input_path", model,
         "--output_path", d["dataset"], "--output_type", "COLMAP"], log_file=d["log"])
    flat = d["dataset"] / "sparse"
    ds_sparse.mkdir(parents=True, exist_ok=True)
    for f in list(flat.iterdir()):
        if f.is_file():
            shutil.move(str(f), ds_sparse / f.name)
    log(f"[{room}] dataset pronto em {d['dataset']}")
    return d["dataset"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("room")
    ap.add_argument("--matcher", choices=["auto", "exhaustive", "sequential"])
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    reconstruct(a.room, a.matcher, a.force)


if __name__ == "__main__":
    main()
