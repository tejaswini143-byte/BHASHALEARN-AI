export type Mission = {
  id: string;
  title: string;
  subject: string;
  description: string;
  objective: string;
  progress: number;
  target: number;
  xp_reward: number;
  completed: boolean;
  eligible: boolean;
  completed_at: string | null;
  daily: boolean;
  active_date: string | null;
};

export type MissionOverview = {
  missions: Mission[];
  xp: number;
  level: number;
  xp_into_level: number;
  xp_to_next_level: number;
  badges: string[];
};

export function progressPercent(mission: Pick<Mission, "progress" | "target">): number {
  if (mission.target <= 0) return 0;
  return Math.min(100, Math.max(0, Math.round((mission.progress / mission.target) * 100)));
}

export function missionState(mission: Mission): "claimed" | "ready" | "in-progress" {
  if (mission.completed) return "claimed";
  if (mission.eligible || mission.progress >= mission.target) return "ready";
  return "in-progress";
}
