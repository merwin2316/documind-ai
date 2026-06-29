"use client";

import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import {
    Settings,
    CircleCheck, // For Tasks
    FileText, // For Files
    HelpCircle,
    Zap, // Upgrade plan
    LogOut,
    User,
    Search, // Using Search or similar for Grokipedia/Globe
    Globe,
    Bell
} from "lucide-react";
import { GrokLogo } from "./GrokLogo";
import { Button } from "./button";

interface ChatSidebarProps {
    currentConversationId: string | null;
    onSelectConversation?: (id: string | null) => void;
    onNewChat?: () => void;
    refreshTrigger?: number;
}

export function ChatSidebar({
    currentConversationId,
    onSelectConversation,
    onNewChat,
}: ChatSidebarProps) {
    const router = useRouter();
    const pathname = usePathname();

    const handleSignOut = async () => {
        router.push("/chat");
    };

    const menuItems = [
        { icon: Settings, label: "Settings", id: "settings" },
        { icon: CircleCheck, label: "Tasks", id: "tasks", hasNotification: false },
        { icon: FileText, label: "Files", id: "files" },
        { icon: Globe, label: "Grokipedia", id: "grokipedia" },
        { icon: HelpCircle, label: "Help", id: "help", subMenu: true },
        { icon: Zap, label: "Upgrade plan", id: "upgrade" },
    ];

    return (
        <div className="flex flex-col h-screen w-64 bg-black border-none text-white/90 font-sans">
            {/* Top Logo Area - Hidden in screenshot but good for returning Home */}
            <div className="p-4 mb-2">
                {/* Click logo to go to new chat / home */}
                <div onClick={onNewChat} className="cursor-pointer">
                    <GrokLogo className="w-8 h-8 text-white" />
                </div>
            </div>

            <div className="flex-1 flex flex-col justify-center px-2 space-y-1">
                {/* Navigation Items */}
                {menuItems.map((item) => (
                    <button
                        key={item.id}
                        className={cn(
                            "flex items-center gap-3 px-4 py-3 text-lg font-medium rounded-full transition-colors hover:bg-white/10 text-left w-full",
                            // Highlight active if needed
                        )}
                        onClick={() => {
                            if (item.label === "Files") {
                                // Navigate or show files
                            }
                        }}
                    >
                        <item.icon className="w-5 h-5 text-white/70" strokeWidth={2} />
                        <span>{item.label}</span>
                        {item.subMenu && <span className="ml-auto text-white/50">›</span>}
                    </button>
                ))}

                <button
                    onClick={handleSignOut}
                    className="flex items-center gap-3 px-4 py-3 text-lg font-medium rounded-full transition-colors hover:bg-white/10 text-left w-full mt-2"
                >
                    <LogOut className="w-5 h-5 text-white/70" strokeWidth={2} />
                    <span>Sign Out</span>
                </button>
            </div>

            {/* Bottom Profile Section */}
            <div className="p-4 mt-auto">
                <div className="flex items-center gap-3 p-3 rounded-full hover:bg-white/10 cursor-pointer">
                    <div className="w-10 h-10 rounded-full bg-white flex items-center justify-center">
                        <GrokLogo className="w-6 h-6 text-black" />
                    </div>
                    {/* User name would go here only if expanded */}
                </div>
            </div>
        </div>
    );
}
