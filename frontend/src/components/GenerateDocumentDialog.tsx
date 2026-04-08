"use client";

import { useState } from "react";
import { fetchWithAuth } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import { Sparkles, FileText, Download, Loader2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface GenerateDocumentDialogProps {
    onGenerated?: () => void;
}

export function GenerateDocumentDialog({ onGenerated }: GenerateDocumentDialogProps) {
    const [isOpen, setIsOpen] = useState(false);
    const [loading, setLoading] = useState(false);
    const [generatedFiles, setGeneratedFiles] = useState<any[]>([]);

    const handleGenerate = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        const formData = new FormData(e.currentTarget);

        setLoading(true);
        setGeneratedFiles([]);

        try {
            const response = await fetchWithAuth("/generate/generate", {
                method: "POST",
                body: JSON.stringify({
                    document_type: formData.get("document_type"),
                    topic: formData.get("topic"),
                    instructions: formData.get("instructions") || undefined,
                    format: formData.get("format"),
                }),
            });

            setGeneratedFiles(response.files);
            if (onGenerated) onGenerated();
        } catch (e) {
            alert("Failed to generate document");
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    return (
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
            <DialogTrigger asChild>
                <Button className="bg-gradient-to-r from-violet-500 to-indigo-500 hover:from-violet-600 hover:to-indigo-600">
                    <Sparkles className="mr-2 h-4 w-4" />
                    Generate Document
                </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[500px] bg-[#0A0A0B] border-white/[0.1]">
                <DialogHeader>
                    <DialogTitle className="text-white">Generate AI Document</DialogTitle>
                    <DialogDescription className="text-white/60">
                        Create professional documents with AI. Includes watermark on all pages.
                    </DialogDescription>
                </DialogHeader>

                {generatedFiles.length === 0 ? (
                    <form onSubmit={handleGenerate} className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="document_type" className="text-white/80">Document Type</Label>
                            <select
                                id="document_type"
                                name="document_type"
                                required
                                className="flex h-10 w-full rounded-md border border-white/[0.1] bg-white/[0.05] px-3 py-2 text-sm text-white"
                            >
                                <option value="report">Report</option>
                                <option value="summary">Summary</option>
                                <option value="proposal">Proposal</option>
                                <option value="analysis">Analysis</option>
                            </select>
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="topic" className="text-white/80">Topic</Label>
                            <Input
                                id="topic"
                                name="topic"
                                placeholder="e.g., Q4 Sales Performance"
                                required
                                className="bg-white/[0.05] border-white/[0.1] text-white"
                            />
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="instructions" className="text-white/80">Additional Instructions (Optional)</Label>
                            <textarea
                                id="instructions"
                                name="instructions"
                                placeholder="Any specific requirements..."
                                className="flex min-h-[80px] w-full rounded-md border border-white/[0.1] bg-white/[0.05] px-3 py-2 text-sm text-white placeholder:text-white/40"
                            />
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="format" className="text-white/80">Output Format</Label>
                            <select
                                id="format"
                                name="format"
                                className="flex h-10 w-full rounded-md border border-white/[0.1] bg-white/[0.05] px-3 py-2 text-sm text-white"
                            >
                                <option value="pdf">PDF only</option>
                                <option value="docx">DOCX only</option>
                                <option value="both">Both PDF & DOCX</option>
                            </select>
                        </div>

                        <Button
                            type="submit"
                            disabled={loading}
                            className="w-full bg-white text-black hover:bg-white/90"
                        >
                            {loading ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Generating...
                                </>
                            ) : (
                                <>
                                    <Sparkles className="mr-2 h-4 w-4" />
                                    Generate Document
                                </>
                            )}
                        </Button>
                    </form>
                ) : (
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="space-y-4"
                    >
                        <div className="text-center py-4">
                            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-green-500/20 mb-4">
                                <FileText className="w-8 h-8 text-green-400" />
                            </div>
                            <h3 className="text-lg font-medium text-white mb-2">Document Generated!</h3>
                            <p className="text-sm text-white/60">Your document is ready for download</p>
                        </div>

                        <div className="space-y-2">
                            {generatedFiles.map((file, idx) => (
                                <div
                                    key={idx}
                                    className="flex items-center justify-between p-3 bg-white/[0.05] rounded-lg border border-white/[0.1]"
                                >
                                    <div className="flex items-center gap-2">
                                        <FileText className="w-4 h-4 text-white/60" />
                                        <span className="text-sm text-white">{file.filename}</span>
                                    </div>
                                    <Button
                                        size="sm"
                                        variant="ghost"
                                        className="text-violet-400 hover:text-violet-300"
                                        onClick={() => {
                                            // Download logic - will be in vault
                                            alert("Document saved to vault!");
                                        }}
                                    >
                                        <Download className="w-4 h-4" />
                                    </Button>
                                </div>
                            ))}
                        </div>

                        <Button
                            onClick={() => {
                                setGeneratedFiles([]);
                                setIsOpen(false);
                            }}
                            className="w-full"
                        >
                            Done
                        </Button>
                    </motion.div>
                )}
            </DialogContent>
        </Dialog>
    );
}
