"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { listDocuments, uploadFileWithAuth, deleteDocument } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "sonner";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
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
import { FileText, Upload, MessageSquare, Loader2, CheckCircle2, Trash2, XCircle, Wifi, WifiOff } from "lucide-react";
// FolderTree removed - folders not supported in backend yet
import { motion } from "framer-motion";
import { useDocumentStatus } from "@/hooks/useDocumentStatus";
import { AppSidebar } from "@/components/AppSidebar";

export default function VaultPage() {
    const router = useRouter();
    const [documents, setDocuments] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
    const [deletingId, setDeletingId] = useState<string | null>(null);
    // Folder functionality removed - not supported in backend yet
    // Reprocessing removed - not supported in backend
    const [selectedFileName, setSelectedFileName] = useState<string>("");
    const fileInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        const checkSession = async () => {
            const { data } = await supabase.auth.getSession();
            if (!data.session) {
                router.push("/login");
            } else {
                // Refresh token in local storage securely if needed, but for now we rely on what was set in Login/Callback
                // Or we can just set it here again to be sure
                localStorage.setItem("supabase_token", data.session.access_token);
                loadDocuments();
            }
        };
        checkSession();
    }, [router]);

    const loadDocuments = async () => {
        try {
            setLoading(true);
            const docs = await listDocuments();
            // Backend returns array of documents with structure: { document_id, name, status, total_pages, total_chunks, ... }
            // Transform to match frontend expected format
            setDocuments(docs.map((doc: any) => ({
                id: doc.document_id,
                title: doc.name,
                mime_type: doc.file_type || "application/pdf",
                status: doc.status || "processing",  // Backend uses: "processing", "ready", "error"
                error_message: doc.error_message || null,  // Error details if status is "error"
                created_at: doc.uploaded_at,
                storage_path: doc.storage_path,
                chunk_count: doc.total_chunks || 0,
                page_count: doc.total_pages || 0,
            })));
        } catch (e) {
            console.error("Failed to load docs", e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadDocuments();
    }, []);

    // WebSocket connection for real-time updates with polling fallback
    const { connectionStatus, usePolling, isConnected } = useDocumentStatus({
        enabled: true,
        pollingInterval: 3000,
        onStatusUpdate: (update) => {
            // Update the specific document in the list
            setDocuments((prevDocs) =>
                prevDocs.map((doc) =>
                    doc.id === update.document_id
                        ? {
                            ...doc,
                            status: update.status,
                            error_message: update.error_message,
                            chunk_count: update.total_chunks || doc.chunk_count,
                            page_count: update.total_pages || doc.page_count,
                        }
                        : doc
                )
            );
        },
    });

    // Polling fallback - only poll if WebSocket is not connected and there are processing docs
    useEffect(() => {
        if (!usePolling) {
            return; // WebSocket is handling updates
        }

        const hasProcessingDocs = documents.some((doc) => doc.status === "processing");

        if (!hasProcessingDocs) {
            return; // No need to poll if no documents are processing
        }

        const interval = setInterval(() => {
            loadDocuments();
        }, 3000); // Poll every 3 seconds for faster updates

        return () => clearInterval(interval);
    }, [documents, usePolling]);

    // Close menus when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            const target = event.target as HTMLElement;
            if (!target.closest('.relative.inline-block')) {
                documents.forEach((doc) => {
                    const menu = document.getElementById(`menu-${doc.id}`);
                    if (menu) menu.classList.add("hidden");
                });
            }
        };

        document.addEventListener('click', handleClickOutside);
        return () => document.removeEventListener('click', handleClickOutside);
    }, [documents]);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            // Validate file type
            const allowedExtensions = ['.pdf', '.docx'];
            const fileName = file.name.toLowerCase();
            const isValid = allowedExtensions.some(ext => fileName.endsWith(ext));

            if (!isValid) {
                toast.error('Invalid file type', {
                    description: 'Please upload only PDF or DOCX files.',
                });
                e.target.value = ''; // Clear the input
                setSelectedFileName("");
                return;
            }

            setSelectedFileName(file.name);
        } else {
            setSelectedFileName("");
        }
    };

    const handleUpload = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        const formData = new FormData(e.currentTarget);
        const file = formData.get("file") as File;
        if (!file) return;

        // Validate file type on submit
        const allowedExtensions = ['.pdf', '.docx'];
        const fileName = file.name.toLowerCase();
        const isValid = allowedExtensions.some(ext => fileName.endsWith(ext));

        if (!isValid) {
            toast.error('Invalid file type', {
                description: 'Please upload only PDF or DOCX files.',
            });
            return;
        }

        setUploading(true);
        try {
            // Upload document using API helper
            await uploadFileWithAuth("/documents/upload", file);

            toast.success('Document uploaded successfully', {
                description: `${file.name} is being processed.`,
            });

            setUploadDialogOpen(false);
            setSelectedFileName("");
            if (fileInputRef.current) {
                fileInputRef.current.value = "";
            }
            loadDocuments();
        } catch (e: any) {
            toast.error('Upload failed', {
                description: e.message || 'An error occurred while uploading the file.',
            });
            console.error(e);
        } finally {
            setUploading(false);
        }
    };

    const handleLogout = async () => {
        await supabase.auth.signOut();
        localStorage.removeItem("supabase_token");
        router.push("/login");
    };

    const handleDelete = async (documentId: string, documentTitle: string) => {
        // Use toast.promise for confirmation and progress
        toast.promise(
            new Promise<void>((resolve, reject) => {
                // Show confirmation dialog
                const confirmed = window.confirm(`Are you sure you want to delete "${documentTitle}"? This action cannot be undone.`);
                if (!confirmed) {
                    reject(new Error('Cancelled'));
                    return;
                }

                setDeletingId(documentId);
                deleteDocument(documentId)
                    .then(() => {
                        loadDocuments();
                        resolve();
                    })
                    .catch((e) => {
                        console.error(e);
                        reject(e);
                    })
                    .finally(() => {
                        setDeletingId(null);
                    });
            }),
            {
                loading: 'Deleting document...',
                success: `"${documentTitle}" deleted successfully`,
                error: (err: any) => err.message === 'Cancelled' ? null : 'Failed to delete document',
            }
        );
    };

    const handleReprocess = async (documentId: string) => {
        // Backend doesn't have reprocess endpoint yet
        toast.info('Feature not available', {
            description: 'Reprocess feature is coming soon.',
        });
    };


    return (
        <div className="flex h-screen bg-[#0A0A0B] text-white overflow-hidden">
            {/* Sidebar */}
            <AppSidebar
                currentConversationId={null}
                onSelectConversation={(id) => router.push(`/chat?conversation=${id}`)}
                onNewChat={() => router.push('/chat')}
                refreshTrigger={0}
            />

            {/* Main Content */}
            <div className="flex-1 overflow-y-auto p-8 relative">
                {/* Background Gradients */}
                <div className="absolute inset-0 overflow-hidden pointer-events-none">
                    <div className="absolute top-0 left-1/4 w-96 h-96 bg-violet-500/10 rounded-full mix-blend-normal filter blur-[128px] animate-pulse" />
                    <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-indigo-500/10 rounded-full mix-blend-normal filter blur-[128px] animate-pulse delay-700" />
                </div>

                <div className="max-w-6xl mx-auto relative z-10">
                    <div className="flex justify-between items-center mb-8">
                        <div>
                            <div>
                                <h1 className="text-3xl font-bold tracking-tight text-white/90">
                                    Document Vault
                                </h1>
                                <p className="text-white/60 mt-2">
                                    Upload and manage your documents
                                </p>
                                {/* Connection Status Indicator */}
                                <div className="flex items-center gap-2 mt-2">
                                    {isConnected ? (
                                        <div className="flex items-center gap-1.5 text-xs text-green-400">
                                            <Wifi className="h-3 w-3" />
                                            <span>Real-time updates</span>
                                        </div>
                                    ) : usePolling ? (
                                        <div className="flex items-center gap-1.5 text-xs text-yellow-400">
                                            <WifiOff className="h-3 w-3" />
                                            <span>Polling mode</span>
                                        </div>
                                    ) : connectionStatus === 'connecting' ? (
                                        <div className="flex items-center gap-1.5 text-xs text-blue-400">
                                            <Loader2 className="h-3 w-3 animate-spin" />
                                            <span>Connecting...</span>
                                        </div>
                                    ) : null}
                                </div>
                            </div>
                        </div>
                        <div className="flex gap-2">
                            <Button
                                variant="outline"
                                onClick={() => router.push("/chat")}
                                className="bg-white/5 border-white/10 text-white/90 hover:bg-white/10 hover:text-white/90"
                            >
                                <MessageSquare className="mr-2 h-4 w-4" />
                                Back to Chat
                            </Button>
                            <Dialog open={uploadDialogOpen} onOpenChange={setUploadDialogOpen}>
                                <DialogTrigger asChild>
                                    <Button className="bg-violet-950 hover:bg-violet-900 text-white">
                                        <Upload className="mr-2 h-4 w-4" />
                                        Upload Document
                                    </Button>
                                </DialogTrigger>
                                <DialogContent className="bg-[#0A0A0B] border-white/10 text-white">
                                    <DialogHeader>
                                        <DialogTitle className="text-white">Upload Document</DialogTitle>
                                        <DialogDescription className="text-white/60">
                                            Upload PDF, DOCX, TXT, or MD files to the secure vault.
                                        </DialogDescription>
                                    </DialogHeader>
                                    <form onSubmit={handleUpload} className="space-y-4">
                                        <div className="grid w-full max-w-sm items-center gap-1.5">
                                            <Label htmlFor="file" className="text-white/70">Document</Label>
                                            <div className="flex items-center gap-2">
                                                <input
                                                    ref={fileInputRef}
                                                    id="file"
                                                    name="file"
                                                    type="file"
                                                    accept=".pdf,.docx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown"
                                                    required
                                                    onChange={handleFileChange}
                                                    className="hidden"
                                                />
                                                <Button
                                                    type="button"
                                                    variant="outline"
                                                    onClick={() => fileInputRef.current?.click()}
                                                    className="bg-white/5 border-white/10 text-white hover:bg-white/10 hover:text-white"
                                                >
                                                    Browse
                                                </Button>
                                                {selectedFileName && (
                                                    <span className="text-sm text-white/70 truncate max-w-[200px]">
                                                        {selectedFileName}
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                        <Button
                                            type="submit"
                                            disabled={uploading}
                                            className="w-full bg-violet-950 hover:bg-violet-900 text-white"
                                        >
                                            {uploading ? "Uploading..." : "Upload"}
                                        </Button>
                                    </form>
                                </DialogContent>
                            </Dialog>
                        </div>
                    </div>

                    <Card className="bg-white/[0.02] border-white/[0.05] backdrop-blur-2xl">
                        <CardHeader>
                            <CardTitle className="text-white/90">Files</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {loading ? (
                                <p className="text-white/70">Loading documents...</p>
                            ) : documents.length === 0 ? (
                                <p className="text-white/50">No documents found. Upload one to get started.</p>
                            ) : (
                                <Table>
                                    <TableHeader>
                                        <TableRow className="border-white/10">
                                            <TableHead className="text-white/70">Name</TableHead>
                                            <TableHead className="text-white/70">Type</TableHead>
                                            <TableHead className="text-white/70">Status</TableHead>
                                            <TableHead className="text-white/70">Uploaded At</TableHead>
                                            <TableHead className="text-right text-white/70">Actions</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {documents.map((doc) => {
                                            const status = doc.status || "processing";
                                            const isDeleting = deletingId === doc.id;
                                            const isFailed = status === "error";  // Backend uses "error" for failed
                                            const isProcessing = status === "processing";
                                            const isReady = status === "ready";  // Backend uses "ready" for completed

                                            return (
                                                <TableRow key={doc.id} className="border-white/10 hover:bg-white/[0.02]">
                                                    <TableCell className="font-medium text-white/90">
                                                        <div className="flex items-center gap-2">
                                                            <FileText className="h-4 w-4 text-white/70" />
                                                            <span>{doc.title}</span>
                                                        </div>
                                                    </TableCell>
                                                    <TableCell className="text-white/70">
                                                        <div className="relative inline-block max-w-[120px] overflow-hidden">
                                                            <span className="block truncate pr-4">{doc.mime_type?.split('/')[1]?.toUpperCase() || 'Unknown'}</span>
                                                            <div className="absolute right-0 top-0 bottom-0 w-6 bg-gradient-to-l from-[#0A0A0B] via-[#0A0A0B]/80 to-transparent pointer-events-none"></div>
                                                        </div>
                                                    </TableCell>
                                                    <TableCell>
                                                        {isReady ? (
                                                            <div className="space-y-1">
                                                                <span className="flex items-center gap-1 text-green-400">
                                                                    <CheckCircle2 className="h-3 w-3" />
                                                                    <span className="text-xs">Ready</span>
                                                                </span>
                                                                {doc.chunk_count > 0 && (
                                                                    <div className="text-[10px] text-white/40">
                                                                        {doc.chunk_count} chunks • {doc.page_count} pages
                                                                    </div>
                                                                )}
                                                            </div>
                                                        ) : isFailed ? (
                                                            <div className="space-y-1">
                                                                <span className="flex items-center gap-1 text-red-400">
                                                                    <XCircle className="h-3 w-3" />
                                                                    <span className="text-xs">Failed</span>
                                                                </span>
                                                                {doc.error_message && (
                                                                    <div
                                                                        className="text-[10px] text-red-300 max-w-[200px] truncate cursor-help"
                                                                        title={doc.error_message}
                                                                    >
                                                                        {doc.error_message}
                                                                    </div>
                                                                )}
                                                            </div>
                                                        ) : isProcessing ? (
                                                            <span className="flex items-center gap-1 text-yellow-400">
                                                                <Loader2 className="h-3 w-3 animate-spin" />
                                                                <span className="text-xs">Processing</span>
                                                            </span>
                                                        ) : (
                                                            <span className="flex items-center gap-1 text-white/50">
                                                                <span className="text-xs">Unknown</span>
                                                            </span>
                                                        )}
                                                    </TableCell>
                                                    <TableCell className="text-white/70">{new Date(doc.created_at).toLocaleDateString()}</TableCell>
                                                    <TableCell className="text-right">
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            onClick={() => handleDelete(doc.id, doc.title)}
                                                            disabled={isDeleting}
                                                            className="text-red-400 hover:text-red-300 hover:bg-red-500/20"
                                                        >
                                                            {isDeleting ? (
                                                                <Loader2 className="h-4 w-4 animate-spin" />
                                                            ) : (
                                                                <Trash2 className="h-4 w-4" />
                                                            )}
                                                        </Button>
                                                    </TableCell>
                                                </TableRow>
                                            );
                                        })}
                                    </TableBody>
                                </Table>
                            )}
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    );
}
