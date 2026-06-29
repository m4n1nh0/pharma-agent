import { Link, Outlet, useNavigate } from "@tanstack/react-router";
import { useAuth } from "@/auth/AuthContext";
import { createContext, useContext, useState } from "react";
import { AgentStepsPanel } from "@/components/AgentStepsPanel";

const ROLE_LABEL: Record<string, string> = { farmaceutico: "Farm.", medico: "Médico", admin: "Admin" };

interface AgentStepsContextValue {
  steps: string[];
  setSteps: (steps: string[]) => void;
}

const AgentStepsContext = createContext<AgentStepsContextValue | null>(null);

// Páginas filhas usam isso para publicar os passos do agente no painel direito.
export function useAgentSteps(): AgentStepsContextValue {
  const ctx = useContext(AgentStepsContext);
  if (!ctx) throw new Error("useAgentSteps deve ser usado dentro de <AppLayout>");
  return ctx;
}

export function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [steps, setSteps] = useState<string[]>([]);

  function handleLogout() {
    logout();
    navigate({ to: "/login" });
  }

  return (
    <div className="app-screen">
      <div className="topbar">
        <div className="topbar-logo">
          <div className="topbar-logo-dot" />
          PharmaAI
        </div>
        <nav className="topbar-nav">
          <Link to="/drug" className="nav-btn" activeProps={{ className: "nav-btn active" }}>
            💊 Medicamento
          </Link>
          <Link to="/interactions" className="nav-btn" activeProps={{ className: "nav-btn active" }}>
            ⚡ Interações
          </Link>
          <Link to="/prescription" className="nav-btn" activeProps={{ className: "nav-btn active" }}>
            📋 Prescrição
          </Link>
        </nav>
        <div className="topbar-user">
          <div className="user-chip">
            <div className="user-avatar">{user?.name?.[0]?.toUpperCase() ?? "U"}</div>
            <span>{user?.name?.split(" ").slice(0, 2).join(" ") ?? "Usuário"}</span>
          </div>
          <span className="role-badge">{ROLE_LABEL[user?.role ?? ""] ?? user?.role}</span>
          <button className="btn btn-ghost" onClick={handleLogout} style={{ padding: "6px 14px", fontSize: 12 }}>
            Sair
          </button>
        </div>
      </div>

      <div className="main-layout">
        <div className="panel">
          <AgentStepsContext.Provider value={{ steps, setSteps }}>
            <Outlet />
          </AgentStepsContext.Provider>
        </div>
        <div className="panel-right">
          <div className="steps-panel">
            <div className="panel-title">Raciocínio do Agente</div>
            <div>
              <AgentStepsPanel steps={steps} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
