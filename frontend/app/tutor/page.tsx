import TutorChat from "@/components/chat/TutorChat";

export const metadata = {
  title: "AI Tutor | Edgely",
  description: "Ask your AI tutor about your certification study material.",
};

export default function TutorPage() {
  return (
    <main className="tutor-page">
      <TutorChat />
    </main>
  );
}
