"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { GrokLogo } from "@/components/ui/GrokLogo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AlertCircle, Loader2, Lock, Mail, CheckCircle2 } from "lucide-react";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectPath = searchParams.get("redirect") || "/chat";
  const verified = searchParams.get("verified") === "true";

  const { user, signInWithPassword, isConfigured } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (user) {
      router.replace(redirectPath);
    }
  }, [user, router, redirectPath]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email || !password) {
      setError("Please enter both email and password.");
      return;
    }

    setLoading(true);
    const { error: signInError } = await signInWithPassword(email, password);
    setLoading(false);

    if (signInError) {
      setError(signInError.message || "Failed to sign in. Please verify your credentials.");
      return;
    }

    router.replace(redirectPath);
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-black px-4 py-12 text-white sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-8 rounded-2xl border border-white/10 bg-zinc-950 p-8 shadow-2xl">
        <div className="flex flex-col items-center text-center">
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-white/10 bg-white/5">
            <GrokLogo size={28} />
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-white">Welcome to DocuMind AI</h2>
          <p className="mt-2 text-sm text-zinc-400">
            Sign in to access your intelligent document vault and RAG assistant
          </p>
        </div>

        {!isConfigured && (
          <div className="rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-3.5 text-xs text-yellow-300">
            <div className="flex items-center gap-2 font-medium">
              <AlertCircle className="h-4 w-4 shrink-0 text-yellow-400" />
              <span>Supabase Not Configured</span>
            </div>
            <p className="mt-1 text-yellow-200/80">
              Provide <code className="rounded bg-black/40 px-1 py-0.5">NEXT_PUBLIC_SUPABASE_URL</code> and{" "}
              <code className="rounded bg-black/40 px-1 py-0.5">NEXT_PUBLIC_SUPABASE_ANON_KEY</code> in{" "}
              <code className="rounded bg-black/40 px-1 py-0.5">.env.local</code> to connect your Supabase project.
            </p>
          </div>
        )}

        {verified && (
          <div className="flex items-center gap-2 rounded-lg border border-green-500/30 bg-green-500/10 p-3 text-sm text-green-300">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-green-400" />
            <span>Email verified successfully. You can now sign in.</span>
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
            <AlertCircle className="h-4 w-4 shrink-0 text-red-400" />
            <span>{error}</span>
          </div>
        )}

        <form className="mt-6 space-y-5" onSubmit={handleSubmit}>
          <div className="space-y-1.5">
            <Label htmlFor="email" className="text-xs font-medium text-zinc-300">
              Email Address
            </Label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
              <Input
                id="email"
                type="email"
                autoComplete="email"
                required
                placeholder="name@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="border-white/10 bg-zinc-900/80 pl-9 text-white placeholder-zinc-500 focus-visible:ring-1 focus-visible:ring-white/30"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Label htmlFor="password" className="text-xs font-medium text-zinc-300">
                Password
              </Label>
            </div>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="border-white/10 bg-zinc-900/80 pl-9 text-white placeholder-zinc-500 focus-visible:ring-1 focus-visible:ring-white/30"
              />
            </div>
          </div>

          <Button
            type="submit"
            disabled={loading}
            className="w-full bg-white font-medium text-black transition-colors hover:bg-zinc-200 disabled:opacity-50"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                Signing in...
              </span>
            ) : (
              "Sign In"
            )}
          </Button>
        </form>

        <div className="pt-2 text-center text-xs text-zinc-400">
          Don&apos;t have an account?{" "}
          <Link
            href={`/register${redirectPath !== "/chat" ? `?redirect=${encodeURIComponent(redirectPath)}` : ""}`}
            className="font-medium text-white underline-offset-4 hover:underline"
          >
            Create an account
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-black text-white">
          <Loader2 className="h-8 w-8 animate-spin text-white/70" />
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}

