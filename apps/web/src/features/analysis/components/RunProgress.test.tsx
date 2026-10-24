import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { RunProgress } from './RunProgress'

describe('RunProgress', () => {
  it('informa que o modelo está sendo carregado antes de a execução ser criada', () => {
    render(<RunProgress run={null} rawOutput={null} isStarting />)

    expect(
      screen.getByText('Carregando o modelo na GPU…'),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/primeira execução, o carregamento e a quantização/i),
    ).toBeInTheDocument()
  })
})
