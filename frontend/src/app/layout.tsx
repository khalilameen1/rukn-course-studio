import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import AuthGuard from "@/components/AuthGuard";
import AppShell from "@/components/ui/AppShell";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Rukn Course Studio",
  description: "Internal tool for generating Rukn practical-skill courses as DOCX.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full font-sans antialiased">
        <AppShell>
          <AuthGuard>{children}</AuthGuard>
        </AppShell>
      </body>
    </html>
  );
}
