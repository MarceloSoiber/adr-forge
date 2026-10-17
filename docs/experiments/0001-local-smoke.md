# Experimento 0001 — smokes locais Qwen

**Data:** 2026-10-17  
**Estado:** `passed` — smoke de inferência Transformers e um passo QLoRA executados localmente, offline.

## Comando executado

```bash
uv run pytest -m gpu \
  tests/integration/test_qwen_baseline.py \
  tests/integration/test_qwen_qlora_smoke.py
```

Resultados observados:

- baseline: carregou os três shards Safetensors e gerou saída na RTX 3060;
- QLoRA: treinou um exemplo e publicou adaptador e manifesto; duração de treino do TRL: 1,66 s.

O driver NVIDIA 595.99.02, PyTorch 2.14.1+cu130 e CUDA estavam disponíveis. O modelo GGUF do LM Studio foi descarregado antes dos smokes para liberar VRAM.

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

O cache offline foi validado pelo `AutoConfig` com a revisão acima antes da execução.

## Limites deste experimento

Este é um smoke funcional, não uma medição de qualidade. Não compara baseline e adaptador nem publica artefatos temporários ou dados privados no repositório.

## Pré-requisitos para uma nova tentativa

1. Instalar as dependências opcionais de ML compatíveis e disponibilizar uma GPU CUDA local.
2. Garantir que os artefatos da revisão `cdbee75f17c01a7cc42f958dc650907174af0554` estejam no cache local; os testes executam offline.
3. Liberar a GPU de cargas concorrentes e confirmar que a preflight e o lease exclusivos podem ser obtidos.
4. Executar o baseline com `ADR_FORGE_QWEN_SMOKE=1` e `ADR_FORGE_QWEN_REVISION=cdbee75f17c01a7cc42f958dc650907174af0554`.
5. Executar o QLoRA com `ADR_FORGE_QLORA_SMOKE=1`, preservar o manifest resultante fora do controle de versão e atualizar este relatório com as medições reais.

T125 concluído: os gates locais de baseline e QLoRA foram executados com GPU.
