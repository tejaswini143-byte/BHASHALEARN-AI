import type { Mission } from "./missionModel";
import { missionState, progressPercent } from "./missionModel";

export function MissionCard({ mission, claiming, onClaim }: {
  mission: Mission;
  claiming: boolean;
  onClaim: (missionId: string) => void;
}) {
  const state = missionState(mission);
  const percent = progressPercent(mission);
  return <article className={`mission-card ${mission.daily ? "mission-daily" : ""}`} aria-labelledby={`mission-${mission.id}`}>
    <div className="mission-card-top"><span className="mission-subject">{mission.subject}</span><span className="mission-state">{state === "claimed" ? "Reward claimed" : state === "ready" ? "Ready to claim" : mission.daily ? "Daily challenge" : "In progress"}</span></div>
    <h2 id={`mission-${mission.id}`}>{mission.title}</h2>
    <p>{mission.description}</p>
    <div className="mission-objective"><span>OBJECTIVE</span><strong>{mission.objective}</strong></div>
    <div className="mission-progress-label"><span>Progress</span><strong>{mission.progress} / {mission.target}</strong></div>
    <div className="mission-progress-track" role="progressbar" aria-label={`${mission.title} progress`} aria-valuemin={0} aria-valuemax={mission.target} aria-valuenow={mission.progress}>
      <div style={{ width: `${percent}%` }} />
    </div>
    <div className="mission-card-bottom"><span className="mission-xp">✦ {mission.xp_reward} XP</span>
      {state === "ready" ? <button type="button" disabled={claiming} onClick={() => onClaim(mission.id)}>{claiming ? "Claiming…" : "Claim reward"}</button>
        : state === "claimed" ? <span className="mission-claimed" aria-label="Mission reward claimed">✓ Claimed</span>
          : <span className="mission-locked">Keep learning</span>}
    </div>
  </article>;
}
