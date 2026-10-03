import { GuideScreen } from "./GuideScreen";

export default async function GuidePage({ params }: PageProps<"/guides/[id]">) {
  const { id } = await params;
  return <GuideScreen id={id} />;
}
