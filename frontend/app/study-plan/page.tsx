import { redirect } from "next/navigation";

export default function StudyPlanPage() {
  redirect("/my-learning?tab=plan");
}