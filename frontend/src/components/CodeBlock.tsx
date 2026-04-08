import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { cn } from "@/lib/utils";

const CodeBlock = ({ inline, className, children, ...props }: any) => {
    const [isCopied, setIsCopied] = useState(false);
    const match = /language-(\w+)/.exec(className || '');
    const language = match ? match[1] : '';
    const codeContent = String(children).replace(/\n$/, '');

    const copyToClipboard = () => {
        navigator.clipboard.writeText(codeContent);
        setIsCopied(true);
        setTimeout(() => setIsCopied(false), 2000);
    };

    if (inline) {
        return (
            <code className="px-1.5 py-0.5 rounded bg-white/10 text-violet-200 text-sm font-mono" {...props}>
                {children}
            </code>
        );
    }

    return (
        <div className="relative my-4 rounded-xl border border-white/10 bg-[#0d0d0d] overflow-hidden group">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-2 bg-white/[0.03] border-b border-white/5">
                <span className="text-xs font-medium text-white/50 lowercase">{language || 'code'}</span>
                <button
                    onClick={copyToClipboard}
                    className="flex items-center gap-1.5 text-xs font-medium text-white/50 hover:text-white transition-colors"
                >
                    {isCopied ? (
                        <>
                            <Check className="w-3.5 h-3.5 text-green-400" />
                            <span className="text-green-400">Copied!</span>
                        </>
                    ) : (
                        <>
                            <Copy className="w-3.5 h-3.5" />
                            <span>Copy</span>
                        </>
                    )}
                </button>
            </div>
            {/* Code */}
            <div className="p-4 overflow-x-auto">
                <code className={cn("text-sm font-mono leading-relaxed text-white/90", className)} {...props}>
                    {children}
                </code>
            </div>
        </div>
    );
};

export default CodeBlock;
