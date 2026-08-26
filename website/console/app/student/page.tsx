import { redirect } from "next/navigation"
import { ENABLE_STUDENT_HUB } from "@/lib/ceaser"
import { StudentPage } from "@/components/ceaser/pages/student-page"

export default function StudentRoute() {
  if (!ENABLE_STUDENT_HUB) {
    redirect("/?view=chat")
  }

  return <StudentPage />
}
