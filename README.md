# Apê 3D

Tour 3D do apartamento, com quadros, móveis, medidas e layouts.

## Já funciona sem captura

O site abre com a maquete do apê montada a partir da planta do manual (final 01; o final 02 espelhado está na aba Cena).
Dá pra andar pelos cômodos (**Ir para**), pendurar quadros e testar móveis desde já.
Para corrigir uma medida: edite `pipeline/planta_final01.json` e rode `python pipeline/planta.py` e `python pipeline/scene.py`.

## Como usar

1. **Capture** seguindo o guia (RoomPlan + um vídeo 4K por cômodo).
2. **Coloque os arquivos** em `capturas/`:
   - `capturas/roomplan/apartamento.usdz`
   - `capturas/videos/sala.mov`, `cozinha.mov`… (um por cômodo, nome sem acento)
   - `capturas/medidas.txt` (opcional)
3. **Abra o Claude Code nesta pasta** e peça: *"rode o pipeline do apê"*. Ele segue o `CLAUDE.md`:
   instala o que faltar, processa os vídeos na RTX 3070 e abre o site.

Para só abrir o site depois: `python serve.py` → http://localhost:8000

## No site

| Ferramenta | Para quê |
| --- | --- |
| Foto / Maquete / Raio-X | splat fotorrealista, maquete do RoomPlan, ou os dois juntos |
| Orbitar / Andar | ver de fora ou andar em primeira pessoa (arraste pra olhar, WASD pra andar) |
| Quadro | escolha a imagem e a medida, clique na parede |
| Móvel | tamanhos prontos ou medida livre, ou um modelo .glb; clique no chão |
| Medir | dois cliques = distância em cm |
| Alinhar | encaixa cada splat na maquete (uma vez por cômodo) |
| Layouts | salve versões e compare |
| Capturar | tira uma imagem da vista atual |

Sem o pipeline, também dá pra arrastar direto pro site um USDZ e splats `.spz`/`.ply` feitos no Scaniverse.
