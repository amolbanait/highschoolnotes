import { Suspense } from "react";

import { AuthForm } from "@/app/(auth)/AuthForm";

export const metadata = { title: "Create account · HighSchoolNotes" };

export default function SignupPage() {
  return (
    <Suspense>
      <AuthForm mode="signup" />
    </Suspense>
  );
}
