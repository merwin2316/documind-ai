"use client";

import React, { useState } from "react";
import { GrokTextLogo } from "./ui/GrokLogo";
import { Mic, ArrowRight, Paperclip, ChevronDown, Rocket } from "lucide-react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { cn } from "@/lib/utils";

interface GrokHomeProps {
    onSendMessage: (message: string) => void;
    isLoading?: boolean;
}

export function GrokHome({ onSendMessage, isLoading }: GrokHomeProps) {
    const [input, setInput] = useState("");

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (input.trim() && !isLoading) {
            onSendMessage(input);
            setInput("");
        }
    };

    return (
        <div className="flex flex-col items-center justify-center h-full w-full max-w-4xl mx-auto px-4 relative">
            {/* Centered Logo */}
            <div className="mb-12 transform scale-150">
                <GrokTextLogo className="text-white w-48 h-16" />
            </div>

            {/* Main Input Area */}
            <div className="w-full max-w-2xl relative z-10">
                <form onSubmit={handleSubmit} className="relative group">
                    <div className="absolute left-4 top-1/2 -translate-y-1/2 text-muted-foreground/50 hover:text-white transition-colors cursor-pointer">
                        <Paperclip className="w-5 h-5" />
                    </div>

                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="What do you want to know?"
                        className="w-full bg-[#0a0a0a] border border-white/10 rounded-2xl py-5 pl-12 pr-32 text-lg text-white placeholder:text-zinc-600 focus:outline-none focus:border-zinc-700/50 transition-all shadow-xl"
                        disabled={isLoading}
                    />

                    {/* Right Action Buttons */}
                    <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-2">
                        {/* Auto Dropdown Pll */}
                        <div className="flex items-center gap-1 px-3 py-1.5 bg-[#1a1a1a] rounded-full text-xs font-medium text-zinc-400 hover:text-white hover:bg-zinc-800 cursor-pointer transition-colors border border-white/5">
                            <Rocket className="w-3 h-3" />
                            <span>Auto</span>
                            <ChevronDown className="w-3 h-3 opacity-50 ml-1" />
                        </div>

                        {/* Voice Button */}
                        <div className="w-9 h-9 flex items-center justify-center rounded-full bg-white text-black hover:bg-zinc-200 cursor-pointer transition-colors">
                            <Mic className="w-5 h-5" />
                        </div>
                    </div>
                </form>
            </div>

            {/* Footer / Connect X Account Pill */}
            {/* Positioned at bottom center or just below input */}
            <div className="mt-20">
                <div className="flex items-center gap-4 bg-[#0a0a0a] border border-white/10 rounded-full pl-5 pr-2 py-2 max-w-md mx-auto shadow-2xl">
                    <div className="w-5 h-5 bg-white text-black rounded-full flex items-center justify-center font-bold text-xs">X</div>
                    <div className="flex flex-col">
                        <span className="text-sm font-semibold text-white">Connect your X account</span>
                        <span className="text-[10px] text-zinc-500">Unlock early features and personalized content.</span>
                    </div>
                    <Button size="sm" variant="outline" className="ml-auto rounded-full bg-transparent border-white/20 hover:bg-white/10 text-white h-8 text-xs px-4">
                        Connect
                    </Button>
                </div>
            </div>
        </div>
    );
}
