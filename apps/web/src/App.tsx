import { useState } from 'react'

import { AnalysisFlow } from './features/analysis/AnalysisFlow'
import { AboutPage } from './features/about/AboutPage'
import { TrainingDashboard } from './features/training/TrainingDashboard'
import { DatasetPage } from './features/dataset/DatasetPage'

type WorkspaceView = 'analysis' | 'training' | 'dataset' | 'about'

type NavigationItem = {
  label: string
  icon: string
  view?: WorkspaceView
}

const navigation: NavigationItem[] = [
  { label: 'Testar IA', icon: '✦', view: 'analysis' },
  { label: 'Treinamento', icon: '◌', view: 'training' },
  { label: 'Base de dados', icon: '▣', view: 'dataset' },
  { label: 'Sobre', icon: 'i', view: 'about' },
]

export function App() {
  const [view, setView] = useState<WorkspaceView>('analysis')
  const activeItem = navigation.find((item) => item.view === view)

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Navegação principal">
        <a className="brand" href="#workspace" aria-label="ADR Forge, início">
          <span>AF</span>
          <strong>
            adr<span>forge</span>
          </strong>
        </a>
        <nav>
          <p>Workspace</p>
          {navigation.map((item) => (
            <button
              key={item.label}
              className={item.view === view ? 'active' : undefined}
              type="button"
              disabled={!item.view}
              aria-current={item.view === view ? 'page' : undefined}
              onClick={() => item.view && setView(item.view)}
            >
              <span aria-hidden="true">{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="storage-meter">
            <span />
          </div>
          <p>
            <strong>Ambiente local</strong>
            <br />
            Pronto para analisar
          </p>
          <button type="button" aria-label="Abrir configurações">
            ⚙
          </button>
        </div>
      </aside>
      <div className="content-shell">
        <header className="topbar">
          <div>
            <span className="crumb">Workspace</span>
            <span aria-hidden="true">/</span>
            <strong>{activeItem?.label}</strong>
          </div>
          <div className="topbar-actions">
            <span className="online">
              <i /> Sistema online
            </span>
            <button type="button">MS</button>
          </div>
        </header>
        {view === 'analysis' ? (
          <AnalysisFlow />
        ) : view === 'training' ? (
          <TrainingDashboard />
        ) : view === 'dataset' ? (
          <DatasetPage />
        ) : (
          <AboutPage />
        )}
      </div>
    </div>
  )
}
