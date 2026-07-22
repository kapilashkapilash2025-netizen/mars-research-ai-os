import type { Metadata } from "next";
import { Geist_Mono, Space_Grotesk } from "next/font/google";
import "./globals.css";
import "./typography.css";

const spaceGrotesk = Space_Grotesk({
  variable: "--font-space-grotesk",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Areograph Labs — Verifiable Mission Twin",
  description: "Deterministic, explainable, and replayable Mars mission research simulation.",
  openGraph: {
    title: "Areograph Verifiable Mission Twin",
    description: "Evidence first. Decisions replayable.",
    images: [{ url: "/og-v7.png", width: 1792, height: 1024 }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Areograph Verifiable Mission Twin",
    description: "Evidence first. Decisions replayable.",
    images: ["/og-v7.png"],
  },
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
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
        className={`${spaceGrotesk.variable} ${geistMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
