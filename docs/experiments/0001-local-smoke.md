# Experimento 0001 — smokes locais Qwen (não executados)

**Data:** 2026-10-17  
**Estado:** `skipped` — este registro não comprova inferência, treinamento, capacidade de GPU, nem qualidade do modelo.

## Comando executado

```bash
uv run pytest -m gpu \
  tests/integration/test_qwen_baseline.py \
  tests/integration/test_qwen_qlora_smoke.py
```

Os dois testes foram coletados, mas foram ignorados porque os opt-ins não foram
fornecidos:

- baseline: `ADR_FORGE_QWEN_SMOKE=1` e `ADR_FORGE_QWEN_REVISION`;
- QLoRA: `ADR_FORGE_QLORA_SMOKE=1`.

Como essa verificação ocorre antes da importação do framework e da consulta a
CUDA, não houve avaliação de hardware, driver, VRAM, dependências de ML, cache
local do modelo ou artefatos de treinamento nesta tentativa.

## Identidades e configurações pretendidas

| Item | Valor |
| --- | --- |
| Revisão do código | `1223cb016390f2fa8c8a414aa92244bcf6fc988b` |
| Modelo | `Qwen/Qwen3-4B-Instruct-2507` |
| Revisão imutável do modelo | `cdbee75f17c01a7cc42f958dc650907174af0554` |
| Configuração de treino | `configs/training/qwen3-4b-smoke.yaml` |
| Configuração do modelo | `configs/models/qwen3-4b-instruct-2507.yaml` |
| Dataset de smoke | `datasets/fixtures/training-smoke.jsonl` |
| Rede para os testes | desabilitada por `HF_HUB_OFFLINE=1` e `TRANSFORMERS_OFFLINE=1` quando o opt-in é aceito |

O baseline usa a revisão fornecida por `ADR_FORGE_QWEN_REVISION`; portanto, a
revisão acima é a identidade configurada para o experimento, não uma revisão
confirmada por uma execução nesta máquina.

## Dados não produzidos

Não foram produzidos duração, telemetria de hardware, pico de VRAM, tokens,
checkpoints, manifest de adaptador, hashes de artefatos ou resultado de
inferência. Nenhum artefato privado foi adicionado ao repositório.

## Pré-requisitos para uma nova tentativa

1. Instalar as dependências opcionais de ML compatíveis e disponibilizar uma GPU CUDA local.
2. Garantir que os artefatos da revisão `cdbee75f17c01a7cc42f958dc650907174af0554` estejam no cache local; os testes executam offline.
3. Liberar a GPU de cargas concorrentes e confirmar que a preflight e o lease exclusivos podem ser obtidos.
4. Executar o baseline com `ADR_FORGE_QWEN_SMOKE=1` e `ADR_FORGE_QWEN_REVISION=cdbee75f17c01a7cc42f958dc650907174af0554`.
5. Executar o QLoRA com `ADR_FORGE_QLORA_SMOKE=1`, preservar o manifest resultante fora do controle de versão e atualizar este relatório com as medições reais.

T125 permanece aberto: o gate local com GPU ainda não foi executado.
