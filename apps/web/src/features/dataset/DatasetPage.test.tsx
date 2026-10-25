import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { DatasetPage } from './DatasetPage'

afterEach(() => vi.unstubAllGlobals())

describe('DatasetPage', () => {
  it('resume uma amostra real e carrega a lista paginada de registros', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          version: 'v0.4.0-adr-dialogue',
          output_format: 'adr-json-v2',
          schema_version: 'v1',
          record_count: 160,
          source_count: 4,
          total_bytes: 524288,
          approximate_tokens: 94600,
          manifest_sha256: 'a'.repeat(64),
          artifact_sha256: 'b'.repeat(64),
          generated_at: '2026-10-24T12:00:00Z',
          records: [
            {
              id: 'example:1',
              title: 'Persistência SQL',
              domain: 'Dados',
              status: 'proposed',
              tokens: 1024,
              context_excerpt: 'Cenário de pagamentos com auditoria.',
              decision_excerpt: 'Use persistência SQL relacional.',
              confidence: 0.82,
            },
          ],
          status_counts: { proposed: 150, provisional: 10 },
          domain_counts: { Dados: 120, Integração: 40 },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          items: [
            {
              id: 'example:1',
              title: 'Persistência SQL',
              domain: 'Dados',
              status: 'proposed',
              tokens: 1024,
              context_excerpt: 'Cenário de pagamentos com auditoria.',
              decision_excerpt: 'Use persistência SQL relacional.',
              confidence: 0.82,
            },
          ],
          total: 2,
          offset: 0,
          limit: 12,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          items: [
            {
              id: 'example:2',
              title: 'Integração assíncrona',
              domain: 'Integração',
              status: 'provisional',
              tokens: 840,
              context_excerpt: 'Vídeos podem levar quinze minutos.',
              decision_excerpt: null,
              confidence: 0.6,
            },
          ],
          total: 2,
          offset: 1,
          limit: 12,
        }),
      })
    vi.stubGlobal('fetch', fetch)

    render(<DatasetPage />)

    expect(
      await screen.findByText(/Dataset v0.4.0-adr-dialogue/),
    ).toBeInTheDocument()
    expect(screen.getByText('160')).toBeInTheDocument()
    expect(screen.getByText('Persistência SQL')).toBeInTheDocument()
    expect(
      screen.getAllByText('Use persistência SQL relacional.'),
    ).toHaveLength(2)
    expect(screen.getByText('150')).toBeInTheDocument()
    expect(screen.queryByText('248')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Carregar mais' }))

    expect(await screen.findByText('Integração assíncrona')).toBeInTheDocument()
    expect(screen.getByText('Perguntas em aberto')).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledTimes(3)
  })
})
