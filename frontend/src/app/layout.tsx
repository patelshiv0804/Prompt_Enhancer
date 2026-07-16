import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Prompt Enhancer — Write Better Prompts, Get Better Answers",
  description:
    "Prompt Enhancer helps you write better prompts so AI can give you better answers. Optimize for ChatGPT, Claude, Gemini, Midjourney, and more.",
  keywords: [
    "prompt engineering",
    "AI prompts",
    "ChatGPT",
    "Claude",
    "prompt optimizer",
  ],
  openGraph: {
    title: "Prompt Enhancer — Write Better Prompts, Get Better Answers",
    description:
      "Prompt Enhancer helps you write better prompts so AI can give you better answers.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`} data-scroll-behavior="smooth">
      <body className="min-h-full flex flex-col bg-white text-foreground">
        {children}
      </body>
    </html>
  );
}
