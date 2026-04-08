"use client";

import React from "react";
import Image from "next/image";
import { AnimatedChatInput } from "./AnimatedChatInput";

interface DashboardHomeProps {
    onSendMessage: (message: string) => void;
    onFileUpload: (file: File) => void;
    isLoading?: boolean;
}

export function DashboardHome({ onSendMessage, onFileUpload, isLoading }: DashboardHomeProps) {
    const [input, setInput] = React.useState("");

    const handleSend = () => {
        onSendMessage(input);
        setInput("");
    };

    return (
        <div className="flex flex-col items-center justify-center h-full w-full max-w-4xl mx-auto px-4 relative">
            {/* Centered Logo */}
            <div className="mb-12 flex flex-col items-center gap-6">
                {/* Simple Bold Logo */}
                <div className="flex items-center gap-4">
                    <div className="w-16 h-16 rounded-2xl bg-white flex items-center justify-center">
                        <span className="text-black text-4xl font-bold">Ø</span>
                    </div>
                    <div>
                        <h1 className="text-5xl font-semibold text-white">
                            DocuMind AI
                        </h1>
                    </div>
                </div>
                <h2 className="text-white/50 text-lg font-normal">What do you want to know?</h2>
            </div>

            {/* Main Input Area - REUSING the Chat Input Component for consistency */}
            <div className="w-full max-w-2xl relative z-10 transition-all duration-500 ease-out transform translate-y-0">
                <AnimatedChatInput
                    value={input}
                    onChange={setInput}
                    onSend={handleSend}
                    onFileUpload={onFileUpload}
                    isLoading={isLoading}
                    placeholder="What do you want to know?"
                />
            </div>

            {/* Footer / Connect Links - Renamed/Rebranded */}
            <div className="mt-16 opacity-0 animate-in fade-in slide-in-from-bottom-4 duration-1000 fill-mode-forwards" style={{ animationDelay: '0.2s' }}>
                <div className="flex items-center gap-4 bg-[#111] border border-white/5 rounded-full pl-5 pr-2 py-2 max-w-md mx-auto hover:border-white/10 transition-colors cursor-default">
                    <div className="w-5 h-5 bg-white text-black rounded-full flex items-center justify-center font-bold text-xs font-serif">F</div>
                    <div className="flex flex-col">
                        <span className="text-sm font-semibold text-white">Connect Data Sources</span>
                        <span className="text-[10px] text-zinc-500">Connect your tools for personalized context.</span>
                    </div>
                    <button className="ml-auto rounded-full bg-white/5 hover:bg-white/10 border border-white/10 text-white h-7 text-xs px-4 transition-colors">
                        Connect
                    </button>
                </div>
            </div>
        </div>
    );
}
