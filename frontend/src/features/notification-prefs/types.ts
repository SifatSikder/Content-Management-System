/**
 * Department-scoped notification preferences.
 *
 * Mirror of `app/schemas/notification_prefs.py`. Each `EventPref` represents
 * one event the department defines (e.g. `cut_uploaded`) with the user's
 * effective on/off (`enabled`) and the department's default for reference.
 */

export interface EventPref {
  event_key: string;
  name_i18n: Record<string, string>;
  default_enabled: boolean;
  enabled: boolean;
}

export interface DepartmentPrefs {
  department_id: string;
  events: EventPref[];
}

export interface SetEventPrefBody {
  department_id: string;
  event_key: string;
  enabled: boolean;
}
