"use client";

import { useEffect, useRef, useCallback } from "react";
import { useState } from "react";
import { cn } from "@/lib/utils";
import {
    SendIcon,
    Paperclip,
    LoaderIcon,
} from "lucide-react";
import { motion } from "framer-motion";
import * as React from "react";

interface UseAutoResizeTextareaProps {
    minHeight: number;
    maxHeight?: number;
}

function useAutoResizeTextarea({
    minHeight,
    maxHeight,
}: UseAutoResizeTextareaProps) {
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const adjustHeight = useCallback(
        (reset?: boolean) => {
            const textarea = textareaRef.current;
            if (!textarea) return;

            if (reset) {
                textarea.style.height = `${minHeight}px`;
                return;
            }

            textarea.style.height = `${minHeight}px`;
            const newHeight = Math.max(
                minHeight,
                Math.min(
                    textarea.scrollHeight,
                    maxHeight ?? Number.POSITIVE_INFINITY
                )
            );

            textarea.style.height = `${newHeight}px`;
        },
        [minHeight, maxHeight]
    );

    useEffect(() => {
        const textarea = textareaRef.current;
        if (textarea) {
            textarea.style.height = `${minHeight}px`;
        }
    }, [minHeight]);

    return { textareaRef, adjustHeight };
}

interface AnimatedChatInputProps {
    value: string;
    onChange: (value: string) => void;
    onSend: () => void;
    onFileUpload?: (file: File) => void;
    isLoading?: boolean;
    placeholder?: string;
}

export function AnimatedChatInput({
    value,
    onChange,
    onSend,
    onFileUpload,
    isLoading = false,
    placeholder = "What do you want to know?"
}: AnimatedChatInputProps) {
    const [inputFocused, setInputFocused] = useState(false);
    const { textareaRef, adjustHeight } = useAutoResizeTextarea({
        minHeight: 48,
        maxHeight: 200,
    });

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            if (value.trim() && !isLoading) {
                onSend();
            }
        }
    };

    return (
        <motion.div
            className={cn(
                "relative backdrop-blur-xl bg-[#1a1a1a] rounded-[2.5rem] border shadow-2xl overflow-hidden transition-all duration-200",
                inputFocused ? "border-white/20" : "border-white/10"
            )}
            initial={{ scale: 0.98 }}
            animate={{ scale: 1 }}
        >
            <div className="flex items-center gap-3 px-5 py-3">
                {/* Document Upload Button */}
                <motion.label
                    htmlFor="file-upload"
                    whileTap={{ scale: 0.94 }}
                    className="p-2 text-white/50 hover:text-white/90 rounded-full transition-colors flex-shrink-0 cursor-pointer"
                >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                    </svg>
                    <input
                        id="file-upload"
                        type="file"
                        accept=".pdf,.docx,.doc"
                        onChange={(e) => {
                            const file = e.target.files?.[0];
                            if (file && onFileUpload) {
                                onFileUpload(file);
                            }
                            e.target.value = ''; // Reset input
                        }}
                        className="hidden"
                    />
                </motion.label>

                {/* Input Field */}
                <textarea
                    ref={textareaRef}
                    value={value}
                    onChange={(e) => {
                        onChange(e.target.value);
                        adjustHeight();
                    }}
                    onKeyDown={handleKeyDown}
                    onFocus={() => setInputFocused(true)}
                    onBlur={() => setInputFocused(false)}
                    placeholder={placeholder}
                    className="flex-1 resize-none bg-transparent border-none text-white/90 text-[15px] focus:outline-none placeholder:text-white/40 min-h-[48px] py-3"
                    style={{ overflow: "hidden" }}
                />

                {/* Right Side Controls */}
                <div className="flex items-center gap-2 flex-shrink-0">
                    {/* File Upload */}
                    <input
                        type="file"
                        id="file-upload"
                        className="hidden"
                        accept=".pdf,.docx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown"
                        onChange={(e) => {
                            const file = e.target.files?.[0];
                            if (file) {
                                const allowedExtensions = ['.pdf', '.docx', '.txt', '.md'];
                                const fileName = file.name.toLowerCase();
                                const isValid = allowedExtensions.some(ext => fileName.endsWith(ext));

                                if (!isValid) {
                                    alert(`Invalid file type. Please upload only PDF, DOCX, TXT, or MD files.`);
                                    e.target.value = '';
                                    return;
                                }

                                if (onFileUpload) {
                                    onFileUpload(file);
                                }
                            }
                            e.target.value = '';
                        }}
                    />

                    {/* Auto Mode Selector */}
                    <div className="flex items-center gap-1.5 px-3 py-1.5 bg-white/5 hover:bg-white/10 rounded-full transition-colors cursor-pointer">
                        <svg className="w-3.5 h-3.5 text-white/70" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                        <span className="text-xs text-white/70 font-medium">Auto</span>
                        <svg className="w-3 h-3 text-white/50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                    </div>

                    {/* Voice/Audio Button */}
                    <motion.button
                        type="button"
                        onClick={onSend}
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        disabled={isLoading}
                        className="p-2.5 bg-white rounded-full hover:bg-white/90 transition-colors flex-shrink-0"
                    >
                        {isLoading ? (
                            <LoaderIcon className="w-4 h-4 text-black animate-spin" />
                        ) : (
                            <svg className="w-4 h-4 text-black" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                            </svg>
                        )}
                    </motion.button>
                </div>
            </div>
        </motion.div>
    );
}

export function TypingIndicator() {
    return (
        <motion.div
            className="flex items-center gap-1.5 px-4 py-3 max-w-fit"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
        >
            {[1, 2, 3].map((dot) => (
                <motion.div
                    key={dot}
                    className="w-2 h-2 bg-white/60 rounded-full"
                    animate={{
                        opacity: [0.3, 0.9, 0.3],
                        scale: [0.85, 1.15, 0.85]
                    }}
                    transition={{
                        duration: 1.2,
                        repeat: Infinity,
                        delay: dot * 0.15,
                    }}
                />
            ))}
        </motion.div>
    );
}
