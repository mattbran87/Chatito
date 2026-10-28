/** The lint hook's per-session values. */
declare module 'claude-code' {
  interface PluginState {
    'simple-english': {
      /** True after a simple-english skill loads in this session. */
      armed: boolean
      /** Lint passes per file path since the last skill load. */
      lintCounts: Record<string, number>
    }
  }
}
