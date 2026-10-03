import { RequireAuth } from "@/components/auth";

export default function SignedInLayout({ children }: { children: React.ReactNode }) {
  return <RequireAuth>{children}</RequireAuth>;
}
