"use client";

import { useState, useEffect } from "react";
import { supabase } from "@/lib/supabase";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

export default function LoginPage() {
    const router = useRouter();
    const [isLogin, setIsLogin] = useState(true);
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    useEffect(() => {
        const checkSession = async () => {
            const { data } = await supabase.auth.getSession();
            if (data.session) {
                router.push("/chat");
            }
        };
        checkSession();
    }, [router]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);
        setSuccess(null);

        // Clean and validate email format
        const cleanEmail = email.trim().toLowerCase();

        // Check for empty email
        if (!cleanEmail) {
            setError("Please enter an email address");
            setLoading(false);
            return;
        }

        // More permissive regex - allows short local parts like "lok"
        const emailRegex = /^[a-zA-Z0-9._+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
        if (!emailRegex.test(cleanEmail)) {
            setError("Please enter a valid email address (format: name@domain.com)");
            setLoading(false);
            return;
        }

        // Additional check for minimum length before @
        const localPart = cleanEmail.split('@')[0];
        if (localPart.length < 1) {
            setError("Email address is invalid");
            setLoading(false);
            return;
        }

        // Note: Supabase may require minimum 4 characters in the local part
        // "lok" is 3 characters, which might be rejected
        if (localPart.length < 4) {
            console.warn(`Short email local part (${localPart.length} chars). Supabase typically requires at least 4 characters.`);
        }

        // Validate password
        if (password.length < 6) {
            setError("Password must be at least 6 characters long");
            setLoading(false);
            return;
        }

        try {
            if (isLogin) {
                const { data, error: signInError } = await supabase.auth.signInWithPassword({
                    email: cleanEmail,
                    password,
                });

                if (signInError) {
                    console.error("Sign in error:", signInError);
                    console.error("Error details:", {
                        message: signInError.message,
                        status: signInError.status,
                        code: signInError.code,
                        email: cleanEmail
                    });

                    if (signInError.message.includes("Invalid login credentials") || signInError.code === "invalid_credentials") {
                        throw new Error("Invalid email or password. If you just signed up, make sure to verify your email first, or try signing up again.");
                    } else if (signInError.message.includes("Email not confirmed") || signInError.message.includes("email_not_confirmed")) {
                        throw new Error("Please verify your email address before logging in. Check your inbox (and spam folder) for the verification link.");
                    } else if (signInError.message.includes("User not found") || signInError.code === "user_not_found") {
                        throw new Error("No account found with this email. Please sign up first or check your email address.");
                    } else if (signInError.message.includes("invalid") || signInError.message.includes("Invalid")) {
                        throw new Error(`Authentication error: ${signInError.message}`);
                    } else {
                        throw new Error(signInError.message || "Login failed. Please try again.");
                    }
                }

                // Success - store token and redirect
                if (data.session) {
                    localStorage.setItem("supabase_token", data.session.access_token);
                    setSuccess("Login successful! Redirecting...");
                    setTimeout(() => {
                        router.push("/chat");
                    }, 500);
                }
            } else {
                const { data, error: signUpError } = await supabase.auth.signUp({
                    email: cleanEmail,
                    password,
                    options: {
                        emailRedirectTo: window.location.origin,
                    },
                });

                if (signUpError) {
                    console.error("Sign up error:", signUpError);
                    console.error("Error details:", {
                        message: signUpError.message,
                        status: signUpError.status,
                        code: signUpError.code,
                        email: cleanEmail,
                        emailLength: cleanEmail.length
                    });

                    if (signUpError.message.includes("User already registered") || signUpError.message.includes("already registered")) {
                        throw new Error("This email is already registered. Please login instead.");
                    } else if (signUpError.message.includes("Password")) {
                        throw new Error("Password does not meet requirements. Use at least 6 characters.");
                    } else if (signUpError.message.includes("invalid") || signUpError.message.includes("Invalid") || signUpError.message.includes("email")) {
                        // Check if it's a minimum length issue (Supabase typically requires 4+ chars)
                        if (localPart.length < 4) {
                            throw new Error(`Email address must have at least 4 characters before the @ symbol. "${cleanEmail}" has only ${localPart.length} character(s). Please use a longer email address like "loktest@gmail.com" or try a different email.`);
                        }
                        // Display the actual error message from Supabase with helpful context
                        throw new Error(`Email validation failed: ${signUpError.message}. If your email is short (less than 4 characters before @), please use a longer email address.`);
                    } else {
                        throw new Error(signUpError.message || "Sign up failed. Please try again.");
                    }
                }

                // Check if email confirmation is required
                if (data.user && !data.session) {
                    setSuccess("Sign up successful! Please check your email (and spam folder) to verify your account. After verification, you can log in.");
                    // Clear form after a delay
                    setTimeout(() => {
                        setIsLogin(true);
                        setEmail("");
                        setPassword("");
                    }, 3000);
                } else if (data.session) {
                    // Email confirmation disabled - auto-logged in
                    localStorage.setItem("supabase_token", data.session.access_token);
                    setSuccess("Sign up successful! Redirecting...");
                    setTimeout(() => {
                        router.push("/chat");
                    }, 500);
                } else {
                    // Edge case: user created but no session and no confirmation required
                    setSuccess("Account created! You can now log in.");
                    setTimeout(() => {
                        setIsLogin(true);
                        setEmail("");
                        setPassword("");
                    }, 2000);
                }
            }
        } catch (err: any) {
            console.error("Auth error:", err);
            setError(err.message || "Authentication failed. Please try again.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex h-screen w-full items-center justify-center bg-[#0A0A0B]">
            <Card className="w-[400px] bg-white/[0.02] border-white/10">
                <CardHeader>
                    <CardTitle className="text-white">DocuMind AI</CardTitle>
                    <CardDescription className="text-white/60">RAG-Powered Document Chat System</CardDescription>
                </CardHeader>
                <CardContent>
                    {/* Tabs */}
                    <div className="flex mb-6 bg-white/5 rounded-lg p-1">
                        <button
                            onClick={() => {
                                setIsLogin(true);
                                setError(null);
                                setSuccess(null);
                            }}
                            className={`flex-1 py-2 px-4 rounded-md font-semibold transition-colors text-sm ${isLogin
                                ? "bg-white/10 text-white"
                                : "text-white/60 hover:text-white/90"
                                }`}
                        >
                            Login
                        </button>
                        <button
                            onClick={() => {
                                setIsLogin(false);
                                setError(null);
                                setSuccess(null);
                            }}
                            className={`flex-1 py-2 px-4 rounded-md font-semibold transition-colors text-sm ${!isLogin
                                ? "bg-white/10 text-white"
                                : "text-white/60 hover:text-white/90"
                                }`}
                        >
                            Sign Up
                        </button>
                    </div>

                    {/* Error Message */}
                    {error && (
                        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm">
                            {error}
                        </div>
                    )}

                    {/* Success Message */}
                    {success && (
                        <div className="mb-4 p-3 bg-green-500/10 border border-green-500/20 rounded-lg text-green-400 text-sm">
                            {success}
                        </div>
                    )}

                    {/* Form */}
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div>
                            <Label htmlFor="email" className="text-white/70 mb-2 block">
                                Email
                            </Label>
                            <Input
                                id="email"
                                type="email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                placeholder="your@email.com"
                                required
                                className="bg-white/5 border-white/10 text-white placeholder:text-white/30"
                                disabled={loading}
                            />
                            {email && email.includes('@') && (() => {
                                const localPart = email.split('@')[0].trim();
                                return localPart.length > 0 && localPart.length < 4 ? (
                                    <p className="text-xs text-yellow-400 mt-1">
                                        ⚠️ Email must have at least 4 characters before @. Current: {localPart.length} character(s).
                                    </p>
                                ) : null;
                            })()}
                        </div>

                        <div>
                            <Label htmlFor="password" className="text-white/70 mb-2 block">
                                Password
                            </Label>
                            <Input
                                id="password"
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                placeholder="••••••••"
                                required
                                minLength={6}
                                className="bg-white/5 border-white/10 text-white placeholder:text-white/30"
                                disabled={loading}
                            />
                            {!isLogin && (
                                <p className="text-xs text-white/50 mt-1">Password must be at least 6 characters</p>
                            )}
                        </div>

                        <Button
                            type="submit"
                            disabled={loading}
                            className="w-full bg-violet-500 hover:bg-violet-600 text-white"
                        >
                            {loading ? (
                                <>
                                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                    Please wait...
                                </>
                            ) : (
                                isLogin ? "Login" : "Sign Up"
                            )}
                        </Button>
                    </form>
                </CardContent>
            </Card>
        </div>
    );
}
