const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export const PASSWORD_MIN_LENGTH = 8;

export function validateEmail(value: string): string | undefined {
  const email = value.trim();
  if (!email) return "Enter your email address.";
  if (!EMAIL_PATTERN.test(email)) return "Enter a valid email address.";
  return undefined;
}

// Keep these rules in sync with the backend password policy.
export function validateNewPassword(value: string): string | undefined {
  if (!value) return "Enter a password.";
  if (value.length < PASSWORD_MIN_LENGTH) {
    return `Use at least ${PASSWORD_MIN_LENGTH} characters.`;
  }
  if (!/[A-Za-z]/.test(value) || !/\d/.test(value)) {
    return "Include at least one letter and one number.";
  }
  return undefined;
}

export function validateName(value: string): string | undefined {
  if (!value.trim()) return "Enter your name.";
  return undefined;
}
