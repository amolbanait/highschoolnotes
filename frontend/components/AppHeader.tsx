"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth";

export function AppHeader() {
  const { user, signOut } = useAuth();
  const router = useRouter();
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur print:hidden">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
        <Link href="/" className="flex items-center gap-2 font-bold text-slate-900">
          <span
            aria-hidden
            className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white"
          >
            ✎
          </span>
          HighSchoolNotes
        </Link>
        {user && (
          <nav className="flex items-center gap-1 text-sm">
            <Link
              href="/new"
              className="rounded-lg bg-indigo-600 px-3 py-2 font-medium text-white hover:bg-indigo-700"
            >
              New guide
            </Link>
            <Link href="/account" className="rounded-lg px-3 py-2 text-slate-600 hover:bg-slate-100">
              {user.display_name}
            </Link>
            <button
              type="button"
              onClick={async () => {
                await signOut();
                router.push("/login");
              }}
              className="hidden rounded-lg px-3 py-2 text-slate-600 hover:bg-slate-100 sm:block"
            >
              Sign out
            </button>
          </nav>
        )}
      </div>
    </header>
  );
}
