"""Etapa 5: monta site/scene.json com as maquetes e os splats que existirem em site/assets.

    python pipeline/scene.py
    python pipeline/scene.py --default planta-final02     # qual maquete abre primeiro

Maquetes possíveis (o site deixa trocar na aba Cena):
  - scan            site/assets/apartamento.usdz (ou .glb), do RoomPlan
  - planta-final01  site/assets/planta-final01.glb, gerada da planta do manual (pipeline/planta.py)
  - planta-final02  a mesma, espelhada
Alinhamentos já feitos (transform de cada splat) são preservados.
"""
from __future__ import annotations

import argparse
import json

from common import ASSETS, SITE, SPLATS, log

SPLAT_EXT = (".ply", ".spz", ".splat", ".ksplat")


def nice(name: str) -> str:
    return name.replace("-", " ").strip().capitalize()


def build(default: str | None = None) -> dict:
    out_file = SITE / "scene.json"
    old = {}
    if out_file.exists():
        try:
            old = json.loads(out_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            old = {}
    old_splats = {s.get("id"): s for s in old.get("splats", [])}

    models = []
    for ext in ("usdz", "glb"):
        p = ASSETS / f"apartamento.{ext}"
        if p.exists():
            models.append({"id": "scan", "name": "Escaneamento (RoomPlan)", "url": f"assets/{p.name}", "source": "scan"})
            break
    planta = ASSETS / "planta.json"
    if planta.exists():
        models += json.loads(planta.read_text(encoding="utf-8")).get("variants", [])

    ids = [m["id"] for m in models]
    old_default = old.get("model") if isinstance(old.get("model"), str) else None
    if default and default not in ids:
        log(f"AVISO: maquete '{default}' não existe; opções: {', '.join(ids)}")
        default = None
    chosen = default or ("scan" if "scan" in ids else None) or (old_default if old_default in ids else None) or (ids[0] if ids else None)

    splats = []
    for p in sorted(SPLATS.iterdir()) if SPLATS.exists() else []:
        if p.suffix.lower() not in SPLAT_EXT:
            continue
        sid = p.stem
        prev = old_splats.get(sid, {})
        entry = {"id": sid, "name": prev.get("name") or nice(sid), "url": f"assets/splats/{p.name}"}
        if prev.get("transform"):
            entry["transform"] = prev["transform"]
        elif not sid.endswith("-scaniverse"):
            # o COLMAP endireitado deixa o "pra cima" em -Y; o site usa +Y. Começa virado 180° no eixo X.
            entry["transform"] = {"p": [0, 0, 0], "q": [1, 0, 0, 0], "s": 1}
        splats.append(entry)

    data = {"models": models, "model": chosen, "splats": splats}
    out_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"scene.json: {len(models)} maquete(s) (abre em: {chosen or 'nenhuma'}), {len(splats)} splat(s) → {out_file}")
    return data


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--default", help="id da maquete que abre primeiro (scan, planta-final01, planta-final02)")
    a = ap.parse_args()
    build(a.default)


if __name__ == "__main__":
    main()
