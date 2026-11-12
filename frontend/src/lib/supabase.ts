/**
 * Supabase Auth client for DocuMind AI (Next.js 16 + @supabase/ssr).
 * Manages user sessions, token storage, and authentication state.
 */
import { createBrowserClient } from "@supabase/ssr";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

export const isSupabaseConfigured = Boolean(
  supabaseUrl &&
  supabaseAnonKey &&
  supabaseUrl.startsWith("http") &&
  !supabaseUrl.includes("placeholder")
);

// Fallback to a placeholder URL/key if not configured to prevent client instantiation crashes
const effectiveUrl = isSupabaseConfigured ? supabaseUrl : "https://placeholder.supabase.co";
const effectiveKey = isSupabaseConfigured ? supabaseAnonKey : "placeholder-anon-key";

export const supabase = createBrowserClient(effectiveUrl, effectiveKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
});

export default supabase;
