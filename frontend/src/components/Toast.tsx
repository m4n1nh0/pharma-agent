import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";

type ToastType = "" | "error" | "success";

interface ToastState {
  message: string;
  type: ToastType;
  visible: boolean;
}

const ToastContext = createContext<((message: string, type?: ToastType) => void) | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<ToastState>({ message: "", type: "", visible: false });
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  const show = useCallback((message: string, type: ToastType = "") => {
    setToast({ message, type, visible: true });
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setToast((t) => ({ ...t, visible: false })), 4000);
  }, []);

  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className={`toast ${toast.visible ? "show" : ""} ${toast.type}`}>{toast.message}</div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast deve ser usado dentro de <ToastProvider>");
  return ctx;
}
