// Shapes returned by the platform API. Field names match docs/api/m1-contract.md.

export type EnrollmentStatus = "active" | "paused" | "completed" | "abandoned";

export type Certification = {
  id: number;
  name: string;
  slug: string;
  description: string | null;
};

export type Enrollment = {
  id: number;
  certification_id: number;
  certification_name: string;
  certification_slug: string;
  status: EnrollmentStatus;
  goal: string | null;
  deadline: string | null; // YYYY-MM-DD
  weekly_study_hours: number | null;
  created_at: string;
};

export type EnrollmentCreate = {
  certification_id: number;
  goal?: string | null;
  deadline?: string | null;
  weekly_study_hours?: number | null;
};

export type EnrollmentUpdate = {
  status?: EnrollmentStatus;
  goal?: string | null;
  deadline?: string | null;
  weekly_study_hours?: number | null;
};

export type PlatformUser = {
  id: number;
  external_auth_id: string;
  display_name: string;
  email: string;
  role: string;
  created_at: string | null;
  target_certification_id: number | null;
  exam_date: string | null;
  weekly_study_hours: number | null;
  experience_level: "beginner" | "intermediate" | "advanced" | null;
};

export type UserUpdate = {
  display_name?: string;
  exam_date?: string | null;
  weekly_study_hours?: number | null;
  experience_level?: PlatformUser["experience_level"];
};

// GET /tutor/me/context: what the tutor knows about the learner.
export type LearnerContext = {
  user_id: number;
  display_name: string;
  experience_level: string | null;
  exam_date: string | null;
  target_certification_id: number | null;
  goals: Record<string, unknown>;
  enrollments: { certification_id: number; name: string; goal: string | null; deadline: string | null }[];
  domain_progress: { name: string; certification_id: number; mastery_score: number }[];
};
