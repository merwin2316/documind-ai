/**
 * Supabase stub — no-op module for local-only mode.
 * All auth methods return dummy values so components that
 * still reference supabase.auth.* don't crash.
 */

const noopAuth = {
  getSession: async () => ({
    data: { session: null },
    error: null,
  }),
  getUser: async () => ({
    data: { user: null },
    error: null,
  }),
  signOut: async () => ({ error: null }),
  signInWithPassword: async () => ({
    data: { session: null, user: null },
    error: null,
  }),
  signUp: async () => ({
    data: { session: null, user: null },
    error: null,
  }),
  onAuthStateChange: (_callback: any) => ({
    data: {
      subscription: {
        unsubscribe: () => {},
      },
    },
  }),
};

export const supabase = {
  auth: noopAuth,
  storage: {
    from_: () => ({
      createSignedUrl: async () => ({ data: null, error: new Error("Local mode") }),
    }),
  },
};
