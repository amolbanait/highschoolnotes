import { Suspense } from "react";

import { AuthForm } from "@/app/(auth)/AuthForm";

export const metadata = { title: "Sign in · HighSchoolNotes" };

export default function LoginPage() {
  return (
    <Suspense>
      <AuthForm mode="login" />
    </Suspense>
  );
}
