export const days = [
  "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun",
];

export const courses = [
  {
    id: "aws",
    provider: "AWS",
    name: "AWS Solutions Architect Associate",
    initial: 16,
    lessons: [
      "Cloud basics",
      "AWS regions",
      "Availability zones",
      "Shared responsibility",
      "IAM users",
      "IAM roles",
      "IAM policies",
      "S3 buckets",
      "S3 storage classes",
      "S3 lifecycle",
      "EC2 instances",
      "EBS volumes",
      "Snapshots",
      "Load balancing",
      "Auto Scaling",
      "CloudWatch",
      "VPC fundamentals",
      "Subnets & routing",
      "Security groups",
      "Network ACLs",
      "Route 53",
      "CloudFront",
      "Multi-AZ databases",
      "Disaster recovery",
      "Architecture review",
    ],
  },
  {
    id: "azure",
    provider: "Azure",
    name: "Azure Fundamentals",
    initial: 3,
    lessons: [
      "Cloud concepts",
      "Shared responsibility",
      "Cloud benefits",
      "Core Azure services",
      "Regions",
      "Resource groups",
      "Compute",
      "Storage",
      "Virtual networks",
      "Identity",
      "Governance",
      "Monitoring",
      "Costs",
      "Support",
      "Final review",
    ],
  },
  {
    id: "pm",
    provider: "Project management",
    name: "Project Management Fundamentals",
    initial: 0,
    lessons: [
      "Project life cycles",
      "Stakeholders",
      "Project charter",
      "Scope",
      "Work breakdown",
      "Schedules",
      "Budgets",
      "Risks",
      "Communication",
      "Quality",
      "Change control",
      "Project closure",
    ],
  },
];

export const awards = [
  {
    name: "Cloud Foundations",
    date: "October 28, 2026",
    count: 8,
    minutes: 250,
    award: "Cloud Explorer",
  },
  {
    name: "Introduction to Networking",
    date: "November 6, 2026",
    count: 6,
    minutes: 195,
    award: "Networking Starter",
  },
];

export const schedule = [
  { day: 0, title: "IAM fundamentals", minutes: 25 },
  { day: 0, title: "Storage essentials", minutes: 20 },
  { day: 1, title: "VPC fundamentals", minutes: 25 },
  { day: 2, title: "Subnets & routing", minutes: 25 },
  { day: 4, title: "Networking practice", minutes: 30 },
];

export function duration(minutes: number) {
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;

  return [
    hours ? `${hours}h` : "",
    remainingMinutes ? `${remainingMinutes}m` : "",
  ]
    .filter(Boolean)
    .join(" ") || "0m";
}