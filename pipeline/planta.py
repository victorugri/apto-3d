"""Gera a maquete 3D a partir da planta do manual (pipeline/planta_final01.json).

    python pipeline/planta.py

Saída:
    site/assets/planta-final01.glb   (como no manual)
    site/assets/planta-final02.glb   (espelhada: o apartamento final 02 é o final 01 invertido)
    site/assets/planta.json          (cômodos e variantes, lido pelo scene.py)

A planta usa centímetros, com x para a direita e y para baixo, como no desenho da página 10 do manual.
Para corrigir uma medida, edite o JSON e rode de novo. Os nomes dos nós seguem o que o site reconhece:
Floor__, Wall__, Door__, Window__, Storage__ e Opcional__ (grupo que pode ser escondido no site).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

from common import ASSETS, fail, log

SPEC = Path(__file__).resolve().parent / "planta_final01.json"
FLOOR_T = 0.02      # espessura do piso (m)
GLASS_T = 0.02      # espessura do vidro (m)
FRAME_W = 0.06      # largura do batente (m)
FRAME_D = 0.04      # profundidade extra do batente além da parede (m)


def safe(s: str) -> str:
    """Nome de nó que o GLTFLoader do three.js mantém igual (ele troca espaço por _ e apaga . : / [ ])."""
    s = re.sub(r"[\[\]\.:/]", "", s)
    return re.sub(r"\s+", "_", s.strip())


class Builder:
    def __init__(self, spec: dict, mirror: bool, width_cm: float):
        import trimesh
        self.trimesh = trimesh
        self.scene = trimesh.Scene()
        self.mirror = mirror
        self.W = width_cm
        self.H = spec["pe_direito"] / 100
        self.types = spec["tipos_abertura"]
        self.names: dict[str, int] = {}

    # plano (cm, x→direita, y→baixo) → mundo (m, x, z)
    def px(self, x: float) -> float:
        return (self.W - x if self.mirror else x) / 100

    def pz(self, y: float) -> float:
        return y / 100

    def uniq(self, base: str) -> str:
        n = self.names.get(base, 0)
        self.names[base] = n + 1
        return base if n == 0 else f"{base}#{n}"

    def box(self, kind: str, label: str, x0, z0, x1, z1, y0, y1, parent: str | None = None):
        """Caixa alinhada aos eixos; x/z em cm do plano, y em m."""
        a, b = sorted((self.px(x0), self.px(x1)))
        c, d = sorted((self.pz(z0), self.pz(z1)))
        if b - a < 1e-4 or d - c < 1e-4 or y1 - y0 < 1e-4:
            return
        ext = [b - a, y1 - y0, d - c]
        T = np.eye(4)
        T[:3, 3] = [(a + b) / 2, (y0 + y1) / 2, (c + d) / 2]
        mesh = self.trimesh.creation.box(extents=ext, transform=T)
        name = self.uniq(f"{kind}__{safe(label)}")
        if parent:
            self.scene.add_geometry(mesh, node_name=name, geom_name=name, parent_node_name=parent)
        else:
            self.scene.add_geometry(mesh, node_name=name, geom_name=name)

    def wall(self, w: dict, parent: str | None = None):
        x0, y0, x1, y1 = w["retangulo"]
        horiz = (x1 - x0) >= (y1 - y0)
        lo, hi = (x0, x1) if horiz else (y0, y1)
        a0, a1 = (y0, y1) if horiz else (x0, x1)          # espessura
        label = w["nome"]

        def seg(s, e, yb, yt, kind="Wall", lab=label, t0=a0, t1=a1):
            if horiz:
                self.box(kind, lab, s, t0, e, t1, yb, yt, parent)
            else:
                self.box(kind, lab, t0, s, t1, e, yb, yt, parent)

        ops = sorted(w.get("aberturas", []), key=lambda o: o["de"])
        cur = lo
        for o in ops:
            s, e = max(lo, o["de"]), min(hi, o["ate"])
            t = self.types[o["tipo"]]
            base, topo = t["base"] / 100, t["topo"] / 100
            seg(cur, s, 0, self.H)                          # parede cheia antes da abertura
            if base > 0:
                seg(s, e, 0, base)                          # peitoril
            if topo < self.H:
                seg(s, e, topo, self.H)                     # verga
            mid = (a0 + a1) / 2
            if t.get("vidro"):
                g = GLASS_T * 100 / 2
                seg(s, e, base, topo, "Window", f"Vidro {label}", mid - g, mid + g)
            if t.get("batente"):
                fw = FRAME_W * 100
                fd = FRAME_D * 100 / 2
                seg(s, s + fw, 0, topo, "Door", f"Porta {label}", a0 - fd, a1 + fd)
                seg(e - fw, e, 0, topo, "Door", f"Porta {label}", a0 - fd, a1 + fd)
                seg(s, e, topo - FRAME_W, topo, "Door", f"Porta {label}", a0 - fd, a1 + fd)
            cur = e
        seg(cur, hi, 0, self.H)

    def build(self, spec: dict) -> list[dict]:
        rooms = []
        for c in spec["comodos"]:
            for r in c["retangulos"]:
                self.box("Floor", c["nome"], r[0], r[1], r[2], r[3], -FLOOR_T, 0)
            big = max(c["retangulos"], key=lambda r: (r[2] - r[0]) * (r[3] - r[1]))
            area = sum((r[2] - r[0]) * (r[3] - r[1]) for r in c["retangulos"]) / 1e4
            # câmera num canto do eixo comprido, olhando para o outro lado do cômodo
            x0, y0, x1, y1 = big
            if (x1 - x0) >= (y1 - y0):
                cam, look = ((x0 + min(60, (x1 - x0) * .2), (y0 + y1) / 2), (x1, (y0 + y1) / 2))
            else:
                cam, look = (((x0 + x1) / 2, y1 - min(60, (y1 - y0) * .2)), ((x0 + x1) / 2, y0))
            rooms.append({"name": c["nome"], "x": round(self.px(cam[0]), 3), "z": round(self.pz(cam[1]), 3),
                          "lx": round(self.px(look[0]), 3), "lz": round(self.pz(look[1]), 3), "area": round(area, 2)})
        for w in spec["paredes"]:
            self.wall(w)
        for o in spec.get("opcionais", []):
            group = self.uniq(f"Opcional__{safe(o['nome'])}")
            self.scene.graph.update(frame_from=self.scene.graph.base_frame, frame_to=group, matrix=np.eye(4))
            self.wall(o, parent=group)
        gh = spec.get("guarda_corpo_altura", 110) / 100
        for g in spec.get("guarda_corpos", []):
            x0, y0, x1, y1 = g["retangulo"]
            horiz = (x1 - x0) >= (y1 - y0)
            m = ((y0 + y1) / 2) if horiz else ((x0 + x1) / 2)
            t = GLASS_T * 100 / 2
            if horiz:
                self.box("Window", g["nome"], x0, m - t, x1, m + t, 0, gh)
            else:
                self.box("Window", g["nome"], m - t, y0, m + t, y1, 0, gh)
        for f in spec.get("moveis_fixos", []):
            x0, y0, x1, y1 = f["retangulo"]
            self.box("Storage", f["nome"], x0, y0, x1, y1, 0, f["altura"] / 100)
        return rooms


def width_of(spec: dict) -> float:
    xs = []
    for key in ("comodos",):
        for c in spec[key]:
            for r in c["retangulos"]:
                xs += [r[0], r[2]]
    for key in ("paredes", "opcionais", "guarda_corpos", "moveis_fixos"):
        for w in spec.get(key, []):
            xs += [w["retangulo"][0], w["retangulo"][2]]
    return max(xs) + min(xs)   # espelha em torno do centro, mantendo a mesma faixa de x


def main():
    try:
        import trimesh  # noqa: F401
    except ImportError:
        fail("instale: pip install trimesh numpy")
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    ASSETS.mkdir(parents=True, exist_ok=True)
    W = width_of(spec)
    variants = []
    for vid, name, mirror in [("final01", "Planta do manual: final 01", False), ("final02", "Planta do manual: final 02", True)]:
        b = Builder(spec, mirror, W)
        rooms = b.build(spec)
        out = ASSETS / f"planta-{vid}.glb"
        out.write_bytes(b.scene.export(file_type="glb"))
        log(f"{out.name}: {len(b.scene.geometry)} peças, {out.stat().st_size / 1024:.0f} KB")
        variants.append({"id": f"planta-{vid}", "name": name, "url": f"assets/{out.name}", "source": "planta", "rooms": rooms})
    (ASSETS / "planta.json").write_text(json.dumps({"variants": variants}, ensure_ascii=False, indent=2), encoding="utf-8")
    log("variantes salvas em site/assets/planta.json; rode python pipeline/scene.py para atualizar o scene.json")


if __name__ == "__main__":
    main()
