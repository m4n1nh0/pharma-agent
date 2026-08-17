/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Origem da API. Vazia = mesma origem (dev com proxy, ou API servindo a SPA). */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
