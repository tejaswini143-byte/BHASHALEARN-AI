import type {DashboardData,LearningProgress} from "./contracts";
export function buildTimeline(data:DashboardData){
 const all=[
 ...data.sessions.map(s=>({id:"s"+s.id,title:s.topic,detail:"Learning session started",at:s.created_at})),
 ...data.progress.map((p:LearningProgress)=>({id:"p"+p.id,title:p.topic,detail:p.evidence_attempts+" assessed attempts recorded",at:p.updated_at})),
 ...(data.missions?.missions??[]).filter(m=>m.completed_at).map(m=>({id:"m"+m.id,title:m.title,detail:"Mission reward claimed",at:m.completed_at as string}))
 ];
 return all.filter(e=>Number.isFinite(Date.parse(e.at))).sort((a,b)=>Date.parse(b.at)-Date.parse(a.at)).slice(0,8);
}
export function recommendNextStep(data:DashboardData){
 const p=data.progress.find(x=>x.recommendation.trim());
 if(p)return {title:p.recommendation,detail:"Based on your recorded progress in "+p.topic+".",href:"/classroom"};
 const s=[...data.sessions].sort((a,b)=>Date.parse(b.created_at)-Date.parse(a.created_at))[0];
 if(s)return {title:"Continue "+s.topic,detail:"Pick up your most recent learning session.",href:"/classroom?session="+encodeURIComponent(s.id)};
 if(data.preferences.learning_goal?.trim())return {title:"Start with your goal: "+data.preferences.learning_goal.trim(),detail:"Your saved learning goal is ready.",href:"/classroom"};
 return {title:"Start a learning session",detail:"Choose a topic to explore.",href:"/classroom"};
}
export function averageMastery(items:LearningProgress[]){const a=items.filter(x=>x.evidence_attempts>0&&Number.isFinite(x.mastery_score));return a.length?a.reduce((s,x)=>s+x.mastery_score,0)/a.length:null;}
