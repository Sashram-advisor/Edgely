export type LoginPayload = {
  email: string;
  password: string;
};

export type RegisterPayload = {
  full_name: string;
  email: string;
  password: string;
};

export type ForgotPasswordPayload = {
  email: string;
};

export type ResetPasswordPayload = {
  token: string;
  password: string;
};

export type MessageResponse = {
  message: string;
};

// The platform user as returned by the backend's UserRead schema (POST/GET /users/me).
// Only the fields the frontend actually relies on are typed; extra fields are allowed.
export type UserProfile = {
  id: number;
  display_name: string | null;
  email: string | null;
  role: string;
  target_certification_id: number | null;
  exam_date: string | null;
  weekly_study_hours: number | null;
  experience_level: string | null;
  [key: string]: unknown;
};
