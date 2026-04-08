"use client";

import { useState, useEffect } from "react";
import dynamic from "next/dynamic";

// This wrapper ensures PDFViewer never loads during SSR
// Use a more aggressive client-only loading strategy
const PDFViewer = dynamic(
    () => {
        // Double-check we're in browser before importing
        if (typeof window === "undefined") {
            return Promise.resolve({ default: () => null });
        }
        return import("./PDFViewer");  // Use default export
    },
    {
        ssr: false,
        loading: () => (
            <div className="flex items-center justify-center h-full">
                <div className="text-white/50">Loading PDF viewer...</div>
            </div>
        ),
    }
);

interface PDFViewerWrapperProps {
    isOpen: boolean;
    onClose: () => void;
    fileUrl: string;
    fileName: string;
    highlightPage?: number;
    highlightText?: string;
    citations?: Array<{
        page_number?: number;
        content?: string;
    }>;
}

export function PDFViewerWrapper(props: PDFViewerWrapperProps) {
    const [isMounted, setIsMounted] = useState(false);

    useEffect(() => {
        setIsMounted(true);
    }, []);

    if (!isMounted) {
        return null;
    }

    return <PDFViewer {...props} citations={props.citations || []} />;
}

