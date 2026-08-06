/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Базовый URL API (DRF), по умолчанию /api/v1. */
  readonly VITE_API_BASE_URL?: string;
  /** DSN Sentry (опционально). */
  readonly VITE_SENTRY_DSN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
