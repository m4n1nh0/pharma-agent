import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useAuth } from "@/auth/AuthContext";
import { useToast } from "@/components/Toast";
import { ApiError } from "@/api/client";

export function LoginPage() {
  const [tab, setTab] = useState<"login" | "register">("login");
  const { isAuthenticated, login, register } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();

  // Navega só depois que o React re-renderiza com o auth atualizado — o router lê
  // `context.auth` (injetado em App.tsx) durante o render, então chamar navigate()
  // direto após o login resolver corre o risco de o beforeLoad ainda ver o contexto antigo.
  useEffect(() => {
    if (isAuthenticated) navigate({ to: "/drug" });
  }, [isAuthenticated, navigate]);

  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginBusy, setLoginBusy] = useState(false);

  const [regName, setRegName] = useState("");
  const [regEmail, setRegEmail] = useState("");
  const [regRole, setRegRole] = useState("farmaceutico");
  const [regCrf, setRegCrf] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regBusy, setRegBusy] = useState(false);

  async function handleLogin(e: FormEvent) {
    e.preventDefault();
    setLoginBusy(true);
    try {
      await login(loginEmail, loginPassword);
      toast("Bem-vindo(a)!", "success");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Falha no login", "error");
    } finally {
      setLoginBusy(false);
    }
  }

  async function handleRegister(e: FormEvent) {
    e.preventDefault();
    setRegBusy(true);
    try {
      await register({ name: regName, email: regEmail, password: regPassword, role: regRole, crm_crf: regCrf || null });
      toast("Conta criada com sucesso!", "success");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Erro no cadastro", "error");
    } finally {
      setRegBusy(false);
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <div className="auth-logo">
          <div className="auth-logo-icon">⚕</div>
          <div className="auth-logo-text">
            Pharma<span>AI</span>
          </div>
        </div>

        <div className="auth-tabs">
          <button className={`auth-tab ${tab === "login" ? "active" : ""}`} onClick={() => setTab("login")} type="button">
            Entrar
          </button>
          <button className={`auth-tab ${tab === "register" ? "active" : ""}`} onClick={() => setTab("register")} type="button">
            Cadastrar
          </button>
        </div>

        {tab === "login" ? (
          <form className="auth-form" onSubmit={handleLogin}>
            <div className="form-field">
              <label>E-mail</label>
              <input type="email" value={loginEmail} onChange={(e) => setLoginEmail(e.target.value)} placeholder="seu@email.com" required />
            </div>
            <div className="form-field">
              <label>Senha</label>
              <input type="password" value={loginPassword} onChange={(e) => setLoginPassword(e.target.value)} placeholder="••••••••" required />
            </div>
            <button type="submit" className="btn btn-primary" disabled={loginBusy}>
              {loginBusy ? "Entrando..." : "Entrar"}
            </button>
          </form>
        ) : (
          <form className="auth-form" onSubmit={handleRegister}>
            <div className="form-field">
              <label>Nome completo</label>
              <input type="text" value={regName} onChange={(e) => setRegName(e.target.value)} placeholder="Dr(a). Seu Nome" required />
            </div>
            <div className="form-field">
              <label>E-mail profissional</label>
              <input type="email" value={regEmail} onChange={(e) => setRegEmail(e.target.value)} placeholder="seu@email.com" required />
            </div>
            <div className="form-field">
              <label>Perfil</label>
              <select value={regRole} onChange={(e) => setRegRole(e.target.value)}>
                <option value="farmaceutico">Farmacêutico(a)</option>
                <option value="medico">Médico(a)</option>
              </select>
            </div>
            <div className="form-field">
              <label>CRM / CRF</label>
              <input type="text" value={regCrf} onChange={(e) => setRegCrf(e.target.value)} placeholder="CRF-SE 12345" />
            </div>
            <div className="form-field">
              <label>Senha (mín. 6 caracteres)</label>
              <input type="password" value={regPassword} onChange={(e) => setRegPassword(e.target.value)} placeholder="••••••••" minLength={6} required />
            </div>
            <button type="submit" className="btn btn-primary" disabled={regBusy}>
              {regBusy ? "Criando conta..." : "Criar conta"}
            </button>
          </form>
        )}

        <div className="demo-hint">
          <strong>Demo disponível:</strong>
          <br />
          farmacêutico: <strong>demo@pharma.com</strong> / <strong>demo123</strong>
          <br />
          médico: <strong>medico@pharma.com</strong> / <strong>medico123</strong>
        </div>
      </div>
    </div>
  );
}
