"use client";

import { useState, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import {
    Settings,
    FileText,
    HelpCircle,
    LogOut,
    Globe,
    MessageSquare,
    Clock,
} from "lucide-react";
import { Button } from "./ui/button";
import { listConversations } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { motion } from "framer-motion";

interface Conversation {
    id: string;
    title: string;
    created_at: string;
}

interface AppSidebarProps {
    currentConversationId: string | null;
    onSelectConversation?: (id: string | null) => void;
    onNewChat?: () => void;
    refreshTrigger?: number;
}

export function AppSidebar({
    currentConversationId,
    onSelectConversation,
    onNewChat,
    refreshTrigger,
}: AppSidebarProps) {
    const router = useRouter();
    const pathname = usePathname();
    const { user, signOut } = useAuth();
    const [conversations, setConversations] = useState<Conversation[]>([]);

    useEffect(() => {
        loadConversations();
    }, []);

    useEffect(() => {
        if (refreshTrigger !== undefined) {
            loadConversations();
        }
    }, [refreshTrigger]);

    const loadConversations = async () => {
        try {
            const convs = await listConversations(0, 50);
            setConversations(convs.map((conv: any) => ({
                id: conv.conversation_id,
                title: conv.title || "Untitled",
                created_at: conv.created_at
            })));
        } catch (e) {
            console.error("Failed to load conversations", e);
        }
    };

    const handleSignOut = async () => {
        await signOut();
    };

    const groupConversations = () => {
        const now = new Date();
        const today: Conversation[] = [];
        const thisYear: Conversation[] = [];

        conversations.forEach((conv) => {
            const date = new Date(conv.created_at);
            const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));

            if (diffDays === 0) {
                today.push(conv);
            } else if (date.getFullYear() === now.getFullYear()) {
                thisYear.push(conv);
            }
        });

        return { today, thisYear };
    };

    const grouped = groupConversations();
    const currentYear = new Date().getFullYear();

    const menuItems = [
        { icon: MessageSquare, label: "Chat", id: "chat", action: onNewChat },
        { icon: Settings, label: "Settings", id: "settings" },
        { icon: FileText, label: "Vault", id: "vault" },
        { icon: Globe, label: "Knowledge Base", id: "knowledge-base" },
        { icon: HelpCircle, label: "Help", id: "help", subMenu: true },
    ];

    return (
        <div className="flex flex-col h-screen w-64 bg-black border-r border-white/5 text-white/90 font-sans z-50">
            {/* Top Logo Area */}
            <div className="p-6 pb-4">
                <div
                    onClick={onNewChat}
                    className="cursor-pointer select-none flex items-center gap-3 group"
                >
                    {/* Simple Bold Icon */}
                    <div className="w-8 h-8 rounded-lg bg-white flex items-center justify-center">
                        <span className="text-black text-xl font-bold">Ø</span>
                    </div>
                    {/* Logo Text */}
                    <div>
                        <div className="font-semibold text-base text-white">
                            DocuMind AI
                        </div>
                    </div>
                </div>
            </div>

            {/* Navigation Items */}
            <div className="px-3 space-y-1 pb-4">
                {menuItems.map((item) => (
                    <button
                        key={item.id}
                        className={cn(
                            "flex items-center gap-3 px-3 py-2.5 text-[14px] font-medium rounded-lg transition-colors hover:bg-white/5 text-left w-full",
                            pathname === "/" + item.id ? "bg-white/5 text-white" : "text-white/60 hover:text-white"
                        )}
                        onClick={() => {
                            if (item.action) {
                                item.action();
                            } else if (item.id === "vault") {
                                router.push("/vault");
                            } else if (item.id === "knowledge-base") {
                                router.push("/knowledge-base");
                            } else if (item.id === "settings") {
                                // router.push("/settings");
                            }
                        }}
                    >
                        <item.icon className="w-4 h-4" strokeWidth={2} />
                        <span>{item.label}</span>
                        {item.subMenu && <span className="ml-auto text-white/40">›</span>}
                    </button>
                ))}
            </div>

            {/* History Section */}
            <div className="flex-1 overflow-y-auto px-3 pb-4">
                <div className="flex items-center gap-2 px-3 py-2 mb-3">
                    <Clock className="w-4 h-4 text-white/70" strokeWidth={2} />
                    <h2 className="text-[15px] font-semibold text-white">History</h2>
                </div>

                <div className="space-y-4">
                    {/* Today */}
                    {grouped.today.length > 0 && (
                        <div>
                            <p className="text-xs text-white/40 mb-2 px-3 font-medium">Today</p>
                            <div className="space-y-0.5">
                                {grouped.today.map((conv) => (
                                    <motion.button
                                        key={conv.id}
                                        onClick={() => onSelectConversation?.(conv.id)}
                                        className={cn(
                                            "w-full text-left px-3 py-2 rounded-lg text-[14px] transition-colors truncate",
                                            currentConversationId === conv.id
                                                ? "bg-white/10 text-white"
                                                : "text-white/70 hover:bg-white/5 hover:text-white"
                                        )}
                                        whileHover={{ x: 2 }}
                                    >
                                        {conv.title}
                                    </motion.button>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* This Year */}
                    {grouped.thisYear.length > 0 && (
                        <div>
                            <p className="text-xs text-white/40 mb-2 px-3 font-medium">{currentYear}</p>
                            <div className="space-y-0.5">
                                {grouped.thisYear.slice(0, 5).map((conv) => (
                                    <motion.button
                                        key={conv.id}
                                        onClick={() => onSelectConversation?.(conv.id)}
                                        className={cn(
                                            "w-full text-left px-3 py-2 rounded-lg text-[14px] transition-colors truncate",
                                            currentConversationId === conv.id
                                                ? "bg-white/10 text-white"
                                                : "text-white/70 hover:bg-white/5 hover:text-white"
                                        )}
                                        whileHover={{ x: 2 }}
                                    >
                                        {conv.title}
                                    </motion.button>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* See all link */}
                    {conversations.length > 0 && (
                        <button className="w-full text-left px-3 py-2 text-[14px] text-white/50 hover:text-white/70 transition-colors">
                            See all
                        </button>
                    )}
                </div>
            </div>

            {/* User Profile & Sign Out */}
            <div className="p-3 border-t border-white/5 space-y-2">
                {user?.email && (
                    <div className="flex items-center gap-2.5 px-3 py-1.5 text-xs text-white/50 truncate">
                        <div className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
                        <span className="truncate">{user.email}</span>
                    </div>
                )}
                <button
                    onClick={handleSignOut}
                    className="flex items-center gap-3 px-3 py-2 text-[14px] font-medium rounded-lg transition-colors hover:bg-white/5 text-left w-full text-white/60 hover:text-white"
                >
                    <LogOut className="w-4 h-4" strokeWidth={2} />
                    <span>Sign Out</span>
                </button>
            </div>
        </div>
    );
}
