interface ImportMetaEnv {
  readonly VITE_DESKTOP_COMPANION_URL?: string;
  readonly VITE_DESKTOP_COMPANION_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
