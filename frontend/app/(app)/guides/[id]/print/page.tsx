import { PrintScreen } from "./PrintScreen";

export default async function PrintPage({ params }: PageProps<"/guides/[id]/print">) {
  const { id } = await params;
  return <PrintScreen id={id} />;
}
