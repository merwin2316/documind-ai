"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { listConversations, deleteConversation, updateConversation, fetchWithAuth } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
    MessageSquare,
    FileText,
    Settings,
    LogOut,
    Plus,
    User,
    Shield,
    Trash2,
    ChevronLeft,
    ChevronRight,
    X,
    Pencil,
    Check,
    MoreVertical,
    Pin,
} from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import Image from "next/image";

interface Conversation {
    id: string;
    title: string;
    created_at: string;
    isPinned?: boolean;
}

interface ChatSidebarProps {
    currentConversationId: string | null;
    onSelectConversation: (id: string) => void;
    onNewChat: () => void;
    refreshTrigger?: number; // Trigger to refresh conversations
}

export function ChatSidebar({
    currentConversationId,
    onSelectConversation,
    onNewChat,
    refreshTrigger,
}: ChatSidebarProps) {
    const router = useRouter();
    const [conversations, setConversations] = useState<Conversation[]>([]);
    const [user, setUser] = useState<any>(null);
    const [isAdmin, setIsAdmin] = useState(false);
    const [isMinimized, setIsMinimized] = useState(false);
    const [hoveredConversationId, setHoveredConversationId] = useState<string | null>(null);

    useEffect(() => {
        loadUserAndConversations();
    }, []);

    // Refresh conversations when refreshTrigger changes
    useEffect(() => {
        if (refreshTrigger !== undefined) {
            loadUserAndConversations();
        }
    }, [refreshTrigger]);

    const loadUserAndConversations = async () => {
        try {
            const { data } = await supabase.auth.getUser();
            setUser(data.user);

            const convs = await listConversations(0, 50);
            // Transform backend format to frontend format
            setConversations(convs.map((conv: any) => ({
                id: conv.conversation_id,
                title: conv.title || "Untitled",
                created_at: conv.created_at
            })));

            // Check if admin - backend doesn't have role endpoint, so assume not admin for now
            try {
                const userProfile = await fetchWithAuth("/auth/me");
                setIsAdmin(userProfile.role === "admin");
            } catch {
                setIsAdmin(false);
            }
        } catch (e) {
            console.error("Failed to load sidebar data", e);
        }
    };

    const handleLogout = async () => {
        await supabase.auth.signOut();
        localStorage.removeItem("supabase_token");
        router.push("/login");
    };

    const handleDeleteConversation = async (conversationId: string, e: React.MouseEvent) => {
        e.stopPropagation(); // Prevent selecting the conversation when clicking delete

        if (!confirm("Are you sure you want to delete this conversation? This action cannot be undone.")) {
            return;
        }

        try {
            await deleteConversation(conversationId);

            // Remove from local state
            setConversations((prev) => prev.filter((conv) => conv.id !== conversationId));

            // If this was the current conversation, clear it
            if (currentConversationId === conversationId) {
                onNewChat();
            }
        } catch (e: any) {
            console.error("Failed to delete conversation", e);
            alert(e.message || "Failed to delete conversation");
        }
    };

    const handleRenameConversation = async (conversationId: string, newTitle: string) => {
        try {
            // Update backend
            await updateConversation(conversationId, { title: newTitle });

            // Update local state
            setConversations((prev) =>
                prev.map((conv) =>
                    conv.id === conversationId ? { ...conv, title: newTitle } : conv
                )
            );
        } catch (e: any) {
            console.error("Failed to rename conversation", e);
            alert(e.message || "Failed to rename conversation");
        }
    };

    const groupConversations = () => {
        const now = new Date();
        const pinned: Conversation[] = [];
        const today: Conversation[] = [];
        const yesterday: Conversation[] = [];
        const lastWeek: Conversation[] = [];
        const byMonth: { [key: string]: Conversation[] } = {};

        conversations.forEach((conv) => {
            if (conv.isPinned) {
                pinned.push(conv);
                return;
            }

            const date = new Date(conv.created_at);
            const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));

            if (diffDays === 0) {
                today.push(conv);
            } else if (diffDays === 1) {
                yesterday.push(conv);
            } else if (diffDays <= 7) {
                lastWeek.push(conv);
            } else {
                // Group by month and year
                const monthYear = date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
                if (!byMonth[monthYear]) {
                    byMonth[monthYear] = [];
                }
                byMonth[monthYear].push(conv);
            }
        });

        return { pinned, today, yesterday, lastWeek, byMonth };
    };

    const grouped = groupConversations();

    if (isMinimized) {
        return (
            <div className="h-screen bg-[#0A0A0B] border-r border-white/[0.05] flex flex-col items-center py-4">
                <button
                    onClick={() => setIsMinimized(false)}
                    className="p-2 text-white/70 hover:text-white hover:bg-white/[0.05] rounded-lg transition-colors"
                    title="Expand sidebar"
                >
                    <ChevronRight className="w-5 h-5" />
                </button>
            </div>
        );
    }

    return (
        <div className="w-64 h-screen bg-[#0A0A0B] border-r border-white/[0.05] flex flex-col relative">
            {/* Minimize Button */}
            <button
                onClick={() => setIsMinimized(true)}
                className="absolute top-4 right-2 p-1.5 text-white/40 hover:text-white/70 hover:bg-white/[0.05] rounded transition-colors z-10"
                title="Minimize sidebar"
            >
                <ChevronLeft className="w-4 h-4" />
            </button>
            {/* User Profile */}
            <div className="p-4 border-b border-white/[0.05]">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full overflow-hidden flex items-center justify-center bg-white/5">
                        <Image
                            src="/logo-single.jpg"
                            alt="Logo"
                            width={40}
                            height={40}
                            className="w-10 h-10 object-cover"
                        />
                    </div>
                    <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-white truncate">
                            {user?.email?.split('@')[0] || 'User'}
                        </p>
                        <p className="text-xs text-white/40 truncate">
                            {user?.email || ''}
                        </p>
                    </div>
                </div>
            </div>

            {/* New Chat Button */}
            <div className="p-3">
                <Button
                    onClick={onNewChat}
                    className="w-full bg-white/[0.05] hover:bg-white/[0.1] text-white border border-white/[0.1]"
                >
                    <Plus className="w-4 h-4 mr-2" />
                    New Chat
                </Button>
            </div>

            {/* Conversations */}
            <div className="flex-1 overflow-y-auto px-3 space-y-4">
                {grouped.pinned.length > 0 && (
                    <div>
                        <p className="text-xs text-white/40 mb-2 px-2">Pinned</p>
                        {grouped.pinned.map((conv) => (
                            <ConversationItem
                                key={conv.id}
                                conversation={conv}
                                isActive={currentConversationId === conv.id}
                                onClick={() => onSelectConversation(conv.id)}
                                onDelete={(e) => handleDeleteConversation(conv.id, e)}
                                onRename={(newTitle) => handleRenameConversation(conv.id, newTitle)}
                                onTogglePin={async () => {
                                    try {
                                        const newPinnedState = !conv.isPinned;
                                        await updateConversation(conv.id, { is_pinned: newPinnedState });
                                        setConversations((prev) =>
                                            prev.map((c) =>
                                                c.id === conv.id ? { ...c, isPinned: newPinnedState } : c
                                            )
                                        );
                                    } catch (e: any) {
                                        console.error("Failed to toggle pin", e);
                                        alert(e.message || "Failed to update pin status");
                                    }
                                }}
                                isHovered={hoveredConversationId === conv.id}
                                onHover={() => setHoveredConversationId(conv.id)}
                                onLeave={() => setHoveredConversationId(null)}
                            />
                        ))}
                    </div>
                )}

                {grouped.today.length > 0 && (
                    <div>
                        <p className="text-xs text-white/40 mb-2 px-2">Today</p>
                        {grouped.today.map((conv) => (
                            <ConversationItem
                                key={conv.id}
                                conversation={conv}
                                isActive={currentConversationId === conv.id}
                                onClick={() => onSelectConversation(conv.id)}
                                onDelete={(e) => handleDeleteConversation(conv.id, e)}
                                onRename={(newTitle) => handleRenameConversation(conv.id, newTitle)}
                                onTogglePin={() => {
                                    setConversations((prev) =>
                                        prev.map((c) =>
                                            c.id === conv.id ? { ...c, isPinned: !c.isPinned } : c
                                        )
                                    );
                                }}
                                isHovered={hoveredConversationId === conv.id}
                                onHover={() => setHoveredConversationId(conv.id)}
                                onLeave={() => setHoveredConversationId(null)}
                            />
                        ))}
                    </div>
                )}

                {grouped.yesterday.length > 0 && (
                    <div>
                        <p className="text-xs text-white/40 mb-2 px-2">Yesterday</p>
                        {grouped.yesterday.map((conv) => (
                            <ConversationItem
                                key={conv.id}
                                conversation={conv}
                                isActive={currentConversationId === conv.id}
                                onClick={() => onSelectConversation(conv.id)}
                                onDelete={(e) => handleDeleteConversation(conv.id, e)}
                                onRename={(newTitle) => handleRenameConversation(conv.id, newTitle)}
                                onTogglePin={() => {
                                    setConversations((prev) =>
                                        prev.map((c) =>
                                            c.id === conv.id ? { ...c, isPinned: !c.isPinned } : c
                                        )
                                    );
                                }}
                                isHovered={hoveredConversationId === conv.id}
                                onHover={() => setHoveredConversationId(conv.id)}
                                onLeave={() => setHoveredConversationId(null)}
                            />
                        ))}
                    </div>
                )}

                {grouped.lastWeek.length > 0 && (
                    <div>
                        <p className="text-xs text-white/40 mb-2 px-2">Last 7 days</p>
                        {grouped.lastWeek.map((conv) => (
                            <ConversationItem
                                key={conv.id}
                                conversation={conv}
                                isActive={currentConversationId === conv.id}
                                onClick={() => onSelectConversation(conv.id)}
                                onDelete={(e) => handleDeleteConversation(conv.id, e)}
                                onRename={(newTitle) => handleRenameConversation(conv.id, newTitle)}
                                onTogglePin={() => {
                                    setConversations((prev) =>
                                        prev.map((c) =>
                                            c.id === conv.id ? { ...c, isPinned: !c.isPinned } : c
                                        )
                                    );
                                }}
                                isHovered={hoveredConversationId === conv.id}
                                onHover={() => setHoveredConversationId(conv.id)}
                                onLeave={() => setHoveredConversationId(null)}
                            />
                        ))}
                    </div>
                )}

                {Object.entries(grouped.byMonth).map(([monthYear, convs]) => (
                    <div key={monthYear}>
                        <p className="text-xs text-white/40 mb-2 px-2">{monthYear}</p>
                        {convs.map((conv) => (
                            <ConversationItem
                                key={conv.id}
                                conversation={conv}
                                isActive={currentConversationId === conv.id}
                                onClick={() => onSelectConversation(conv.id)}
                                onDelete={(e) => handleDeleteConversation(conv.id, e)}
                                onRename={(newTitle) => handleRenameConversation(conv.id, newTitle)}
                                onTogglePin={() => {
                                    setConversations((prev) =>
                                        prev.map((c) =>
                                            c.id === conv.id ? { ...c, isPinned: !c.isPinned } : c
                                        )
                                    );
                                }}
                                isHovered={hoveredConversationId === conv.id}
                                onHover={() => setHoveredConversationId(conv.id)}
                                onLeave={() => setHoveredConversationId(null)}
                            />
                        ))}
                    </div>
                ))}
            </div>

            {/* Bottom Actions */}
            <div className="p-3 border-t border-white/[0.05] space-y-2">
                <Button
                    variant="ghost"
                    className="w-full justify-start text-white/70 hover:text-white hover:bg-white/[0.05]"
                    onClick={() => router.push("/vault")}
                >
                    <FileText className="w-4 h-4 mr-2" />
                    Document Vault
                </Button>

                {isAdmin && (
                    <Button
                        variant="ghost"
                        className="w-full justify-start text-white/70 hover:text-white hover:bg-white/[0.05]"
                        onClick={() => router.push("/admin")}
                    >
                        <Shield className="w-4 h-4 mr-2" />
                        Admin Dashboard
                    </Button>
                )}

                <Button
                    variant="ghost"
                    className="w-full justify-start text-white/70 hover:text-white hover:bg-white/[0.05]"
                    onClick={handleLogout}
                >
                    <LogOut className="w-4 h-4 mr-2" />
                    Logout
                </Button>
            </div>
        </div>
    );
}

function ConversationItem({
    conversation,
    isActive,
    onClick,
    onDelete,
    onRename,
    onTogglePin,
    isHovered,
    onHover,
    onLeave,
}: {
    conversation: Conversation;
    isActive: boolean;
    onClick: () => void;
    onDelete: (e: React.MouseEvent) => void;
    onRename: (newTitle: string) => void;
    onTogglePin: () => void | Promise<void>;
    isHovered: boolean;
    onHover: () => void;
    onLeave: () => void;
}) {
    const [isEditing, setIsEditing] = useState(false);
    const [editTitle, setEditTitle] = useState(conversation.title);
    const [showMenu, setShowMenu] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);
    const menuRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (isEditing && inputRef.current) {
            inputRef.current.focus();
            inputRef.current.select();
        }
    }, [isEditing]);

    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                setShowMenu(false);
            }
        };

        if (showMenu) {
            document.addEventListener('mousedown', handleClickOutside);
        }

        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, [showMenu]);

    const handleEdit = (e: React.MouseEvent) => {
        e.stopPropagation();
        setShowMenu(false);
        setIsEditing(true);
        setEditTitle(conversation.title);
    };

    const handleMenuToggle = (e: React.MouseEvent) => {
        e.stopPropagation();
        setShowMenu(!showMenu);
    };

    const handlePin = (e: React.MouseEvent) => {
        e.stopPropagation();
        setShowMenu(false);
        onTogglePin();
    };

    const handleDeleteClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        setShowMenu(false);
        onDelete(e);
    };

    const handleSave = () => {
        if (editTitle.trim() && editTitle.trim() !== conversation.title) {
            onRename(editTitle.trim());
        } else {
            setEditTitle(conversation.title);
        }
        setIsEditing(false);
    };

    const handleCancel = (e?: React.MouseEvent) => {
        if (e) e.stopPropagation();
        setEditTitle(conversation.title);
        setIsEditing(false);
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === "Enter") {
            handleSave();
        } else if (e.key === "Escape") {
            handleCancel();
        }
    };

    return (
        <motion.div
            onMouseEnter={onHover}
            onMouseLeave={onLeave}
            className="relative group overflow-hidden"
        >
            {isEditing ? (
                <div className="w-full px-3 py-2 rounded-lg text-sm flex items-center gap-2 bg-white/[0.1]">
                    <MessageSquare className="w-4 h-4 flex-shrink-0" />
                    <input
                        ref={inputRef}
                        type="text"
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        onKeyDown={handleKeyDown}
                        onBlur={handleSave}
                        className="flex-1 bg-transparent text-white border-none outline-none"
                        onClick={(e) => e.stopPropagation()}
                    />
                    <button
                        onClick={handleSave}
                        className="p-1 text-green-400 hover:text-green-300 hover:bg-green-500/20 rounded transition-colors"
                        title="Save"
                    >
                        <Check className="w-3.5 h-3.5" />
                    </button>
                    <button
                        onClick={handleCancel}
                        className="p-1 text-white/40 hover:text-white/70 hover:bg-white/10 rounded transition-colors"
                        title="Cancel"
                    >
                        <X className="w-3.5 h-3.5" />
                    </button>
                </div>
            ) : (
                <>
                    <motion.button
                        onClick={onClick}
                        className={cn(
                            "w-full text-left px-3 py-2 pr-10 rounded-lg text-sm transition-colors flex items-center gap-2",
                            isActive
                                ? "bg-white/[0.1] text-white"
                                : "text-white/70 hover:bg-white/[0.05] hover:text-white"
                        )}
                        whileHover={{ x: 2 }}
                    >
                        <MessageSquare className="w-4 h-4 flex-shrink-0" />
                        <span className="truncate flex-1">{conversation.title}</span>
                    </motion.button>

                    {/* Three-dot menu - Show on hover */}
                    {isHovered && (
                        <div className="absolute right-2 top-1/2 -translate-y-1/2 z-10" ref={menuRef}>
                            <button
                                onClick={handleMenuToggle}
                                className="p-1.5 text-white/40 hover:text-white/70 hover:bg-white/[0.1] rounded transition-colors"
                                title="Options"
                            >
                                <MoreVertical className="w-4 h-4" />
                            </button>

                            {/* Dropdown Menu */}
                            {showMenu && (
                                <motion.div
                                    initial={{ opacity: 0, scale: 0.95, y: -10 }}
                                    animate={{ opacity: 1, scale: 1, y: 0 }}
                                    exit={{ opacity: 0, scale: 0.95 }}
                                    className="absolute right-0 top-8 bg-[#1A1A1B] border border-white/[0.1] rounded-lg shadow-xl overflow-hidden min-w-[140px] z-50"
                                    onClick={(e) => e.stopPropagation()}
                                >
                                    <button
                                        onClick={handleEdit}
                                        className="w-full px-4 py-2.5 text-left text-sm text-white/90 hover:bg-white/[0.05] flex items-center gap-2 transition-colors"
                                    >
                                        <Pencil className="w-4 h-4" />
                                        Rename
                                    </button>
                                    <button
                                        onClick={handlePin}
                                        className="w-full px-4 py-2.5 text-left text-sm text-white/90 hover:bg-white/[0.05] flex items-center gap-2 transition-colors"
                                    >
                                        <Pin className="w-4 h-4" />
                                        {conversation.isPinned ? 'Unpin' : 'Pin'}
                                    </button>
                                    <button
                                        onClick={handleDeleteClick}
                                        className="w-full px-4 py-2.5 text-left text-sm text-red-400 hover:bg-red-500/10 flex items-center gap-2 transition-colors"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                        Delete
                                    </button>
                                </motion.div>
                            )}
                        </div>
                    )}
                </>
            )}
        </motion.div>
    );
}
