import type {Student} from "../auth";
export type LearningProgress={id:string;topic:string;mastery_score:number;attempts:number;evidence_attempts:number;evidence_status:string;correct_attempts:number;incorrect_attempts:number;recommendation:string;updated_at:string};
export type LearningSession={id:string;topic:string;language:string;created_at:string;course_id?:string|null};
export type LearningPreferences={preferred_language:string;learning_level:string;learning_goal:string|null};
export type MissionOverview={missions:{id:string;title:string;completed_at:string|null}[];xp:number;level:number;xp_into_level:number;xp_to_next_level:number;badges:string[]};
export type CourseSummary={id:string;title:string;language:string};
export type DashboardData={course:CourseSummary|null;student:Student;progress:LearningProgress[];sessions:LearningSession[];preferences:LearningPreferences;missions:MissionOverview|null};
export type DashboardIntegrations={adaptiveQuizzes?:{href:string};analytics?:{href:string};teachingIntelligence?:{href:string};personalAssistant?:{href:string;reminders?:{id:string;title:string;dueAt:string}[]};holographicTeacher?:{href:string};multilingualVoice?:{href:string};careerRoadmap?:{href:string;nextMilestone?:string}};
export const EMPTY_INTEGRATIONS:DashboardIntegrations={};
