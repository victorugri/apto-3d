# Apê 3D — instruções para o Claude Code

Este projeto transforma capturas do apartamento feitas com iPhone 16 Pro num site 3D local onde dá pra
andar pelo apê, pendurar quadros, colocar móveis, medir e comparar layouts.

- **Maquete**: escaneamento RoomPlan (USDZ) com paredes, portas, janelas e móveis em medida real.
- **Splats**: um Gaussian Splat por cômodo, treinado a partir de um vídeo 4K, para o visual fotorrealista.
- **Site**: `site/index.html` junta os dois. A maquete fica invisível por baixo do splat e serve de
  "régua": é nela que o quadro gruda na parede e o móvel pisa no chão.

O guia de captura (como filmar e escanear) está com o usuário, fora deste repositório.

## Estrutura

```
apto-3d/
  CLAUDE.md            este arquivo
  README.md            resumo para o usuário
  serve.py             servidor local do site (salva layouts e alinhamento no disco)
  capturas/            ORIGINAIS do usuário — nunca alterar nem apagar
    roomplan/          apartamento.usdz (export do app de RoomPlan)
    videos/            um vídeo por cômodo: sala.mov, cozinha.mov, suite-master.mov…
    scaniverse/        splats prontos do app Scaniverse (opcional)
    medidas.txt        medidas de trena, em cm (para conferir escala)
  pipeline/            scripts Python, rodar a partir da raiz do projeto
    config.json        caminhos das ferramentas e parâmetros
    check_env.py       confere instalação
    frames.py          etapa 1: vídeo → frames nítidos
    sfm.py             etapa 2: COLMAP → poses + dataset sem distorção
    train.py           etapa 3: Brush → splat .ply
    model.py           copia o USDZ (e converte para GLB com --glb)
    planta.py          gera a maquete a partir da planta do manual (planta_final01.json → GLB)
    planta_final01.json  paredes, portas, janelas e cômodos do apê, em cm (tirados do manual, p.10)
    scene.py           gera site/scene.json
    run_all.py         tudo em sequência
  work/<cômodo>/       cache descartável (frames, banco do COLMAP, dataset, treino, pipeline.log)
  site/
    index.html         o site inteiro (um arquivo, sem build)
    scene.json         gerado pelo pipeline
    assets/            apartamento.usdz, splats/<cômodo>.ply
    data/              o que o usuário salva pelo site (layouts, imagens, alinhamento)
```

## Maquete da planta do manual

Antes do escaneamento, o site já abre com uma maquete do apê montada a partir da planta técnica do manual
do proprietário (Vista da Gávea, apartamento final 01, p.10; o final 02 é o mesmo espelhado, p.11).

- `pipeline/planta_final01.json`: cômodos, paredes com aberturas (portas, portas de vidro, janelas), guarda-corpos,
  móveis fixos e "opcionais" (hoje a porta de vidro entre sala e varanda, que o usuário pretende tirar).
  Coordenadas em cm, x para a direita e y para baixo, como no desenho. As áreas batem com as do manual
  (ex.: suíte 2 = 9,62 m², banhos = 3,38 m²), mas medidas de obra podem variar alguns cm.
- `python pipeline/planta.py` gera `site/assets/planta-final01.glb`, `planta-final02.glb` e `planta.json`
  (cômodos com a posição de câmera usada no "Ir para"). Depois `python pipeline/scene.py`.
- Para corrigir uma medida que o usuário conferiu com trena: edite o JSON e rode os dois comandos.
- Quando o USDZ do RoomPlan existir, o `scene.py` coloca ele como padrão; as plantas continuam disponíveis
  na aba Cena do site.

## Máquina do usuário

Windows, i7-10700K, 16 GB RAM, RTX 3070 (8 GB VRAM). Use PowerShell. Caminhos com `/` funcionam no Python.

## Instalação (uma vez)

Peça confirmação ao usuário antes de instalar programas. Depois:

1. Python 3.11 ou mais novo: `winget install Python.Python.3.12`
2. `pip install -r pipeline/requirements.txt`
3. ffmpeg (build *full*, que tem o filtro `zscale` para vídeo HDR): `winget install Gyan.FFmpeg`
4. COLMAP: baixe o asset `*-windows-cuda*.zip` da última release em
   https://github.com/colmap/colmap/releases , extraia em `C:/tools/colmap` e ponha em
   `pipeline/config.json` → `tools.colmap`: `"C:/tools/colmap/COLMAP.bat"` (ou o `colmap.exe` que vier no zip).
5. Brush: baixe o zip de Windows da última release em https://github.com/ArthurBrussee/brush/releases ,
   extraia em `C:/tools/brush` e ponha o caminho do executável em `tools.brush`.
6. `python pipeline/check_env.py` até tudo dar OK.

Os nomes dos assets nas releases mudam; confira na página antes de baixar.

## Fluxo de trabalho

1. `python pipeline/check_env.py`
2. Confira o que existe em `capturas/` e mostre ao usuário a lista de cômodos que serão processados.
3. **Teste rápido primeiro**, no menor cômodo:
   `python pipeline/run_all.py --room <cômodo> --steps 7000`
   e abra o resultado com `python serve.py` antes de gastar horas no resto.
4. Tudo: `python pipeline/run_all.py` (de 30 a 60 min por cômodo na 3070). Se for longo, rode um cômodo
   por vez e reporte entre eles.
5. `python serve.py` abre http://localhost:8000. No site, o usuário alinha cada splat uma vez
   (ferramenta **Alinhar**). Com o `serve.py`, o alinhamento é salvo sozinho em `site/data`.

Cada etapa pula o que já existe. `--force` refaz tudo; `--from sfm` ou `--from train` refaz a partir dali.
Rodar etapas avulsas: `python pipeline/frames.py capturas/videos/sala.mov`, `python pipeline/sfm.py sala`,
`python pipeline/train.py sala`, `python pipeline/scene.py`.

## Verificar cada etapa (não confie só no código de saída)

- **frames**: 150 a 260 imagens por cômodo em `work/<cômodo>/images`. Abra 2 ou 3 e confira se estão nítidas
  e com cores normais (lavadas = vídeo HDR mal convertido).
- **sfm**: o log mostra `N/M imagens registradas`. Abaixo de 80%, tente `--matcher exhaustive`, aumente
  `frames.sample_fps`, ou sugira regravar aquele cômodo (mais devagar, mais sobreposição).
- **train**: `site/assets/splats/<cômodo>.ply` costuma ter de 50 a 400 MB. Abra no site e olhe.

## Quando algo dá errado

| Sintoma | O que fazer |
| --- | --- |
| COLMAP reclama de opção desconhecida | As versões renomeiam opções. `sfm.py` lê o `-h`; rode `colmap <comando> -h` e ajuste o nome em `sfm.py`. |
| Brush não aceita os argumentos | `python pipeline/train.py <cômodo> --print-help` e configure `train.command` no `config.json` (modelo com `{brush} {dataset} {out_dir} {steps} {max_res}`). |
| Falta de memória na GPU | `train.max_resolution` para 1280 (ou `frames.long_side` 1280 e refazer frames), fechar jogos e navegador. |
| Splat com névoa ou "fantasmas" | Mais passos (`--steps 40000`); se persistir, é a captura (algo se mexeu, luz mudou). |
| Cores lavadas | Vídeo HDR: confira se o ffmpeg tem `zscale` (`check_env.py` avisa). Ou regravar com Vídeo HDR desligado. |
| Splat aparece de cabeça pra baixo ou torto no site | O `scene.py` já vira 180° em X os splats do pipeline (o COLMAP endireitado usa "pra cima" = −Y). Se ainda vier torto: no site, Alinhar → pares sem "manter em pé", ou Virar 180°. |
| USDZ não abre no site | `python pipeline/model.py --glb`, apague `site/assets/apartamento.usdz` e rode `python pipeline/scene.py` (ele usa o `apartamento.glb`). |
| Poucas imagens registradas num banheiro | Banheiro pequeno com azulejo liso é difícil. Aceitável ficar só com a maquete nele. |

## O site (`site/index.html`)

- Um arquivo só: HTML + CSS + um `<script type="module">`. Sem build, sem npm.
- Bibliotecas via import map do jsDelivr: three.js **0.186.1** (tem o `USDLoader` que lê USDZ binário) e
  Spark **2.2.0** (`@sparkjsdev/spark`, renderizador de Gaussian Splat para three.js). Precisa de internet
  para carregar as bibliotecas. Para funcionar offline, copie os arquivos para `site/vendor/` e troque o import map.
- O arquivo começa em `<title>`, sem `<!doctype>`/`<head>`/`<body>`: é o formato de artifact do Claude,
  para o mesmo arquivo poder ser publicado. O `serve.py` acrescenta o esqueleto ao servir. Não acrescente
  doctype no arquivo; se precisar mexer no `<head>`, mexa na constante `HEAD` do `serve.py`.
- Armazenamento (`Store` no código): com o `serve.py`, grava em `site/data/kv/*.json` e `site/data/blobs/*`;
  sem ele, usa IndexedDB do navegador.
- Unidades: metros, Y para cima. `state.floorY` é a altura do piso (vem do piso do RoomPlan).
- `scene.json`: `{ "models": [{"id", "name", "url", "source": "scan"|"planta", "rooms": [{"name", "x", "z", "lx", "lz", "area"}]}], "model": "<id padrão>", "splats": [{"id", "name", "url", "transform": {"p": [x,y,z], "q": [x,y,z,w], "s": escala}}] }`.
  O formato antigo `"model": {"url": ...}` ainda é aceito. O alinhamento salvo pelo site tem prioridade sobre o `transform`.
- Nomes de nó no GLB: `Wall__`, `Door__`, `Window__`, `Floor__`, `Storage__` + rótulo (o rótulo aparece na aba Cena);
  um nó `Opcional__<nome>` agrupa peças que o usuário pode esconder.
- Itens (`state.items`):
  - quadro: `{type:'frame', w, h, d, style, mw, pp, imageId, pos:[x,y,z], normal:[x,y,z]}` (cm, exceto pos em m)
  - móvel caixa: `{type:'box', L, P, A, color, opacity, rot, pos}`; modelo: `{type:'glb', assetId, scale, rot, pos}`
- Classificação da maquete por nome de nó (`classify()`): wall, door, window, opening, floor, object.
- Depuração: `window.__ape` no console do navegador expõe estado, câmera, maquete e splats.
- Ao mudar o site: mantenha os textos em português, teste com `python serve.py` e olhe no navegador
  (Chrome) antes de dizer que terminou.

## Regras

- Nunca altere nem apague nada em `capturas/`.
- `work/` pode ser apagado a qualquer momento; `site/data/` não (são os layouts do usuário). Pergunte antes.
- Arquivos grandes (vídeos, splats, `work/`) ficam fora do git (`.gitignore`).
- Reporte ao usuário em português, curto: o que rodou, quanto tempo levou, o que olhar no site.
