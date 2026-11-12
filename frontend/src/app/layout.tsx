import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { ToolbarInit } from "@/components/ToolbarInit";
import { Toaster } from "@/components/Toaster";
import { AuthProvider } from "@/context/AuthContext";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "DocuMind AI - Intelligent Document Analysis",
  description: "Intelligent document management and AI chat platform. Automatically categorize, search, and interact with your documents using advanced AI.",
  icons: {
    icon: "/favicon.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <AuthProvider>
          <ToolbarInit />
          <Toaster />
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
