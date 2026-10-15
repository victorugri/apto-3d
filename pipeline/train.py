"""Etapa 3: treina o Gaussian Splat do cômodo na GPU (Brush, por padrão).

    python pipeline/train.py sala
    python pipeline/train.py sala --steps 15000          # teste rápido
    python pipeline/train.py sala --print-help           # mostra as opções do Brush instalado

Entrada: work/<cômodo>/dataset
Saída:   site/assets/splats/<cômodo>.ply

As opções de linha de comando do Brush mudam entre versões. Este script lê o `brush --help` e usa os nomes que
encontrar. Se nada servir, defina em pipeline/config.json → train.command um modelo de comando com
{brush} {dataset} {out_dir} {steps} {max_res}, ex.:
    "command": "{brush} {dataset} --total-steps {steps} --export-path {out_dir} --export-every {steps}"
"""
from __future__ import annotations

import argparse
import shlex
import shutil
import time
from pathlib import Path

from common import SPLATS, capture, fail, find_tool, load_config, log, pick_option, room_dirs, run


def train(room: str, steps: int | None = None, force: bool = False) -> Path:
    cfg = load_config()
    tcfg = cfg["train"]
    steps = steps or tcfg["steps"]
    d = room_dirs(room)
    out = SPLATS / f"{room}.ply"
    if out.exists() and not force:
        log(f"[{room}] splat já existe em {out} (use --force para refazer)")
        return out
    if not (d["dataset"] / "sparse" / "0").exists():
        fail(f"sem dataset em {d['dataset']}. Rode antes: python pipeline/sfm.py {room}")

    brush = find_tool("brush", cfg)
    if not brush and not tcfg.get("command"):
        fail("Brush não encontrado. Baixe o .zip para Windows em https://github.com/ArthurBrussee/brush/releases, "
             "extraia (ex.: C:\\tools\\brush) e coloque o caminho do executável em pipeline/config.json → tools.brush")

    if d["train"].exists():
        shutil.rmtree(d["train"])
    d["train"].mkdir(parents=True)
    SPLATS.mkdir(parents=True, exist_ok=True)

    if tcfg.get("command"):
        cmd = shlex.split(tcfg["command"].format(brush=brush or "brush", dataset=d["dataset"], out_dir=d["train"],
                                                 steps=steps, max_res=tcfg["max_resolution"]), posix=False)
    else:
        help_text = capture([brush, "--help"])
        cmd = [brush, str(d["dataset"])]
        s_opt = pick_option(help_text, "--total-steps", "--total-train-steps", "--total-train-iters", "--max-steps", "--steps")
        p_opt = pick_option(help_text, "--export-path", "--export-dir", "--output-path", "--output")
        e_opt = pick_option(help_text, "--export-every", "--save-every")
        n_opt = pick_option(help_text, "--export-name")
        r_opt = pick_option(help_text, "--max-resolution", "--max-res")
        if not p_opt:
            fail("não reconheci a opção de saída do Brush instalado. Rode `python pipeline/train.py "
                 f"{room} --print-help` e configure train.command em pipeline/config.json.")
        if s_opt:
            cmd += [s_opt, str(steps)]
        cmd += [p_opt, str(d["train"])]
        if e_opt:
            cmd += [e_opt, str(steps)]
        if n_opt:
            cmd += [n_opt, f"{room}.ply"]
        if r_opt and tcfg.get("max_resolution"):
            cmd += [r_opt, str(tcfg["max_resolution"])]
        cmd += [str(x) for x in tcfg.get("extra_args", [])]

    t0 = time.time()
    log(f"[{room}] treinando {steps} passos (na 3070 costuma levar de 15 a 40 min por cômodo)…")
    run(cmd, log_file=d["log"])
    plys = sorted(d["train"].rglob("*.ply"), key=lambda p: p.stat().st_mtime)
    if not plys:
        fail(f"o treino terminou mas não achei nenhum .ply em {d['train']}. Veja {d['log']}.")
    shutil.copy2(plys[-1], out)
    mb = out.stat().st_size / 1e6
    log(f"[{room}] splat pronto: {out} ({mb:.0f} MB) em {(time.time() - t0) / 60:.0f} min")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("room")
    ap.add_argument("--steps", type=int)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--print-help", action="store_true", help="mostra o --help do Brush instalado e sai")
    a = ap.parse_args()
    if a.print_help:
        b = find_tool("brush")
        print(capture([b, "--help"]) if b else "Brush não encontrado")
        return
    train(a.room, a.steps, a.force)


if __name__ == "__main__":
    main()
