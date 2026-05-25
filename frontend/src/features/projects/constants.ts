/**
 * Project category mirror — still used by the create-project form and the
 * brief tab to populate the category select.
 *
 * Categories are Content-Creation-specific (Sons Real Estate's video
 * production buckets). They survive Phase E because the underlying
 * `projects.category` Postgres enum hasn't moved; broadening category to
 * be department-defined is a future capability concern, not Phase E scope.
 */

export const CATEGORIES = [
  "property_tour",
  "agent_intro",
  "neighbourhood",
  "testimonial",
  "other",
] as const;
export type Category = (typeof CATEGORIES)[number];
