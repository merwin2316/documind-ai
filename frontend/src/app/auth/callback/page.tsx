"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { Loader2 } from "lucide-react";

export default function AuthCallbackPage() {
    const router = useRouter();

    useEffect(() => {
        // Handle email verification callback
        const handleCallback = async () => {
            // Check for email verification token in URL
            const { data, error } = await supabase.auth.getSession();
            
            if (!error && data.session) {
                // Store token and redirect
                localStorage.setItem("supabase_token", data.session.access_token);
                router.push("/chat");
            } else {
                // No session - redirect to login
                router.push("/login");
            }
        };

        // Listen for auth state changes (email verification, etc.)
        const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
            if (event === 'SIGNED_IN' && session) {
                // Store token for our manual API calls helper
                localStorage.setItem("supabase_token", session.access_token);
                router.push("/chat");
            } else if (event === 'TOKEN_REFRESHED' && session) {
                localStorage.setItem("supabase_token", session.access_token);
            }
        });

        // Try to get session immediately
        handleCallback();

        return () => {
            subscription.unsubscribe();
        };
    }, [router]);

    return (
        <div className="flex h-screen w-full items-center justify-center bg-[#0A0A0B]">
            <div className="text-center space-y-4">
                <Loader2 className="w-8 h-8 animate-spin mx-auto text-violet-400" />
                <p className="text-white/60">Authenticating...</p>
            </div>
        </div>
    );
}
