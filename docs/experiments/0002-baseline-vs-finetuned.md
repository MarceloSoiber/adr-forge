# Experimento 0002 — baseline versus adaptador QLoRA

**Data:** 2026-10-17  
**Estado:** `partial` — a execução real concluiu, mas as duas saídas falharam na validação estrutural.

## Matriz congelada

| Cenário | Estratégia | Estado |
| --- | --- | --- |
| `local-adapter-evaluation` | `qwen3-4b-baseline@1` | `failed`: saída Markdown, não JSON |
| `local-adapter-evaluation` | `qwen3-4b-qlora-smoke@1` | `failed`: saída Markdown, não JSON |

Configuração: `configs/evaluation/qwen3-4b-local-smoke.yaml`. Ela usa a revisão imutável
`cdbee75f17c01a7cc42f958dc650907174af0554`, verifica o manifesto do adaptador antes de
carregá-lo e avalia as duas saídas com as mesmas regras determinísticas da aplicação.

## Execução observada

O experimento `1a398f00-356c-4376-a258-034c5173ef53` executou offline e publicou o artefato
local em `var/benchmarks/1a398f00-356c-4376-a258-034c5173ef53.json`. O adaptador foi validado
contra o manifesto antes de ser carregado. Para caber na RTX 3060 sem paginar a RAM, base e
adaptador foram carregados em NF4 4-bit.

| Estratégia | Entrada | Saída | Latência | Validação |
| --- | ---: | ---: | ---: | --- |
| baseline | 142 tokens | 64 tokens | 5.573 ms | falhou: `JSONDecodeError` |
| adaptador QLoRA | 142 tokens | 64 tokens | 4.002 ms | falhou: `JSONDecodeError` |

Ambos produziram conteúdo sobre o cenário, mas em Markdown e truncado pelo limite de 64 tokens.
Não há pontuação determinística ou humana e não se pode concluir melhoria de qualidade.

## Reprodução depois da recuperação da GPU

1. Confirmar `nvidia-smi` funcional e encerrar cargas concorrentes de GPU, inclusive LM Studio.
2. Executar offline:

   ```bash
   HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
   uv run adr-forge benchmark run \
     --config configs/evaluation/qwen3-4b-local-smoke.yaml --json
   ```

3. Inspecionar o JSON criado em `var/benchmarks/`, incluindo saída bruta, telemetria e achados
   determinísticos por célula.

## Limitações

O adaptador vem de um smoke de um único exemplo. Mesmo com a matriz concluída, ela demonstra o
fluxo técnico de comparação e não sustenta uma alegação de melhoria geral de qualidade.
