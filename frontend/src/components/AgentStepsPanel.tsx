const STEP_ICONS = ["🧠", "🔧", "📊", "✅", "🔍"];

export function AgentStepsPanel({ steps }: { steps: string[] }) {
  if (!steps.length) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">🧠</div>
        <div className="empty-state-text">Os passos de análise do agente LangGraph aparecerão aqui em tempo real</div>
      </div>
    );
  }

  const now = new Date();
  const time = `${now.getHours()}:${String(now.getMinutes()).padStart(2, "0")}:${String(now.getSeconds()).padStart(2, "0")}`;

  return (
    <>
      {steps.map((step, i) => (
        <div className="step-item" key={i}>
          <div className="step-icon">{STEP_ICONS[i % STEP_ICONS.length]}</div>
          <div>
            <div className="step-text">{step}</div>
            <div className="step-time">{time}</div>
          </div>
        </div>
      ))}
    </>
  );
}
