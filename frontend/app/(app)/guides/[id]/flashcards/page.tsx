import { PracticeScreen } from "../PracticeScreen";

export default async function FlashcardsPage({ params }: PageProps<"/guides/[id]/flashcards">) {
  const { id } = await params;
  return <PracticeScreen id={id} mode="flashcards" />;
}
