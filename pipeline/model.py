"""Etapa 4: copia a maquete do RoomPlan para o site (e, se pedir, converte para GLB).

    python pipeline/model.py                # copia capturas/roomplan/*.usdz → site/assets/apartamento.usdz
    python pipeline/model.py --glb          # também gera site/assets/apartamento.glb

O site abre o USDZ direto. O GLB é um plano B caso algum USDZ não abra no navegador
(precisa de: pip install usd-core trimesh).
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from common import ASSETS, ROOMPLAN, fail, log


def find_usdz() -> Path | None:
    files = sorted(ROOMPLAN.glob("*.usdz")) + sorted(ROOMPLAN.glob("*.usd*"))
    return files[0] if files else None


def usdz_to_glb(src: Path, dst: Path) -> Path:
    try:
        import numpy as np
        import trimesh
        from pxr import Usd, UsdGeom
    except ImportError:
        fail("para converter em GLB instale: pip install usd-core trimesh numpy")
    stage = Usd.Stage.Open(str(src))
    mpu = UsdGeom.GetStageMetersPerUnit(stage) or 1.0
    up = UsdGeom.GetStageUpAxis(stage)
    cache = UsdGeom.XformCache()
    scene = trimesh.Scene()
    n = 0
    for prim in stage.Traverse():
        if not prim.IsA(UsdGeom.Mesh):
            continue
        mesh = UsdGeom.Mesh(prim)
        pts = mesh.GetPointsAttr().Get()
        counts = mesh.GetFaceVertexCountsAttr().Get()
        idx = mesh.GetFaceVertexIndicesAttr().Get()
        if not pts or not counts or not idx:
            continue
        m = np.array(cache.GetLocalToWorldTransform(prim), dtype=float)   # USD: vetor-linha
        p = np.c_[np.array(pts, dtype=float), np.ones(len(pts))] @ m
        verts = p[:, :3] * mpu
        if up == UsdGeom.Tokens.z:
            verts = verts[:, [0, 2, 1]] * np.array([1, 1, -1])
        faces, k = [], 0
        idx = list(idx)
        for c in counts:
            for j in range(1, c - 1):
                faces.append([idx[k], idx[k + j], idx[k + j + 1]])
            k += c
        name = prim.GetName()
        parent = prim.GetParent().GetName() if prim.GetParent() else ""
        node = f"{name}" if name.lower() not in ("mesh", "geom") else f"{parent}"
        scene.add_geometry(trimesh.Trimesh(vertices=verts, faces=np.array(faces), process=False), node_name=node, geom_name=node)
        n += 1
    if not n:
        fail(f"nenhuma malha encontrada em {src}")
    dst.write_bytes(scene.export(file_type="glb"))
    log(f"GLB com {n} peças salvo em {dst}")
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, help="arquivo USDZ (padrão: o primeiro em capturas/roomplan)")
    ap.add_argument("--glb", action="store_true", help="também gerar apartamento.glb")
    a = ap.parse_args()
    src = a.src or find_usdz()
    if not src or not src.exists():
        fail("nenhum USDZ em capturas/roomplan/. Exporte do app de RoomPlan e salve lá.")
    ASSETS.mkdir(parents=True, exist_ok=True)
    dst = ASSETS / "apartamento.usdz"
    shutil.copy2(src, dst)
    log(f"maquete copiada: {src.name} → {dst}")
    if a.glb:
        usdz_to_glb(dst, ASSETS / "apartamento.glb")


if __name__ == "__main__":
    main()
