const principles = [
  {
    number: '01',
    title: 'Decidir com contexto',
    text: 'Transformamos perguntas de arquitetura em decisões registradas, comparáveis e fáceis de revisar.',
  },
  {
    number: '02',
    title: 'Treinar com evidência',
    text: 'Cada experimento deixa rastros: dataset, configuração, métricas e artefatos locais.',
  },
  {
    number: '03',
    title: 'Aprender fazendo',
    text: 'O laboratório aproxima teoria e prática para testar hipóteses sem esconder as limitações do modelo.',
  },
]

export function AboutPage() {
  return (
    <main className="about-page" id="workspace">
      <section className="about-hero" aria-labelledby="about-title">
        <div>
          <p className="section-kicker">Sobre o projeto · ADR Forge</p>
          <h1 id="about-title">Um laboratório para pensar melhor sobre software.</h1>
          <p className="about-lede">
            O ADR Forge é um ambiente local para explorar decisões de arquitetura
            com inteligência artificial, registrar o raciocínio e transformar cada
            tentativa em aprendizado reutilizável.
          </p>
        </div>
        <div className="about-mark" aria-hidden="true">
          <span>AF</span>
          <small>learn / test / decide</small>
        </div>
      </section>

      <section className="about-grid" aria-label="Como o projeto funciona">
        <article className="about-card about-card--feature">
          <p className="about-card__label">O objetivo</p>
          <h2>Decisões de arquitetura que continuam úteis depois da conversa.</h2>
          <p>
            A ferramenta ajuda a estruturar cenários, explicitar restrições e
            produzir registros de decisão arquitetural (ADRs). Assim, o resultado
            não é apenas uma resposta: é um ponto de partida para o time discutir,
            validar e evoluir.
          </p>
        </article>
        <article className="about-card about-card--accent">
          <p className="about-card__label">Fine-tuning</p>
          <h2>Ensinar um modelo a reconhecer o contrato do domínio.</h2>
          <p>
            Experimentamos fine-tuning com QLoRA em modelos locais para adaptar o
            comportamento às necessidades de decisões arquiteturais. O processo é
            deliberadamente observável: dataset versionado, execução reproduzível,
            avaliação e artefatos sob nosso controle.
          </p>
        </article>
      </section>

      <section className="about-lab" aria-labelledby="lab-title">
        <div className="about-lab__heading">
          <p className="section-kicker">Modo laboratório</p>
          <h2 id="lab-title">Aprendizado é parte do produto.</h2>
          <p>
            O projeto é um espaço seguro para testar ideias, medir resultados e
            documentar o que não funcionou. A curiosidade guia o experimento; a
            rastreabilidade transforma o experimento em conhecimento.
          </p>
        </div>
        <div className="about-principles">
          {principles.map((principle) => (
            <div className="about-principle" key={principle.number}>
              <span>{principle.number}</span>
              <div>
                <h3>{principle.title}</h3>
                <p>{principle.text}</p>
              </div>
            </div>
          ))}
        </div>
      </section>
    </main>
  )
}
