type SourceMetadata = { landing_path?: string; apply_source_path?: string };
declare global {
  interface Window {
    spaceFunnel?: {
      track: (name: string) => void;
      once: (name: string) => void;
      sources: () => SourceMetadata;
    };
  }
}
export function trackApplication(name: 'application_started' | 'application_submitted') {
  try {
    if (name === 'application_started') window.spaceFunnel?.once(name);
    else window.spaceFunnel?.track(name);
  } catch { /* A blocked tracker must not interrupt submission. */ }
}
export function sourceMetadata(): SourceMetadata {
  try { return window.spaceFunnel?.sources() || {}; }
  catch { return {}; }
}
