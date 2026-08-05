/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the backend API (e.g. the Cloud Run URL). Empty in dev. */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
