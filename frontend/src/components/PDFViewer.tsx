"use client";

import { Worker, Viewer } from '@react-pdf-viewer/core';
import { defaultLayoutPlugin } from '@react-pdf-viewer/default-layout';
import { searchPlugin, Match } from '@react-pdf-viewer/search';
import { highlightPlugin, Trigger } from '@react-pdf-viewer/highlight';
import '@react-pdf-viewer/core/lib/styles/index.css';
import '@react-pdf-viewer/default-layout/lib/styles/index.css';
import '@react-pdf-viewer/search/lib/styles/index.css';
import '@react-pdf-viewer/highlight/lib/styles/index.css';
import { useState, useEffect } from 'react';
import { X } from 'lucide-react';

interface PDFViewerProps {
    isOpen: boolean;
    onClose: () => void;
    fileUrl: string;
    fileName: string;
    highlightPage?: number;
    highlightText?: string;
    citations: any[];
}

interface HighlightArea {
    height: number;
    left: number;
    pageIndex: number;
    top: number;
    width: number;
}

const PDFViewer: React.FC<PDFViewerProps> = ({
    isOpen,
    onClose,
    fileUrl,
    fileName,
    highlightPage,
    highlightText,
    citations,
}) => {
    const [currentPage, setCurrentPage] = useState(highlightPage || 1);
    const [error, setError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [searchKeywords, setSearchKeywords] = useState<string[]>([]);

    // Extract search keyword when component mounts or highlightText changes
    // Extract search keyword when component mounts or highlightText changes
    useEffect(() => {
        if (highlightText) {
            // 1. Basic cleanup: spaces and newlines
            let cleanText = highlightText
                .replace(/\r?\n|\r/g, ' ')
                .replace(/\s+/g, ' ');

            // 2. Remove citation markers like [1], (1), [12] which confuse search
            cleanText = cleanText.replace(/\[\d+\]/g, '').replace(/\(\d+\)/g, '');

            cleanText = cleanText.trim();

            // Strategy: Search for shorter chunks to handle PDF text layer inconsistencies
            // (e.g. newlines, hyphens, extra spaces in the PDF layer that don't match our text)

            const keywords: string[] = [];

            // Always add the full sentence first (if it works, it looks best)
            // keywords.push(cleanText); // Optional: disable full sentence if it causes issues, but usually fine

            const words = cleanText.split(' ');

            if (words.length > 10) {
                // Use 8-word chunks with 4-word overlap
                // Longer chunks (8 words) are much more unique and prevent "painting the whole page"
                for (let i = 0; i < words.length - 7; i += 4) {
                    const chunk = words.slice(i, i + 8).join(' ');
                    // Filter out short chunks
                    if (chunk.length > 30) {
                        keywords.push(chunk);
                    }
                }
            } else {
                keywords.push(cleanText);
            }

            setSearchKeywords(keywords);
        } else {
            setSearchKeywords([]);
        }
    }, [highlightText]);

    // Search plugin with keyword that automatically highlights
    const searchPluginInstance = searchPlugin({
        keyword: searchKeywords,
        onHighlightKeyword: (props) => {
            // Keyword highlighted successfully
        },
    });

    const { jumpToMatch, setTargetPages, highlight: searchHighlight } = searchPluginInstance;

    // Highlight plugin for visual styling
    const highlightPluginInstance = highlightPlugin({
        trigger: Trigger.None, // We'll use search plugin for highlighting
    });

    // Default layout plugin
    const defaultLayoutPluginInstance = defaultLayoutPlugin();

    // Jump to first match when keyword is set and document is loaded
    useEffect(() => {
        if (searchKeywords.length > 0 && !isLoading && jumpToMatch) {
            setTimeout(() => {
                // Jump to first match (index 0)
                jumpToMatch(0);
            }, 1000);
        }
    }, [searchKeywords, isLoading, jumpToMatch]);

    // Auto-hide loading spinner after 10 seconds
    useEffect(() => {
        if (isLoading) {
            const timeout = setTimeout(() => {
                console.warn("PDF loading timeout - hiding spinner");
                setIsLoading(false);
            }, 10000);
            return () => clearTimeout(timeout);
        }
    }, [isLoading]);

    // Props validated on mount

    if (!isOpen) return null;

    return (
        <div className="h-full w-full flex flex-col bg-[#1a1a1b]">
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-white/10 bg-[#1a1a1b]">
                <div className="flex-1 min-w-0">
                    <h3 className="text-white font-medium truncate">{fileName}</h3>
                    {highlightText && (
                        <p className="text-sm text-white/60 mt-1">
                            Searching for matches...
                        </p>
                    )}
                </div>
                <button
                    onClick={onClose}
                    className="ml-4 p-2 hover:bg-white/10 rounded-lg transition-colors flex-shrink-0"
                >
                    <X className="w-5 h-5 text-white/60" />
                </button>
            </div>

            {/* PDF Viewer */}
            <div className="flex-1 relative overflow-hidden">
                {error ? (
                    <div className="absolute inset-0 flex items-center justify-center bg-[#1a1a1b]">
                        <div className="text-center p-8">
                            <p className="text-red-400 mb-4">{error}</p>
                            <button
                                onClick={() => {
                                    setError(null);
                                    setIsLoading(true);
                                }}
                                className="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white rounded-lg transition-colors"
                            >
                                Retry
                            </button>
                        </div>
                    </div>
                ) : (
                    <>
                        {isLoading && (
                            <div className="absolute inset-0 flex items-center justify-center bg-[#1a1a1b] z-10">
                                <div className="text-center">
                                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-violet-500 mx-auto mb-4"></div>
                                    <p className="text-white/60">Loading PDF...</p>
                                </div>
                            </div>
                        )}
                        <Worker workerUrl="https://unpkg.com/pdfjs-dist@3.4.120/build/pdf.worker.min.js">
                            <div className="h-full">
                                <Viewer
                                    fileUrl={fileUrl}
                                    plugins={[searchPluginInstance, highlightPluginInstance, defaultLayoutPluginInstance]}
                                    initialPage={highlightPage ? highlightPage - 1 : 0}
                                    onPageChange={(e) => setCurrentPage(e.currentPage + 1)}
                                    onDocumentLoad={() => {
                                        setIsLoading(false);
                                        setError(null);
                                    }}
                                    theme={{
                                        theme: "dark",
                                    }}
                                />
                            </div>
                        </Worker>
                    </>
                )}
            </div>

            {/* Citations Footer */}
            {citations && citations.length > 0 && (
                <div className="border-t border-white/10 p-4 bg-[#1a1a1b] max-h-32 overflow-y-auto">
                    <p className="text-sm text-white/60 mb-2">Citations on page {currentPage}:</p>
                    <div className="space-y-1">
                        {citations
                            .filter(cit => cit.page_number === currentPage)
                            .map((cit, idx) => (
                                <p key={idx} className="text-xs text-white/80">
                                    [{cit.id}] {cit.content?.substring(0, 100)}...
                                </p>
                            ))}
                    </div>
                </div>
            )}
        </div>
    );
};

export default PDFViewer;
