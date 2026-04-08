import React from "react";

export const GrokLogo = ({ className = "w-8 h-8", size = 32 }: { className?: string; size?: number }) => {
    return (
        <div className={`relative flex items-center justify-center ${className}`}>
            {/* Circle with slash - approximate Grok logo style */}
            <svg
                width={size}
                height={size}
                viewBox="0 0 24 24"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
                className="text-white"
            >
                <path
                    d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2ZM10.5 17L7 12L10.5 7L12 9.1L9.9 12L12 14.9L10.5 17ZM17 12L13.5 17L12 14.9L14.1 12L12 9.1L13.5 7L17 12Z"
                    fill="currentColor"
                />
                {/* Simplified abstract 'G' or slash shape if the above is too generic.
            Actually, the Grok logo is often a stylized square or slash. 
            Let's stick to a clean geometric shape for now.
         */}
                <path d="M4 20L20 4" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
                <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2" />
            </svg>
        </div>
    );
};

export const GrokTextLogo = ({ className }: { className?: string }) => (
    <svg width="67" height="24" viewBox="0 0 67 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
        <path d="M12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2C14.707 2 17.1537 3.07604 18.956 4.82869L16.208 7.64993C15.1187 6.64333 13.642 6.02703 12 6.02703C8.75165 6.02703 6.09638 8.64166 6.09638 11.9459C6.09638 15.2502 8.75165 17.8649 12 17.8649C14.1953 17.8649 16.1437 16.7459 17.158 15.027H11.729V11.4595H21.2323C21.4053 12.062 21.4963 12.7032 21.4963 13.3649C21.4963 18.1333 17.5927 22 12 22Z" fill="white" />
        <path d="M28.0253 21.4595H24.161V6.54053H28.0253V21.4595Z" fill="white" />
        <path d="M37.8105 21.8919C35.5393 21.8919 33.7225 20.1042 33.7225 17.8919C33.7225 15.6796 35.5393 13.8919 37.8105 13.8919C40.0817 13.8919 41.8985 15.6796 41.8985 17.8919C41.8985 20.1042 40.0817 21.8919 37.8105 21.8919ZM37.8105 10.973C34.0227 10.973 30.7307 14.0765 30.7307 17.8919C30.7307 21.7073 34.0227 24.8108 37.8105 24.8108C41.5982 24.8108 44.8902 21.7073 44.8902 17.8919C44.8902 14.0765 41.5982 10.973 37.8105 10.973Z" fill="white" />
        <path d="M52.0913 14.3642C51.272 14.0628 50.413 13.8919 49.5312 13.8919C47.2882 13.8919 45.4225 15.5413 45.161 17.7562V21.4595H41.3408V6.54053H45.161V11.2338C46.12 9.87702 47.7475 9.08107 49.5312 9.08107C50.2735 9.08107 51.012 9.18667 51.6963 9.38287L52.0913 14.3642Z" fill="white" />
        <path d="M60.8988 15.5392L63.882 11.4595H59.2635L57.5348 13.8162L55.806 11.4595H51.1875L54.1708 15.5392L50.8647 21.4595H55.4523L57.5348 17.6534L59.6172 21.4595H64.2048L60.8988 15.5392Z" fill="white" />
    </svg>
)
