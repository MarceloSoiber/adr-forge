# ADR-003 — Start with Qwen3-4B-Instruct-2507 and canonical QLoRA

- Status: accepted
- Date: 2026-10-10
- Decisors: Marcelo Soiber

## Context

The project must teach fine-tuning and operate on an RTX 3060 with 12 GB VRAM.

## Decision

Pin official Qwen3-4B-Instruct-2507 Safetensors for Transformers inference and SFT through TRL,
PEFT LoRA, bitsandbytes 4-bit quantization, Accelerate, and PyTorch. GGUF is inference-only.

## Alternatives considered

- Full fine-tuning: exceeds practical memory and storage.
- Qwen3-VL: visual capability is outside scope.
- 8B first: greater risk before pipeline and data quality are proven.
- Unsloth first: defers canonical learning behind an optimization abstraction.

## Consequences

The first run favors understanding and reproducibility over maximum speed. A second local copy of
the model is needed even if a GGUF is installed in LM Studio.

## Review triggers

Evaluate Qwen3-8B or Unsloth only after the 4B benchmark is complete and measured VRAM, duration,
and quality justify the change.
