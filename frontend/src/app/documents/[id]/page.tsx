"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { fetchWithAuth } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowLeft, Download, FileText, Loader2 } from "lucide-react";

export default function DocumentViewerPage() {
    const router = useRouter();
    const params = useParams();
    const documentId = params.id as string;
    
    const [document, setDocument] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [downloading, setDownloading] = useState(false);

    useEffect(() => {
        const checkSessionAndLoad = async () => {
            const { data } = await supabase.auth.getSession();
            if (!data.session) {
                router.push("/login");
                return;
            }

            localStorage.setItem("supabase_token", data.session.access_token);
            await loadDocument();
        };

        checkSessionAndLoad();
    }, [documentId, router]);

    const loadDocument = async () => {
        try {
            setLoading(true);
            const { getDocument } = await import("@/lib/api");
            const doc = await getDocument(documentId);
            
            // Transform backend format to frontend format
            setDocument({
                id: doc.document_id,
                title: doc.name,
                mime_type: doc.file_type || "application/pdf",
                status: doc.status || "processing",
                created_at: doc.uploaded_at,
                storage_path: doc.storage_path,
                chunk_count: doc.total_chunks || 0,
            });
        } catch (e: any) {
            console.error("Error loading document:", e);
            setError(e.message || "Failed to load document");
        } finally {
            setLoading(false);
        }
    };

    const handleDownload = async () => {
        if (!document?.storage_path) return;

        try {
            setDownloading(true);
            const token = localStorage.getItem("supabase_token");
            
            // Get download URL from Supabase Storage
            const { data: { session } } = await supabase.auth.getSession();
            if (!session) {
                throw new Error("Not authenticated");
            }

            const { data, error } = await supabase.storage
                .from("documents")
                .createSignedUrl(document.storage_path, 3600); // 1 hour expiry

            if (error) throw error;

            if (data?.signedUrl) {
                // Open download in new tab
                window.open(data.signedUrl, '_blank');
            }
        } catch (e: any) {
            console.error("Download error:", e);
            alert("Failed to download document: " + e.message);
        } finally {
            setDownloading(false);
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-[#0A0A0B] text-white flex items-center justify-center">
                <div className="text-center space-y-4">
                    <Loader2 className="w-8 h-8 animate-spin mx-auto text-violet-400" />
                    <p className="text-white/60">Loading document...</p>
                </div>
            </div>
        );
    }

    if (error || !document) {
        return (
            <div className="min-h-screen bg-[#0A0A0B] text-white flex items-center justify-center">
                <Card className="w-full max-w-md bg-white/[0.02] border-white/[0.1]">
                    <CardContent className="p-6 text-center space-y-4">
                        <p className="text-red-400">{error || "Document not found"}</p>
                        <Button
                            onClick={() => router.push("/vault")}
                            className="bg-violet-500 hover:bg-violet-600"
                        >
                            <ArrowLeft className="w-4 h-4 mr-2" />
                            Back to Vault
                        </Button>
                    </CardContent>
                </Card>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-[#0A0A0B] text-white">
            {/* Header */}
            <div className="border-b border-white/[0.1] bg-white/[0.02] sticky top-0 z-10">
                <div className="max-w-7xl mx-auto px-6 py-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                            <Button
                                variant="ghost"
                                onClick={() => router.push("/vault")}
                                className="text-white/70 hover:text-white hover:bg-white/[0.05]"
                            >
                                <ArrowLeft className="w-4 h-4 mr-2" />
                                Back
                            </Button>
                            <div>
                                <h1 className="text-xl font-semibold text-white flex items-center gap-2">
                                    <FileText className="w-5 h-5" />
                                    {document.title}
                                </h1>
                                <p className="text-sm text-white/50 mt-1">
                                    {document.mime_type} • {document.chunk_count || 0} chunks
                                    {document.status && ` • ${document.status}`}
                                </p>
                            </div>
                        </div>
                        <Button
                            onClick={handleDownload}
                            disabled={downloading || !document.storage_path}
                            className="bg-violet-500 hover:bg-violet-600"
                        >
                            {downloading ? (
                                <>
                                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                    Downloading...
                                </>
                            ) : (
                                <>
                                    <Download className="w-4 h-4 mr-2" />
                                    Download
                                </>
                            )}
                        </Button>
                    </div>
                </div>
            </div>

            {/* Document Preview */}
            <div className="max-w-7xl mx-auto px-6 py-8">
                <Card className="bg-white/[0.02] border-white/[0.1]">
                    <CardHeader>
                        <CardTitle className="text-white">Document Information</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <p className="text-sm text-white/50">Title</p>
                                <p className="text-white">{document.title}</p>
                            </div>
                            <div>
                                <p className="text-sm text-white/50">Status</p>
                                <p className="text-white">
                                    {document.status === "completed" ? (
                                        <span className="text-green-400">✅ Completed</span>
                                    ) : document.status === "processing" ? (
                                        <span className="text-yellow-400">⏳ Processing</span>
                                    ) : (
                                        <span className="text-red-400">❌ Failed</span>
                                    )}
                                </p>
                            </div>
                            <div>
                                <p className="text-sm text-white/50">Type</p>
                                <p className="text-white">{document.mime_type || "Unknown"}</p>
                            </div>
                            <div>
                                <p className="text-sm text-white/50">Chunks</p>
                                <p className="text-white">{document.chunk_count || 0}</p>
                            </div>
                            {document.created_at && (
                                <div>
                                    <p className="text-sm text-white/50">Uploaded</p>
                                    <p className="text-white">
                                        {new Date(document.created_at).toLocaleDateString()}
                                    </p>
                                </div>
                            )}
                        </div>

                        {document.storage_path && (
                            <div className="pt-4 border-t border-white/[0.1]">
                                <p className="text-sm text-white/50 mb-2">Storage Path</p>
                                <p className="text-xs text-white/40 font-mono break-all">
                                    {document.storage_path}
                                </p>
                            </div>
                        )}

                        <div className="pt-4">
                            <p className="text-sm text-white/60 mb-2">
                                This document has been processed and is available for search in the chat interface.
                                Use the download button to get the original file.
                            </p>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}

