/**
 * Stage registry, keyed by department template.
 *
 * Mirrors `app/seeds/templates/<key>.py::STAGES` on the backend. When you
 * add a stage there, add it here too — same trade-off as
 * `features/departments/lib/permissionActionsByTemplate.ts`. The DB used to
 * carry these rows; the editor was removed 2026-05-26 because adding a row
 * didn't auto-wire permissions or downstream code.
 */

export interface StageSpec {
  key: string;
  name_i18n: Record<string, string>;
  color: string | null;
  is_terminal: boolean;
  /** Stage keys that can move *into* this stage. Empty for entry stages. */
  allowed_from_stage_keys: string[];
}

const CONTENT_CREATION_STAGES: StageSpec[] = [
  {
    key: "idea",
    name_i18n: { nl: "Idee", en: "Idea" },
    color: "#94a3b8",
    is_terminal: false,
    allowed_from_stage_keys: [],
  },
  {
    key: "script_drafting",
    name_i18n: { nl: "Script schrijven", en: "Script drafting" },
    color: "#60a5fa",
    is_terminal: false,
    allowed_from_stage_keys: ["idea"],
  },
  {
    key: "script_review",
    name_i18n: { nl: "Script review", en: "Script review" },
    color: "#38bdf8",
    is_terminal: false,
    allowed_from_stage_keys: ["script_drafting", "script_locked"],
  },
  {
    key: "script_locked",
    name_i18n: { nl: "Script vergrendeld", en: "Script locked" },
    color: "#0ea5e9",
    is_terminal: false,
    allowed_from_stage_keys: ["script_drafting", "script_review"],
  },
  {
    key: "location_scouting",
    name_i18n: { nl: "Locatie scouten", en: "Location scouting" },
    color: "#fbbf24",
    is_terminal: false,
    allowed_from_stage_keys: [
      "idea",
      "script_drafting",
      "script_review",
      "script_locked",
    ],
  },
  {
    key: "casting",
    name_i18n: { nl: "Casting", en: "Casting" },
    color: "#f59e0b",
    is_terminal: false,
    allowed_from_stage_keys: ["location_scouting"],
  },
  {
    key: "shoot_scheduled",
    name_i18n: { nl: "Opname gepland", en: "Shoot scheduled" },
    color: "#fb7185",
    is_terminal: false,
    allowed_from_stage_keys: ["casting"],
  },
  {
    key: "shoot_done",
    name_i18n: { nl: "Opname klaar", en: "Shoot done" },
    color: "#f43f5e",
    is_terminal: false,
    allowed_from_stage_keys: ["shoot_scheduled"],
  },
  {
    key: "editing",
    name_i18n: { nl: "Montage", en: "Editing" },
    color: "#a78bfa",
    is_terminal: false,
    allowed_from_stage_keys: ["shoot_done", "final_review"],
  },
  {
    key: "final_review",
    name_i18n: { nl: "Eind review", en: "Final review" },
    color: "#8b5cf6",
    is_terminal: false,
    allowed_from_stage_keys: ["editing"],
  },
  {
    key: "approved_published",
    name_i18n: { nl: "Goedgekeurd & gepubliceerd", en: "Approved & published" },
    color: "#22c55e",
    is_terminal: true,
    allowed_from_stage_keys: ["final_review", "editing"],
  },
];

const MARKETING_STAGES: StageSpec[] = [
  {
    key: "lead_new",
    name_i18n: { nl: "Nieuwe lead", en: "New lead" },
    color: "#60a5fa",
    is_terminal: false,
    allowed_from_stage_keys: [],
  },
  {
    key: "qualified",
    name_i18n: { nl: "Gekwalificeerd", en: "Qualified" },
    color: "#38bdf8",
    is_terminal: false,
    allowed_from_stage_keys: ["lead_new"],
  },
  {
    key: "contacted",
    name_i18n: { nl: "Contact gemaakt", en: "Contacted" },
    color: "#fbbf24",
    is_terminal: false,
    allowed_from_stage_keys: ["qualified"],
  },
  {
    key: "meeting_scheduled",
    name_i18n: { nl: "Afspraak ingepland", en: "Meeting scheduled" },
    color: "#f59e0b",
    is_terminal: false,
    allowed_from_stage_keys: ["contacted"],
  },
  {
    key: "closed_won",
    name_i18n: { nl: "Gewonnen", en: "Closed — won" },
    color: "#22c55e",
    is_terminal: true,
    allowed_from_stage_keys: ["meeting_scheduled"],
  },
  {
    key: "closed_lost",
    name_i18n: { nl: "Verloren", en: "Closed — lost" },
    color: "#ef4444",
    is_terminal: true,
    allowed_from_stage_keys: ["qualified", "contacted", "meeting_scheduled"],
  },
];

export const STAGES_BY_TEMPLATE: Record<string, StageSpec[]> = {
  content_creation: CONTENT_CREATION_STAGES,
  marketing: MARKETING_STAGES,
};

export function getStages(templateKey: string | null | undefined): StageSpec[] {
  if (!templateKey) return [];
  return STAGES_BY_TEMPLATE[templateKey] ?? [];
}

export function getStage(
  templateKey: string | null | undefined,
  stageKey: string,
): StageSpec | undefined {
  return getStages(templateKey).find((s) => s.key === stageKey);
}

export function isKnownStage(
  templateKey: string | null | undefined,
  stageKey: string,
): boolean {
  return getStage(templateKey, stageKey) !== undefined;
}

export function localizedStageLabel(
  spec: StageSpec | undefined,
  locale: string,
  fallback: string,
): string {
  if (!spec) return fallback;
  return spec.name_i18n[locale] ?? spec.name_i18n.en ?? spec.name_i18n.nl ?? spec.key;
}
