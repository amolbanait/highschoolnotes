import { PracticeScreen } from "../PracticeScreen";

export default async function QuizPage({ params }: PageProps<"/guides/[id]/quiz">) {
  const { id } = await params;
  return <PracticeScreen id={id} mode="quiz" />;
}
