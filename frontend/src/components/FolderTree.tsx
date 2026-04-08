"use client";

import { useState, useEffect } from "react";
import { Folder, FolderPlus, ChevronRight, ChevronDown, Trash2, Edit2, FileText, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { listFolders, createFolder, deleteFolder, getFolderTree } from "@/lib/api";

interface FolderTreeProps {
    selectedFolderId: string | null;
    onSelectFolder: (folderId: string | null) => void;
    onFolderChange: () => void;
    onFolderListChange?: (folders: any[]) => void;
    onLogout?: () => void;
}

export function FolderTree({ selectedFolderId, onSelectFolder, onFolderChange, onFolderListChange, onLogout }: FolderTreeProps) {
    const [folders, setFolders] = useState<any[]>([]);
    const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
    const [loading, setLoading] = useState(true);
    const [createDialogOpen, setCreateDialogOpen] = useState(false);
    const [newFolderName, setNewFolderName] = useState("");
    const [parentFolderId, setParentFolderId] = useState<string | null>(null);

    useEffect(() => {
        loadFolders();
    }, []);

    const loadFolders = async () => {
        try {
            const tree = await getFolderTree();
            setFolders(tree);
            if (onFolderListChange) {
                // Flatten tree for dropdown
                const flattenFolders = (folders: any[]): any[] => {
                    let result: any[] = [];
                    folders.forEach(folder => {
                        result.push(folder);
                        if (folder.children && folder.children.length > 0) {
                            result = result.concat(flattenFolders(folder.children));
                        }
                    });
                    return result;
                };
                onFolderListChange(flattenFolders(tree));
            }
        } catch (e) {
            console.error("Failed to load folders", e);
        } finally {
            setLoading(false);
        }
    };

    const toggleFolder = (folderId: string) => {
        setExpandedFolders((prev) => {
            const newSet = new Set(prev);
            if (newSet.has(folderId)) {
                newSet.delete(folderId);
            } else {
                newSet.add(folderId);
            }
            return newSet;
        });
    };

    const handleCreateFolder = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!newFolderName.trim()) return;

        try {
            await createFolder({
                name: newFolderName,
                parent_id: parentFolderId || undefined,
            });
            setNewFolderName("");
            setParentFolderId(null);
            setCreateDialogOpen(false);
            loadFolders();
            onFolderChange();
        } catch (e) {
            alert("Failed to create folder");
            console.error(e);
        }
    };

    const handleDeleteFolder = async (folderId: string, folderName: string) => {
        if (!confirm(`Are you sure you want to delete folder "${folderName}"?\n\nThis will permanently delete:\n- All documents inside this folder\n- All subfolders and their contents\n\nThis action cannot be undone.`)) {
            return;
        }

        try {
            await deleteFolder(folderId);
            loadFolders();
            if (selectedFolderId === folderId) {
                onSelectFolder(null);
            }
            onFolderChange();
        } catch (e: any) {
            alert(e.message || "Failed to delete folder");
            console.error(e);
        }
    };

    const renderFolder = (folder: any, level: number = 0) => {
        const isExpanded = expandedFolders.has(folder.id);
        const isSelected = selectedFolderId === folder.id;
        const hasChildren = folder.children && folder.children.length > 0;

        return (
            <div key={folder.id}>
                <div
                    className={`flex items-center gap-2 px-2 py-1.5 rounded hover:bg-white/5 cursor-pointer transition-colors ${
                        isSelected ? "bg-white/10" : ""
                    }`}
                    style={{ paddingLeft: `${level * 1.5 + 0.5}rem` }}
                >
                    {hasChildren ? (
                        <button
                            onClick={() => toggleFolder(folder.id)}
                            className="p-0.5 hover:bg-white/10 rounded text-white/50 hover:text-white/70"
                        >
                            {isExpanded ? (
                                <ChevronDown className="h-4 w-4" />
                            ) : (
                                <ChevronRight className="h-4 w-4" />
                            )}
                        </button>
                    ) : (
                        <div className="w-5" />
                    )}
                    <Folder className="h-4 w-4 text-violet-400" />
                    <span
                        className="flex-1 text-sm text-white/90"
                        onClick={() => onSelectFolder(folder.id)}
                    >
                        {folder.name}
                    </span>
                    <span className="text-xs text-white/50">
                        {folder.document_count || 0}
                    </span>
                    <div className="flex gap-1">
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                setParentFolderId(folder.id);
                                setCreateDialogOpen(true);
                            }}
                            className="p-1 hover:bg-white/10 rounded text-white/50 hover:text-white/70"
                            title="Create subfolder"
                        >
                            <FolderPlus className="h-3 w-3" />
                        </button>
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                handleDeleteFolder(folder.id, folder.name);
                            }}
                            className="p-1 hover:bg-red-500/20 rounded text-red-400 hover:text-red-300"
                            title="Delete folder"
                        >
                            <Trash2 className="h-3 w-3" />
                        </button>
                    </div>
                </div>
                {isExpanded && hasChildren && (
                    <div>
                        {folder.children.map((child: any) => renderFolder(child, level + 1))}
                    </div>
                )}
            </div>
        );
    };

    return (
        <div className="w-64 border-r border-white/10 p-4 bg-[#0A0A0B] flex flex-col min-h-screen">
            <div className="flex-1">
                <div className="flex items-center justify-between mb-4">
                    <h3 className="font-semibold text-sm text-white/90">Folders</h3>
                    <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
                        <DialogTrigger asChild>
                            <Button 
                                size="sm" 
                                variant="outline"
                                className="bg-white/5 border-white/10 text-white/90 hover:bg-white/10"
                            >
                                <FolderPlus className="h-4 w-4 mr-1" />
                                New
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="bg-[#0A0A0B] border-white/10 text-white">
                            <DialogHeader>
                                <DialogTitle className="text-white">Create Folder</DialogTitle>
                                <DialogDescription className="text-white/60">
                                    {parentFolderId ? "Create a subfolder" : "Create a new folder"}
                                </DialogDescription>
                            </DialogHeader>
                            <form onSubmit={handleCreateFolder} className="space-y-4">
                                <div>
                                    <Label htmlFor="folderName" className="text-white/70">Folder Name</Label>
                                    <Input
                                        id="folderName"
                                        value={newFolderName}
                                        onChange={(e) => setNewFolderName(e.target.value)}
                                        placeholder="Enter folder name"
                                        required
                                        className="bg-white/5 border-white/10 text-white"
                                    />
                                </div>
                                <div className="flex gap-2">
                                    <Button 
                                        type="submit" 
                                        className="flex-1 bg-violet-500 hover:bg-violet-600 text-white"
                                    >
                                        Create
                                    </Button>
                                    <Button
                                        type="button"
                                        variant="outline"
                                        onClick={() => {
                                            setCreateDialogOpen(false);
                                            setNewFolderName("");
                                            setParentFolderId(null);
                                        }}
                                        className="bg-white/5 border-white/10 text-white/90 hover:bg-white/10"
                                    >
                                        Cancel
                                    </Button>
                                </div>
                            </form>
                        </DialogContent>
                    </Dialog>
                </div>

                <div className="space-y-1">
                    <div
                        className={`flex items-center gap-2 px-2 py-1.5 rounded hover:bg-white/5 cursor-pointer transition-colors ${
                            selectedFolderId === null ? "bg-white/10" : ""
                        }`}
                        onClick={() => onSelectFolder(null)}
                    >
                        <FileText className="h-4 w-4 text-white/50" />
                        <span className="flex-1 text-sm text-white/90">All Documents</span>
                    </div>
                    {loading ? (
                        <p className="text-sm text-white/50 p-2">Loading...</p>
                    ) : folders.length === 0 ? (
                        <p className="text-sm text-white/50 p-2">No folders yet</p>
                    ) : (
                        folders.map((folder) => renderFolder(folder))
                    )}
                </div>
            </div>

            {/* Logout button at bottom left */}
            {onLogout && (
                <div className="mt-auto pt-4 border-t border-white/10">
                    <Button 
                        variant="outline" 
                        onClick={onLogout}
                        className="w-full bg-white/5 border-white/10 text-white/90 hover:bg-white/10 hover:text-white/90"
                    >
                        <LogOut className="mr-2 h-4 w-4" />
                        Logout
                    </Button>
                </div>
            )}
        </div>
    );
}

