"use client";

import { useEffect } from "react";

export function ToolbarInit() {
    useEffect(() => {
        // Only initialize in development mode
        if (process.env.NODE_ENV === "development") {
            // Dynamic import to avoid including in production bundle
            import("@21st-extension/toolbar").then(({ initToolbar }) => {
                // Define your toolbar configuration
                const stagewiseConfig = {
                    plugins: [],
                };

                // Initialize the toolbar
                initToolbar(stagewiseConfig);
            }).catch((error) => {
                console.warn("Failed to initialize toolbar:", error);
            });
        }
    }, []);

    return null; // This component doesn't render anything
}

