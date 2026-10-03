import "katex/dist/katex.min.css";
import "./globals.css";

import type { Metadata } from "next";

import { AppHeader } from "@/components/AppHeader";
import { AuthProvider } from "@/components/auth";

export const metadata: Metadata = {
  title: "HighSchoolNotes",
  description: "Turn your class material into a clear study guide, practice questions and flashcards.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex min-h-full flex-col">
        <AuthProvider>
          <AppHeader />
          <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}
