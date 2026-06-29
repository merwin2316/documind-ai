"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { fetchWithAuth } from "@/lib/api";
import { motion, AnimatePresence } from "framer-motion";
import {
    Scale, DollarSign, Box, Megaphone, Users, Settings as SettingsIcon,
    BookOpen, FileText, Search, Filter, X, ChevronRight, Sparkles,
    Calendar, Tag as TagIcon, FileCheck
} from "lucide-react";
import { cn } from "@/lib/utils";
import { AppSidebar } from "@/components/AppSidebar";

interface Category {
    name: string;
    count: number;
    icon: string;
    color: string;
}

interface Document {
    document_id: string;
    name: string;
    category: string;
    tags: string[];
    ai_summary: string;
    uploaded_at: string;
    total_pages: number;
    key_entities?: {
        people: string[];
        companies: string[];
        products: string[];
    };
    related_document_ids?: string[];
}

const CATEGORY_ICONS: Record<string, any> = {
    "Legal": Scale,
    "Financial": DollarSign,
    "Product": Box,
    "Marketing": Megaphone,
    "HR": Users,
    "Operations": SettingsIcon,
    "Research": BookOpen,
    "Other": FileText
};

export default function KnowledgeBasePage() {
    const router = useRouter();
    const [categories, setCategories] = useState<Category[]>([]);
    const [documents, setDocuments] = useState<Document[]>([]);
    const [allTags, setAllTags] = useState<{ name: string; count: number }[]>([]);
    const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
    const [selectedTags, setSelectedTags] = useState<string[]>([]);
    const [searchQuery, setSearchQuery] = useState("");
    const [loading, setLoading] = useState(true);
    const [showFilters, setShowFilters] = useState(false);

    useEffect(() => {
        loadCategories();
        loadTags();
        loadDocuments();
    }, []);

    useEffect(() => {
        loadDocuments();
    }, [selectedCategory, selectedTags, searchQuery]);


    const loadCategories = async () => {
        try {
            const response = await fetchWithAuth("/knowledge-base/categories");
            setCategories(response.categories || []);
        } catch (error) {
            console.error("Failed to load categories:", error);
        }
    };

    const loadTags = async () => {
        try {
            const response = await fetchWithAuth("/knowledge-base/tags");
            setAllTags(response.tags || []);
        } catch (error) {
            console.error("Failed to load tags:", error);
        }
    };

    const loadDocuments = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (selectedCategory) params.append("category", selectedCategory);
            if (selectedTags.length > 0) params.append("tags", selectedTags.join(","));
            if (searchQuery) params.append("search", searchQuery);

            const response = await fetchWithAuth(`/knowledge-base/documents?${params.toString()}`);
            setDocuments(response.documents || []);
        } catch (error) {
            console.error("Failed to load documents:", error);
        } finally {
            setLoading(false);
        }
    };

    const toggleTag = (tag: string) => {
        setSelectedTags(prev =>
            prev.includes(tag)
                ? prev.filter(t => t !== tag)
                : [...prev, tag]
        );
    };

    const clearFilters = () => {
        setSelectedCategory(null);
        setSelectedTags([]);
        setSearchQuery("");
    };

    const hasActiveFilters = selectedCategory || selectedTags.length > 0 || searchQuery;

    return (
        <div className="flex h-screen bg-[#0A0A0B] text-white">
            {/* App Sidebar */}
            <AppSidebar
                currentConversationId={null}
                onSelectConversation={(id) => router.push(`/chat?conversation=${id}`)}
                onNewChat={() => router.push('/chat')}
                refreshTrigger={0}
            />

            {/* Knowledge Base Filters Sidebar */}
            <div className="w-80 border-r border-white/5 flex flex-col overflow-hidden">
                {/* Header */}
                <div className="p-6 border-b border-white/5">
                    <div className="flex items-center gap-3 mb-6">
                        {/* Simple Bold Icon */}
                        <div className="w-8 h-8 rounded-lg bg-white flex items-center justify-center">
                            <span className="text-black text-xl font-bold">Ø</span>
                        </div>
                        <div>
                            <h1 className="text-xl font-semibold text-white">
                                DocuMind AI
                            </h1>
                            <p className="text-xs text-white/40">Knowledge Base</p>
                        </div>
                    </div>

                    {/* Search */}
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                        <input
                            type="text"
                            placeholder="Search documents..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="w-full pl-10 pr-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white placeholder:text-white/30 focus:outline-none focus:border-violet-500/50 transition-colors"
                        />
                    </div>
                </div>

                {/* Categories */}
                <div className="flex-1 overflow-y-auto p-4">
                    <div className="mb-6">
                        <div className="flex items-center justify-between mb-3 px-2">
                            <h2 className="text-xs font-semibold text-white/50 uppercase tracking-wider">Categories</h2>
                            {selectedCategory && (
                                <button
                                    onClick={() => setSelectedCategory(null)}
                                    className="text-xs text-violet-400 hover:text-violet-300"
                                >
                                    Clear
                                </button>
                            )}
                        </div>
                        <div className="space-y-1">
                            {categories.map((category) => {
                                const Icon = CATEGORY_ICONS[category.name];
                                const isSelected = selectedCategory === category.name;
                                return (
                                    <motion.button
                                        key={category.name}
                                        onClick={() => setSelectedCategory(isSelected ? null : category.name)}
                                        className={cn(
                                            "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all",
                                            isSelected
                                                ? "bg-white/10 text-white"
                                                : "text-white/70 hover:bg-white/5 hover:text-white"
                                        )}
                                        whileHover={{ x: 2 }}
                                    >
                                        <div
                                            className="p-1.5 rounded-lg"
                                            style={{ backgroundColor: `${category.color}20` }}
                                        >
                                            {Icon && <Icon className="w-4 h-4" style={{ color: category.color }} />}
                                        </div>
                                        <span className="flex-1 text-left text-sm font-medium">{category.name}</span>
                                        <span className="text-xs text-white/40">{category.count}</span>
                                    </motion.button>
                                );
                            })}
                        </div>
                    </div>

                    {/* Popular Tags */}
                    <div>
                        <div className="flex items-center justify-between mb-3 px-2">
                            <h2 className="text-xs font-semibold text-white/50 uppercase tracking-wider">Popular Tags</h2>
                            {selectedTags.length > 0 && (
                                <button
                                    onClick={() => setSelectedTags([])}
                                    className="text-xs text-violet-400 hover:text-violet-300"
                                >
                                    Clear
                                </button>
                            )}
                        </div>
                        <div className="flex flex-wrap gap-2">
                            {allTags.slice(0, 15).map((tag) => {
                                const isSelected = selectedTags.includes(tag.name);
                                return (
                                    <button
                                        key={tag.name}
                                        onClick={() => toggleTag(tag.name)}
                                        className={cn(
                                            "px-3 py-1.5 rounded-full text-xs font-medium transition-all",
                                            isSelected
                                                ? "bg-violet-500/20 text-violet-300 border border-violet-500/30"
                                                : "bg-white/5 text-white/60 hover:bg-white/10 hover:text-white border border-white/10"
                                        )}
                                    >
                                        {tag.name}
                                        <span className="ml-1.5 text-white/40">{tag.count}</span>
                                    </button>
                                );
                            })}
                        </div>
                    </div>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 flex flex-col overflow-hidden">
                {/* Header */}
                <div className="p-6 border-b border-white/5">
                    <div className="flex items-center justify-between">
                        <div>
                            <h2 className="text-2xl font-bold">
                                {selectedCategory || "All Documents"}
                            </h2>
                            <p className="text-sm text-white/40 mt-1">
                                {documents.length} document{documents.length !== 1 ? "s" : ""} found
                            </p>
                        </div>
                        {hasActiveFilters && (
                            <button
                                onClick={clearFilters}
                                className="flex items-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg text-sm transition-colors"
                            >
                                <X className="w-4 h-4" />
                                Clear Filters
                            </button>
                        )}
                    </div>

                    {/* Active Filters */}
                    {(selectedTags.length > 0 || searchQuery) && (
                        <div className="flex flex-wrap gap-2 mt-4">
                            {searchQuery && (
                                <div className="flex items-center gap-2 px-3 py-1.5 bg-violet-500/10 border border-violet-500/20 rounded-lg text-xs">
                                    <Search className="w-3 h-3 text-violet-400" />
                                    <span className="text-violet-300">{searchQuery}</span>
                                </div>
                            )}
                            {selectedTags.map(tag => (
                                <div key={tag} className="flex items-center gap-2 px-3 py-1.5 bg-violet-500/10 border border-violet-500/20 rounded-lg text-xs">
                                    <TagIcon className="w-3 h-3 text-violet-400" />
                                    <span className="text-violet-300">{tag}</span>
                                    <button onClick={() => toggleTag(tag)} className="text-violet-400 hover:text-violet-300">
                                        <X className="w-3 h-3" />
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Document Grid */}
                <div className="flex-1 overflow-y-auto p-6">
                    {loading ? (
                        <div className="flex items-center justify-center h-64">
                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-violet-500"></div>
                        </div>
                    ) : documents.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-64 text-center">
                            <FileText className="w-12 h-12 text-white/20 mb-4" />
                            <p className="text-white/40">No documents found</p>
                            <p className="text-sm text-white/30 mt-1">Try adjusting your filters</p>
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {documents.map((doc) => (
                                <DocumentCard key={doc.document_id} document={doc} />
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

function DocumentCard({ document }: { document: Document }) {
    const router = useRouter();
    const Icon = CATEGORY_ICONS[document.category] || FileText;
    const categoryColor = getCategoryColor(document.category);

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            whileHover={{ y: -4 }}
            onClick={() => router.push(`/vault?doc=${document.document_id}`)}
            className="group cursor-pointer bg-white/[0.02] hover:bg-white/[0.05] border border-white/10 hover:border-white/20 rounded-2xl p-5 transition-all duration-300"
        >
            {/* Header */}
            <div className="flex items-start justify-between mb-4">
                <div
                    className="p-2 rounded-lg"
                    style={{ backgroundColor: `${categoryColor}20` }}
                >
                    <Icon className="w-5 h-5" style={{ color: categoryColor }} />
                </div>
                <span
                    className="px-2.5 py-1 rounded-full text-xs font-medium"
                    style={{
                        backgroundColor: `${categoryColor}15`,
                        color: categoryColor
                    }}
                >
                    {document.category}
                </span>
            </div>

            {/* Title */}
            <h3 className="font-semibold text-white mb-2 line-clamp-2 group-hover:text-violet-300 transition-colors">
                {document.name}
            </h3>

            {/* Summary */}
            <p className="text-sm text-white/50 mb-4 line-clamp-3">
                {document.ai_summary || "No summary available"}
            </p>

            {/* Tags */}
            {document.tags && document.tags.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mb-4">
                    {document.tags.slice(0, 3).map((tag) => (
                        <span
                            key={tag}
                            className="px-2 py-0.5 bg-white/5 border border-white/10 rounded text-xs text-white/60"
                        >
                            {tag}
                        </span>
                    ))}
                    {document.tags.length > 3 && (
                        <span className="px-2 py-0.5 text-xs text-white/40">
                            +{document.tags.length - 3}
                        </span>
                    )}
                </div>
            )}

            {/* Footer */}
            <div className="flex items-center justify-between pt-4 border-t border-white/5">
                <div className="flex items-center gap-4 text-xs text-white/40">
                    <span className="flex items-center gap-1">
                        <Calendar className="w-3 h-3" />
                        {new Date(document.uploaded_at).toLocaleDateString()}
                    </span>
                    {document.total_pages && (
                        <span className="flex items-center gap-1">
                            <FileCheck className="w-3 h-3" />
                            {document.total_pages} pages
                        </span>
                    )}
                </div>
                <ChevronRight className="w-4 h-4 text-white/30 group-hover:text-violet-400 group-hover:translate-x-1 transition-all" />
            </div>
        </motion.div>
    );
}

function getCategoryColor(category: string): string {
    const colors: Record<string, string> = {
        "Legal": "#3B82F6",
        "Financial": "#10B981",
        "Product": "#8B5CF6",
        "Marketing": "#F59E0B",
        "HR": "#EF4444",
        "Operations": "#6366F1",
        "Research": "#EC4899",
        "Other": "#6B7280"
    };
    return colors[category] || "#6B7280";
}
