"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { fetchWithAuth, getDocumentUrl, getDocumentDownloadUrl, API_URL, sendChatMessage, sendChatMessageStream, getConversation, listConversations, uploadFileWithAuth } from "@/lib/api";
import { ChatSidebar } from "@/components/ui/GrokSidebar"; // This will be removed in next step (actually I should just replace it now)
// Wait, I should replace the imports directly.

import { AppSidebar } from "@/components/AppSidebar";
import { DashboardHome } from "@/components/DashboardHome";
import { AnimatedChatInput, TypingIndicator } from "@/components/AnimatedChatInput";
import { Card, CardContent } from "@/components/ui/card";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Download, FileText, Loader2, CheckCircle2, XCircle, Copy, Check, RefreshCw, Volume2, ThumbsUp, ThumbsDown, MoreHorizontal, CornerDownRight } from "lucide-react";
import Image from "next/image";
import { motion, AnimatePresence } from "framer-motion";
import { cn, findLongestCommonSubstring } from "@/lib/utils";
import { toast } from "sonner";

// Import PDFViewerWrapper directly - it already handles SSR internally
import { PDFViewerWrapper } from "@/components/PDFViewerWrapper";
import CodeBlock from "@/components/CodeBlock";
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface Message {
    role: "user" | "assistant";
    content: string;
    citations?: any[];
    documents?: any[]; // For document list responses
    uploadedDocument?: any; // For uploaded documents in chat
    suggestions?: string[]; // Follow-up suggestions
}

export default function ChatPage() {
    const router = useRouter();
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    // Persist conversation ID in localStorage so it persists across navigation
    const [currentConversationId, setCurrentConversationIdState] = useState<string | null>(() => {
        if (typeof window !== 'undefined') {
            return localStorage.getItem('currentConversationId');
        }
        return null;
    });
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const isActiveConversationRef = useRef(false);

    // Wrapper to persist conversation ID to localStorage
    const setCurrentConversationId = (id: string | null) => {
        setCurrentConversationIdState(id);
        if (typeof window !== 'undefined') {
            if (id) {
                localStorage.setItem('currentConversationId', id);
            } else {
                localStorage.removeItem('currentConversationId');
            }
        }
    };

    // File upload state
    const [uploadingFile, setUploadingFile] = useState(false);
    const [copiedMessageIndex, setCopiedMessageIndex] = useState<number | null>(null);
    const [sidebarRefreshTrigger, setSidebarRefreshTrigger] = useState(0);

    // PDF Viewer state (no persistence - user can click citation again after refresh)
    const [pdfViewerOpen, setPdfViewerOpen] = useState(false);
    const [pdfViewerUrl, setPdfViewerUrl] = useState<string>("");
    const [pdfViewerFileName, setPdfViewerFileName] = useState<string>("");
    const [pdfViewerCitation, setPdfViewerCitation] = useState<any>(null);
    const [pdfViewerAllCitations, setPdfViewerAllCitations] = useState<any[]>([]);

    useEffect(() => {
        const checkSession = async () => {
            const { data } = await supabase.auth.getSession();
            if (!data.session) {
                router.push("/login");
            } else {
                localStorage.setItem("supabase_token", data.session.access_token);
            }
        };
        checkSession();
    }, [router]);

    // Load conversation when conversationId changes (e.g., from sidebar selection or on mount)
    // But don't reload if we're actively in a conversation (loading or streaming)
    useEffect(() => {
        // Skip if we're actively sending a message (prevent race conditions)
        if (isActiveConversationRef.current || loading) {
            return;
        }

        if (currentConversationId) {
            // Always load conversation when ID changes (even if messages exist)
            // This ensures we show the correct conversation when navigating
            loadConversation(currentConversationId);
        } else {
            // Only clear messages if we have messages (and we're not actively sending)
            // This prevents clearing the user's message when they send the first message in a new chat
            if (messages.length > 0 && !isActiveConversationRef.current) {
                setMessages([]);
            }
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [currentConversationId]); // Only depend on currentConversationId to avoid unnecessary reloads

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    const createNewConversation = async () => {
        // Conversations are created automatically when sending first message with null conversation_id
        setCurrentConversationId(null);
        setMessages([]);
    };

    const loadConversation = async (convId: string, preserveMessages: boolean = false) => {
        try {
            setLoading(true);
            try {
                const response = await getConversation(convId);

                // Optimized: Single pass transformation instead of map + flatMap
                const transformedMessages: Message[] = [];
                const messages = response.messages || [];

                for (let i = 0; i < messages.length; i++) {
                    const msg = messages[i];

                    // Add user message
                    transformedMessages.push({
                        role: "user",
                        content: msg.user_message || "",
                    });

                    // Add assistant message with citations
                    const citations = (msg.citations || []).map((cit: any, idx: number) => {
                        const mapped = {
                            ...cit,
                            // Ensure content field exists for highlighting (map from quote/text_snippet)
                            content: cit.content || cit.quote || cit.text_snippet || "",
                            // Normalize other fields
                            page_number: cit.page_number || cit.page,
                            file_name: cit.file_name || cit.document_name || "Unknown",
                        };
                        return mapped;
                    });

                    let content = msg.assistant_message || "";

                    // Transform citation format: [CITATION X] -> [X] (single pass)
                    for (let j = 0; j < citations.length; j++) {
                        const cit = citations[j];
                        // Replace [CITATION X] with [X]
                        content = content.replace(new RegExp(`\\[CITATION ${cit.id}\\]`, 'g'), `[${cit.id}]`);
                    }

                    transformedMessages.push({
                        role: "assistant",
                        content: content,
                        citations: citations,
                    });
                }

                setMessages(transformedMessages);
                setLoading(false);
            } catch (error: any) {
                // Determine if this is a "not found" error
                // The backend returns 404 with detail "Conversation not found"
                const errorMessage = error.message?.toLowerCase() || "";
                const isNotFound = errorMessage.includes("conversation not found") ||
                    errorMessage.includes("not found") ||
                    errorMessage.includes("404");

                // Handle "Conversation not found" gracefully
                if (isNotFound) {
                    // CRITICAL: Stop loading state before resetting
                    setLoading(false);

                    // Reset to new conversation (don't alert user, just redirect/clear)
                    setCurrentConversationId(null);
                    setMessages([]);

                    // Update URL silently to /chat (removes bad ID)
                    router.push('/chat');
                    return;
                }
                throw error; // Re-throw other errors
            }
        } catch (error) {
            console.error("Failed to load conversation:", error);
            // toast({
            //     title: "Error",
            //     description: "Failed to load history. Starting new chat.",
            //     variant: "destructive",
            // });
            setLoading(false);
        }
    };



    const submitMessage = async (text: string) => {
        if (!text.trim() || loading) return;

        const activeConversationId = currentConversationId;
        isActiveConversationRef.current = true;
        const query = text.trim();
        setLoading(true);

        // Add user message
        const userMessage: Message = { role: "user", content: query };
        setMessages((prev) => [...prev, userMessage]);

        // Add placeholder assistant message
        const placeholderId = "streaming-" + Date.now();
        const placeholderMessage: Message = {
            role: "assistant",
            content: "",
            citations: []
        };
        setMessages((prev) => [...prev, placeholderMessage]);

        try {
            const response = await sendChatMessageStream({
                conversation_id: activeConversationId || null,
                message: query,
                document_ids: null
            });

            // Handle Streaming Response
            const reader = response.body?.getReader();
            const decoder = new TextDecoder();

            if (!reader) throw new Error("No response body");

            let done = false;
            let currentContent = "";
            let buffer = "";

            while (!done) {
                const { value, done: doneReading } = await reader.read();
                done = doneReading;
                const chunkValue = decoder.decode(value, { stream: true });
                buffer += chunkValue;

                // Process complete SSE messages (separated by \n\n)
                const parts = buffer.split('\n\n');
                buffer = parts.pop() || ""; // Keep the incomplete part

                for (const part of parts) {
                    const lines = part.split('\n');
                    let eventType = "";
                    let data = "";

                    for (const line of lines) {
                        if (line.startsWith("event: ")) {
                            eventType = line.substring(7).trim();
                        } else if (line.startsWith("data: ")) {
                            data = line.substring(6);
                        }
                    }

                    if (eventType === "conversation_id") {
                        const newConvId = data.trim();
                        if (!activeConversationId && newConvId) {
                            setCurrentConversationId(newConvId);
                            setSidebarRefreshTrigger(prev => prev + 1);
                        }
                    } else if (eventType === "status") {
                        try {
                            const statusMsg = JSON.parse(data);
                            // Show status update if no tokens received yet
                            setMessages((prev) => {
                                const newMessages = [...prev];
                                const lastMsg = newMessages[newMessages.length - 1];
                                if (lastMsg.role === "assistant" && currentContent === "") {
                                    lastMsg.content = `*${statusMsg}*`;
                                }
                                return newMessages;
                            });
                        } catch (e) { console.error(e); }
                    } else if (eventType === "token") {
                        try {
                            const token = JSON.parse(data);
                            currentContent += token;
                            // Update UI with accumulated content
                            setMessages((prev) => {
                                const newMessages = [...prev];
                                const lastMsg = newMessages[newMessages.length - 1];
                                if (lastMsg && lastMsg.role === "assistant") {
                                    lastMsg.content = currentContent;
                                }
                                return newMessages;
                            });
                        } catch (e) {
                            console.error("Error parsing token", e);
                        }
                    } else if (eventType === "result") {
                        try {
                            const result = JSON.parse(data);
                            // Final update with citations and exact content
                            let finalAnswer = result.answer;

                            // Citation processing (normalize format)
                            const citations = (result.citations || []).map((cit: any, idx: number) => {
                                const citationId = cit.id || cit.citation_id || (idx + 1);
                                // Replace [CITATION X] with [X]
                                finalAnswer = finalAnswer.replace(new RegExp(`\\[CITATION ${citationId}\\]`, 'g'), `[${idx + 1}]`);
                                // Replace 📄[X] with [X]
                                finalAnswer = finalAnswer.replace(new RegExp(`📄\\[${citationId}\\]`, 'g'), `[${idx + 1}]`);
                                return {
                                    id: idx + 1,
                                    document_id: cit.document_id,
                                    document_name: cit.document_name || cit.file_name || "Unknown",
                                    file_name: cit.file_name || cit.document_name || "Unknown",
                                    page_number: cit.page || cit.page_number,
                                    content: cit.quote || cit.text_snippet || cit.content,
                                    start_char_idx: cit.start_char || cit.start_char_idx,
                                    end_char_idx: cit.end_char || cit.end_char_idx,
                                };
                            });

                            // Generate follow-up suggestions based on the response
                            const { cleanedAnswer, suggestions } = generateFollowUpSuggestions(finalAnswer, citations);

                            setMessages((prev) => {
                                const newMessages = [...prev];
                                const lastMsg = newMessages[newMessages.length - 1];
                                if (lastMsg && lastMsg.role === "assistant") {
                                    lastMsg.content = cleanedAnswer; // Use cleaned answer without "Want to explore more?" section
                                    lastMsg.citations = citations;
                                    lastMsg.suggestions = suggestions;
                                }
                                return newMessages;
                            });
                        } catch (e) {
                            console.error("Error parsing result", e);
                        }
                    } else if (eventType === "error") {
                        throw new Error(JSON.parse(data));
                    }
                }
            }

        } catch (e: any) {
            console.error("Chat error:", e);
            const errorMessage = e.message || e.detail || "Unknown error";
            setMessages((prev) => {
                const newMessages = [...prev];
                const lastMsg = newMessages[newMessages.length - 1];
                if (lastMsg.role === "assistant") {
                    if (lastMsg.content) {
                        lastMsg.content += `\n\n*Error: ${errorMessage}*`;
                    } else {
                        lastMsg.content = `Sorry, I encountered an error: ${errorMessage}`;
                    }
                } else {
                    // Fallback if no assistant message exists (rare)
                    newMessages.push({ role: "assistant", content: `Sorry, I encountered an error: ${errorMessage}` });
                }
                return newMessages;
            });
        } finally {
            setLoading(false);
            isActiveConversationRef.current = false;
        }
    };

    const handleSend = async (message?: string) => {
        // If message is provided (from DashboardHome), use it. Otherwise use local input.
        const textToSend = typeof message === 'string' ? message : input;

        if (!textToSend.trim()) return;

        // If it's from local input, clear it
        if (typeof message !== 'string') {
            setInput("");
        }

        await submitMessage(textToSend);
    };

    const handleFileUpload = async (file: File) => {
        // Validate file type
        const allowedExtensions = ['.pdf', '.docx'];
        const fileName = file.name.toLowerCase();
        const isValid = allowedExtensions.some(ext => fileName.endsWith(ext));

        if (!isValid) {
            toast.error('Invalid file type', {
                description: 'Please upload only PDF or DOCX files.',
            });
            return;
        }

        setUploadingFile(true);

        try {
            // Use documents upload endpoint
            const result = await uploadFileWithAuth("/documents/upload", file);

            // Add user message showing the uploaded file
            setMessages((prev) => [...prev, {
                role: "user",
                content: `Uploaded: ${file.name}`,
                uploadedDocument: {
                    id: result.document_id,
                    title: result.name || file.name,
                    status: result.status || "processing"
                }
            }]);

            // Add assistant confirmation message
            setMessages((prev) => [...prev, {
                role: "assistant",
                content: `File "${file.name}" has been uploaded successfully. It's being processed and will be available in your document vault shortly.`,
                citations: []
            }]);

            // AUTO-SUMMARY: Trigger a summary request automatically
            // This satisfies "give without prompt"
            setTimeout(() => {
                submitMessage(`Summarize the document "${file.name}" I just uploaded.`);
            }, 500); // Small delay for visual flow

        } catch (e: any) {
            console.error("File upload error", e);
            toast.error('Upload failed', {
                description: e.message || 'An error occurred while uploading the file.',
            });
            setMessages((prev) => [...prev, {
                role: "assistant",
                content: `Sorry, I encountered an error uploading the file: ${e.message || "Upload failed"}`,
                citations: []
            }]);
        } finally {
            setUploadingFile(false);
        }
    };

    // Simple markdown renderer - converts **text** to bold
    const renderMarkdown = (text: string) => {
        // Split by ** markers and render bold text
        const parts = text.split(/(\*\*.*?\*\*)/g);
        return parts.map((part, i) => {
            if (part.startsWith('**') && part.endsWith('**')) {
                const boldText = part.slice(2, -2);
                return <strong key={i} className="font-semibold">{boldText}</strong>;
            }
            return <span key={i}>{part}</span>;
        });
    };


    const handleCitationClick = async (citation: any, allCitations: any[] = []) => {
        try {
            // Get document download URL from backend
            const response = await getDocumentDownloadUrl(citation.document_id);
            const documentUrl = response.url || response;

            if (!documentUrl) {
                throw new Error("No document URL returned from server");
            }

            // Check if file is DOCX - download instead of viewing
            const fileName = citation.file_name || citation.document_name || "Document";
            const isDocx = fileName.toLowerCase().endsWith('.docx') ||
                fileName.toLowerCase().includes('vnd.openxmlformats');

            if (isDocx) {
                // Download DOCX file directly

                // Create temporary link and trigger download
                const link = document.createElement('a');
                link.href = documentUrl;
                link.download = fileName;
                link.target = '_blank';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);

                // Show notification
                toast.info('Downloading document', {
                    description: `${fileName} - DOCX files cannot be viewed in the browser.`,
                });

                return;
            }

            // Filter citations for the same document
            const documentCitations = allCitations.filter(
                (cit) => cit.document_id === citation.document_id
            );

            // For PDF files, open in viewer
            setPdfViewerUrl(documentUrl);
            setPdfViewerFileName(fileName);
            setPdfViewerCitation(citation);
            setPdfViewerAllCitations(documentCitations.length > 0 ? documentCitations : [citation]);

            // SMART HIGHLIGHTING (The "Magic Fix")
            // 1. Get the full citation content (the big chunk with 15 items)
            const fullChunkContent = citation.content || "";

            // 2. Get the assistant's answer text associated with this message
            // We need to find the message that contains this citation
            const parentMessage = messages.find(m => m.citations && m.citations.some(c => c.id === citation.id));
            const answerText = parentMessage ? parentMessage.content : "";

            // 3. Find the "Intersection" (Text used in BOTH the Answer and the Chunk)
            let refinedHighlight = fullChunkContent;

            if (answerText && fullChunkContent.length > 500) {
                // Heuristic: If the chunk is huge, try to narrow it down.
                // We split the answer into sentences and find which sentence matches the chunk best.

                // Tokenize answer into meaningful words (ignore short words)
                const answerTokens = answerText.toLowerCase()
                    .replace(/[^\w\s]/g, '')
                    .split(/\s+/)
                    .filter(w => w.length > 4);

                if (answerTokens.length > 0) {
                    const chunkWords = fullChunkContent.split(/\s+/);
                    const windowSize = Math.min(chunkWords.length, 50);

                    let bestWindowScore = 0;
                    let bestWindowStart = 0;
                    let bestWindowEnd = 0;

                    for (let i = 0; i < chunkWords.length - windowSize; i += 5) {
                        const currentWindowWords = chunkWords.slice(i, i + windowSize);
                        const currentWindowText = currentWindowWords.join(" ").toLowerCase();

                        let score = 0;
                        for (const token of answerTokens) {
                            if (currentWindowText.includes(token)) score++;
                        }

                        if (score > bestWindowScore) {
                            bestWindowScore = score;
                            bestWindowStart = i;
                            bestWindowEnd = i + windowSize + 10;
                        }
                    }

                    if (bestWindowScore >= 3) {
                        const buffer = 10;
                        const start = Math.max(0, bestWindowStart - buffer);
                        const end = Math.min(chunkWords.length, bestWindowEnd + buffer);
                        refinedHighlight = chunkWords.slice(start, end).join(" ");
                        console.log("Refined Highlight (Fuzzy):", refinedHighlight);
                    }
                }

            }

            // Pass the refined (shorter, precise) text to the viewer
            setPdfViewerCitation({
                ...citation,
                content: refinedHighlight
            });

            setPdfViewerOpen(true);
        } catch (error: any) {
            console.error("Error opening document:", error);

            // Show user-friendly error message
            const errorMessage = error.message || "Unknown error";

            if (errorMessage.includes("timeout") || errorMessage.includes("Timeout")) {
                toast.error('Document loading timeout', {
                    description: 'The document is taking too long to load. Please try again.',
                });
            } else {
                // Show error with citation details
                toast.error('Unable to open PDF viewer', {
                    description: `${errorMessage} - Document: ${citation.document_name || 'Unknown'}`,
                });
            }
        }
    };

    const handleDocumentView = (documentId: string) => {
        // Open document in new page
        window.open(`/documents/${documentId}`, '_blank');
    };

    const handleCopyMessage = (content: string, index: number) => {
        navigator.clipboard.writeText(content);
        setCopiedMessageIndex(index);
        setTimeout(() => setCopiedMessageIndex(null), 2000);
    };

    const handleRegenerateResponse = async () => {
        // Get the last user message
        const lastUserMessage = messages.filter(m => m.role === "user").pop();
        if (lastUserMessage) {
            // Remove the last assistant response
            setMessages(prev => prev.slice(0, -1));
            // Regenerate
            await submitMessage(lastUserMessage.content);
        }
    };

    const generateFollowUpSuggestions = (answer: string, citations: any[]): { cleanedAnswer: string; suggestions: string[] } => {
        // Extract suggestions from the LLM response text
        const suggestions: string[] = [];
        let cleanedAnswer = answer;

        // Look for "Want to explore more?" or similar patterns
        const explorePattern = /(?:Want to explore more\?|You could ask:|Here are some follow-up questions:)\s*\n+((?:[-•]\s*.+\?\n*)+)/i;
        const match = answer.match(explorePattern);

        if (match) {
            // Extract the bullet points
            const bulletSection = match[1];
            const bullets = bulletSection.match(/[-•]\s*(.+\?)/g);

            if (bullets) {
                bullets.forEach(bullet => {
                    const question = bullet.replace(/^[-•]\s*/, '').trim();
                    suggestions.push(question);
                });
            }

            // Remove the entire "Want to explore more?" section from the answer
            cleanedAnswer = answer.replace(explorePattern, '').trim();
        }

        // Only generate default suggestions for substantial responses
        // Skip for simple greetings or short responses without citations
        const isSubstantialResponse = (
            (citations && citations.length > 0) || // Has citations
            cleanedAnswer.length > 200 || // Long response
            cleanedAnswer.includes('\n\n') // Multiple paragraphs
        );

        if (suggestions.length === 0 && isSubstantialResponse) {
            if (citations && citations.length > 0) {
                suggestions.push("Tell me more about these sources");
                suggestions.push("Summarize the key points from the citations");
            }
            suggestions.push("Can you explain this in simpler terms?");
        }

        return {
            cleanedAnswer,
            suggestions: suggestions.slice(0, 3) // Limit to 3 suggestions
        };
    };

    const handleSuggestionClick = (suggestion: string) => {
        submitMessage(suggestion);
    };


    const renderMessage = (message: Message, index: number) => {
        if (message.role === "user") {
            return (
                <motion.div
                    key={index}
                    className="flex justify-end mb-6"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                >
                    <div className="max-w-[70%] space-y-2">
                        {message.content && (
                            <div className="px-5 py-3 bg-[#2f2f2f] rounded-3xl">
                                <p className="text-white text-[15px] leading-relaxed">{message.content}</p>
                            </div>
                        )}
                        {message.uploadedDocument && (
                            <div className="px-4 py-3 bg-violet-500/10 rounded-2xl border border-violet-500/20 flex items-center gap-3">
                                <FileText className="h-5 w-5 text-violet-400 flex-shrink-0" />
                                <div className="flex-1 min-w-0">
                                    <p className="text-white/90 text-sm font-medium truncate">{message.uploadedDocument.title}</p>
                                    <div className="flex items-center gap-2 mt-1">
                                        {message.uploadedDocument.status === "completed" && (
                                            <span className="flex items-center gap-1 text-xs text-green-400">
                                                <CheckCircle2 className="h-3 w-3" />
                                                Processed
                                            </span>
                                        )}
                                        {message.uploadedDocument.status === "processing" && (
                                            <span className="flex items-center gap-1 text-xs text-yellow-400">
                                                <Loader2 className="h-3 w-3 animate-spin" />
                                                Processing...
                                            </span>
                                        )}
                                        {message.uploadedDocument.status === "failed" && (
                                            <span className="flex items-center gap-1 text-xs text-red-400">
                                                <XCircle className="h-3 w-3" />
                                                Failed
                                            </span>
                                        )}
                                    </div>
                                </div>
                                {message.uploadedDocument.id && (
                                    <button
                                        onClick={() => handleDocumentView(message.uploadedDocument.id)}
                                        className="px-2 py-1 text-xs bg-violet-500/20 hover:bg-violet-500/30 text-violet-300 rounded transition-colors"
                                    >
                                        View
                                    </button>
                                )}
                            </div>
                        )}
                    </div>
                </motion.div>
            );
        }

        // PRE-PROCESS CONTENT: Convert [N] to [N](#citation-N) to preserve markdown structure and avoid URL sanitization
        // This prevents lists from breaking when a citation is inserted
        const processedContent = message.content.replace(/\[(\d+)\]/g, '[$1](#citation-$1)');

        return (
            <motion.div
                key={index}
                className="flex justify-start mb-6"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
            >
                <div className="max-w-[85%] w-full space-y-3">
                    <div className="rounded-2xl">
                        <div className="text-white/95 text-[15px] leading-7">
                            <span className="inline prose prose-invert prose-p:inline prose-p:my-0 prose-headings:my-2 prose-ul:my-3 prose-li:my-1 prose-ul:list-disc prose-ul:pl-5 prose-ol:list-decimal prose-ol:pl-5 max-w-none text-white/95">
                                <ReactMarkdown
                                    remarkPlugins={[remarkGfm]}
                                    components={{
                                        // Override paragraph to add better spacing logic
                                        p: ({ node, ...props }: any) => <p className="mb-2.5 leading-7 last:mb-0" {...props} />,
                                        // Style lists - tighter spacing
                                        ul: ({ node, ...props }: any) => <ul className="list-disc pl-5 my-2.5 space-y-1.5" {...props} />,
                                        ol: ({ node, ...props }: any) => <ol className="list-decimal pl-5 my-2.5 space-y-1.5" {...props} />,
                                        li: ({ node, children, ...props }: any) => {
                                            // Check if the list item contains a question (ends with ?)
                                            const textContent = typeof children === 'string' ? children :
                                                (Array.isArray(children) ? children.join('') : String(children));
                                            const isQuestion = textContent.trim().endsWith('?');

                                            if (isQuestion) {
                                                return (
                                                    <li className="leading-7 group" {...props}>
                                                        <span
                                                            onClick={() => handleSuggestionClick(textContent.trim())}
                                                            className="cursor-pointer text-white/90 hover:text-violet-400 transition-colors underline decoration-transparent hover:decoration-violet-400"
                                                        >
                                                            {children}
                                                        </span>
                                                    </li>
                                                );
                                            }
                                            return <li className="leading-7" {...props}>{children}</li>;
                                        },
                                        // Style headings - tighter with content
                                        h1: ({ node, ...props }: any) => <h1 className="text-xl font-bold mt-4 mb-2 text-white" {...props} />,
                                        h2: ({ node, ...props }: any) => <h2 className="text-lg font-semibold mt-4 mb-2 text-white" {...props} />,
                                        h3: ({ node, ...props }: any) => <h3 className="text-base font-semibold mt-3 mb-1.5 text-white" {...props} />,
                                        // Style code blocks
                                        code: CodeBlock,
                                        // Style tables
                                        table: ({ node, ...props }: any) => <div className="my-4 w-full overflow-hidden rounded-lg border border-white/10"><table className="w-full border-collapse bg-black/20" {...props} /></div>,
                                        thead: ({ node, ...props }: any) => <thead className="bg-white/5" {...props} />,
                                        tbody: ({ node, ...props }: any) => <tbody className="divide-y divide-white/5" {...props} />,
                                        tr: ({ node, ...props }: any) => <tr className="hover:bg-white/5 transition-colors" {...props} />,
                                        th: ({ node, ...props }: any) => <th className="px-4 py-3 text-left text-sm font-semibold text-white/90 border-b border-white/10" {...props} />,
                                        td: ({ node, ...props }: any) => <td className="px-4 py-3 text-sm text-white/70" {...props} />,
                                        // CUSTOM LINK RENDERER for Citations
                                        a: ({ node, href, children, ...props }: any) => {
                                            // Check if it's a citation link
                                            if (href && href.startsWith('#citation-')) {
                                                const citationId = parseInt(href.split('#citation-')[1]);
                                                const citation = message.citations?.find((c: any) => c.id === citationId);

                                                if (citation) {
                                                    return (
                                                        <span
                                                            onClick={(e) => {
                                                                e.preventDefault();
                                                                e.stopPropagation();
                                                                handleCitationClick(citation, message.citations || []);
                                                            }}
                                                            className="relative group inline-flex items-center justify-center px-1 text-xs font-medium text-violet-400 hover:text-violet-300 cursor-pointer transition-colors align-baseline select-none"
                                                            title={`${citation.document_name || 'Document'}${citation.page_number ? ` - Page ${citation.page_number}` : ''}`}
                                                        >
                                                            [{citationId}]
                                                            {/* Tooltip */}
                                                            <span className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 w-72 bg-gray-900 text-white text-xs rounded-lg shadow-xl opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 border border-white/10 text-left">
                                                                <span className="block font-semibold mb-1 text-violet-300">{citation.document_name || 'Document'}</span>
                                                                {citation.page_number && (
                                                                    <span className="block text-violet-400 mb-2 text-[11px]">Page {citation.page_number}</span>
                                                                )}
                                                                {citation.content && (
                                                                    <span className="block text-white/70 text-[11px] line-clamp-5 whitespace-pre-wrap">{citation.content}</span>
                                                                )}
                                                                <span className="absolute bottom-0 left-1/2 transform -translate-x-1/2 translate-y-full w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-gray-900"></span>
                                                            </span>
                                                        </span>
                                                    );
                                                }
                                                // Fallback if citation not found
                                                return <span className="text-xs text-white/50">[{citationId}]</span>;
                                            }

                                            // Regular link
                                            return <a href={href} className="text-violet-400 hover:text-violet-300 underline" target="_blank" rel="noopener noreferrer" {...props}>{children}</a>;
                                        },
                                        // Style blockquotes
                                        blockquote: ({ node, ...props }: any) => <blockquote className="border-l-4 border-violet-500/50 pl-4 my-3 italic text-white/80" {...props} />,
                                    }}
                                >
                                    {processedContent}
                                </ReactMarkdown>
                            </span>
                        </div>
                    </div>

                    {message.documents && message.documents.length > 0 && (
                        <div className="mt-3 space-y-2">
                            <p className="text-xs text-white/50 font-medium">Documents:</p>
                            <div className="flex flex-col gap-2">
                                {message.documents.slice(0, 20).map((doc: any, idx: number) => (
                                    <div
                                        key={doc.id || idx}
                                        className="flex items-center justify-between px-3 py-2 bg-white/[0.05] hover:bg-white/[0.1] border border-white/[0.1] rounded-lg transition-colors"
                                    >
                                        <div className="flex items-center gap-2 flex-1 min-w-0">
                                            <span className="text-xs text-white/50">{idx + 1}.</span>
                                            <span className="text-xs text-white/70 truncate">
                                                {doc.status === "completed" ? "✅" : doc.status === "processing" ? "⏳" : "❌"} {doc.title || "Unknown Document"}
                                            </span>
                                            {doc.is_relevant && (
                                                <span className="text-xs text-violet-400 bg-violet-500/20 px-2 py-0.5 rounded">Relevant</span>
                                            )}
                                        </div>
                                        <button
                                            onClick={() => handleDocumentView(doc.id)}
                                            className="ml-2 px-2 py-1 text-xs bg-violet-500/20 hover:bg-violet-500/30 text-violet-300 rounded transition-colors"
                                        >
                                            View
                                        </button>
                                    </div>
                                ))}
                                {message.documents.length > 20 && (
                                    <p className="text-xs text-white/40 text-center">
                                        ... and {message.documents.length - 20} more documents
                                    </p>
                                )}
                            </div>
                        </div>
                    )}
                    {message.citations && message.citations.length > 0 && (
                        <div className="mt-4 pt-3 border-t border-white/10">
                            <p className="text-xs text-white/50 font-medium mb-2">Sources:</p>
                            <div className="flex flex-wrap gap-2">
                                {(() => {
                                    // Get unique document names
                                    const uniqueDocs = Array.from(
                                        new Map(
                                            message.citations.map((cit: any) => [
                                                cit.document_id,
                                                cit.document_name || cit.file_name || 'Unknown Document'
                                            ])
                                        ).values()
                                    );

                                    return uniqueDocs.map((docName: string, idx: number) => (
                                        <div
                                            key={idx}
                                            className="text-xs text-white/70 bg-white/[0.05] px-3 py-1.5 rounded-lg border border-white/[0.1]"
                                        >
                                            • {docName}
                                        </div>
                                    ));
                                })()}
                            </div>
                        </div>
                    )}

                    {/* Action Buttons - Only show when message is complete (not loading) */}
                    {!loading && message.content && (
                        <div className="flex items-center gap-2 mt-3 ml-1">
                            <button
                                onClick={handleRegenerateResponse}
                                className="p-1.5 text-white/40 hover:text-white/70 hover:bg-white/5 rounded-lg transition-colors"
                                title="Regenerate response"
                            >
                                <RefreshCw className="w-4 h-4" />
                            </button>
                            <button
                                className="p-1.5 text-white/40 hover:text-white/70 hover:bg-white/5 rounded-lg transition-colors"
                                title="Read aloud"
                            >
                                <Volume2 className="w-4 h-4" />
                            </button>
                            <button
                                onClick={() => handleCopyMessage(message.content, index)}
                                className="p-1.5 text-white/40 hover:text-white/70 hover:bg-white/5 rounded-lg transition-colors"
                                title="Copy"
                            >
                                {copiedMessageIndex === index ? (
                                    <Check className="w-4 h-4 text-green-400" />
                                ) : (
                                    <Copy className="w-4 h-4" />
                                )}
                            </button>
                            <button
                                className="p-1.5 text-white/40 hover:text-white/70 hover:bg-white/5 rounded-lg transition-colors"
                                title="Like"
                            >
                                <ThumbsUp className="w-4 h-4" />
                            </button>
                            <button
                                className="p-1.5 text-white/40 hover:text-white/70 hover:bg-white/5 rounded-lg transition-colors"
                                title="Dislike"
                            >
                                <ThumbsDown className="w-4 h-4" />
                            </button>
                            <button
                                className="p-1.5 text-white/40 hover:text-white/70 hover:bg-white/5 rounded-lg transition-colors"
                                title="More options"
                            >
                                <MoreHorizontal className="w-4 h-4" />
                            </button>
                            <div className="ml-2 flex items-center gap-1.5 px-2 py-1 text-xs text-white/40">
                                <span>1.4s</span>
                                <span className="text-white/30">Fast</span>
                            </div>
                        </div>
                    )}

                    {/* Follow-up Suggestions - Only show when message is complete */}
                    {!loading && message.suggestions && message.suggestions.length > 0 && (
                        <div className="mt-4 space-y-2">
                            {message.suggestions.map((suggestion, idx) => (
                                <button
                                    key={idx}
                                    onClick={() => handleSuggestionClick(suggestion)}
                                    disabled={loading}
                                    className="w-full text-left px-4 py-2.5 bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.08] rounded-lg transition-all duration-200 group disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    <div className="flex items-center gap-3">
                                        <CornerDownRight className="w-3.5 h-3.5 text-white/40 group-hover:text-white/60 transition-colors flex-shrink-0" />
                                        <span className="text-white/70 group-hover:text-white/90 text-sm transition-colors">
                                            {suggestion}
                                        </span>
                                    </div>
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            </motion.div>
        );
    };

    return (
        <div className="flex h-screen bg-[#0A0A0B] text-white overflow-hidden">
            {/* Sidebar */}
            {/* Sidebar */}
            <AppSidebar
                currentConversationId={currentConversationId}
                onSelectConversation={(id) => {
                    // Clear messages first, then load new conversation
                    setMessages([]);
                    setCurrentConversationId(id);
                    // loadConversation will be triggered by useEffect
                }}
                onNewChat={() => {
                    setCurrentConversationId(null);
                    setMessages([]);
                }}
                refreshTrigger={sidebarRefreshTrigger}
            />

            {/* Main Content Area - Split View */}
            <div className="flex-1 flex overflow-hidden">
                {/* Chat Column */}
                <div className={cn(
                    "flex flex-col relative transition-all duration-300 ease-in-out",
                    pdfViewerOpen && pdfViewerUrl ? "w-1/2" : "w-full"
                )}>
                    {/* Background Gradients (only show when full width or confined to chat) */}
                    <div className="absolute inset-0 overflow-hidden pointer-events-none">
                        <div className="absolute top-0 left-1/4 w-96 h-96 bg-violet-500/10 rounded-full mix-blend-normal filter blur-[128px] animate-pulse" />
                        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-indigo-500/10 rounded-full mix-blend-normal filter blur-[128px] animate-pulse delay-700" />
                    </div>

                    {/* Chat Messages */}
                    <div className="flex-1 overflow-y-auto p-6 relative z-10">
                        <div className="max-w-4xl mx-auto space-y-6">
                            {messages.length === 0 ? (
                                <div className="absolute inset-0 z-10 bg-[#000000]">
                                    <DashboardHome
                                        onSendMessage={handleSend}
                                        onFileUpload={handleFileUpload}
                                        isLoading={loading}
                                    />
                                </div>
                            ) : (
                                <>
                                    {messages.map((message, index) => renderMessage(message, index))}
                                    {loading && <TypingIndicator />}
                                    <div ref={messagesEndRef} />
                                </>
                            )}
                        </div>
                    </div>

                    {/* Chat Input - Only show when we have messages (otherwise it's in DashboardHome) */}
                    {messages.length > 0 && (
                        <div className="p-6 relative z-10">
                            <div className={cn("mx-auto transition-all duration-300", pdfViewerOpen ? "max-w-full" : "max-w-3xl")}>
                                <AnimatedChatInput
                                    value={input}
                                    onChange={setInput}
                                    onSend={handleSend}
                                    onFileUpload={handleFileUpload}
                                    isLoading={loading || uploadingFile}
                                />
                            </div>
                        </div>
                    )}
                </div>

                {/* PDF Viewer Panel (Right Column) */}
                <AnimatePresence>
                    {pdfViewerOpen && pdfViewerUrl && (
                        <motion.div
                            initial={{ width: 0, opacity: 0 }}
                            animate={{ width: "50%", opacity: 1 }}
                            exit={{ width: 0, opacity: 0 }}
                            transition={{ type: "spring", stiffness: 300, damping: 30 }}
                            className="bg-[#1a1a1b] border-l border-white/10 overflow-hidden relative shadow-2xl z-20"
                        >
                            <div className="absolute inset-0 w-full h-full">
                                <PDFViewerWrapper
                                    isOpen={pdfViewerOpen}
                                    onClose={() => setPdfViewerOpen(false)}
                                    key={`${pdfViewerUrl}-${pdfViewerCitation?.id || 'doc'}`}
                                    fileUrl={pdfViewerUrl}
                                    fileName={pdfViewerFileName}
                                    highlightPage={pdfViewerCitation?.page_number || 1}
                                    // Pass the full citation content for complete highlighting
                                    highlightText={pdfViewerCitation?.content}
                                    citations={pdfViewerAllCitations}
                                />
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
}
