import {Link} from "react-router-dom";
import type {DashboardIntegrations} from "./contracts";
const items=[
 {name:"Immersive AI classroom",detail:"Explore spatial lessons",path:"/immersive",icon:"◈"},
 {name:"Voice learning",detail:"Practice aloud",path:"/voice",icon:"◉"},
 {name:"Visual lessons",detail:"Learn with diagrams",path:"/visual",icon:"◇"},
 {name:"Adaptive quizzes",detail:"Practice and assess",path:"/classroom",icon:"✓"},
 {name:"Progress analytics",detail:"Review your mastery",path:"#mastery",icon:"◒"},
 {name:"Mission Mode",detail:"Challenges and XP",path:"/missions",icon:"✦"},
 {name:"Future Me simulator",detail:"Try career scenarios",path:"/future-me",icon:"◎"},
 {name:"Career roadmap",detail:"Preview and planning",path:"/future-me",icon:"↗"},
 {name:"AI personal assistant",detail:"Coming soon",path:"",icon:"✧"},
 {name:"Learning documents",detail:"Your uploaded materials",path:"/documents",icon:"▤"}
];
export function FeatureNavigation({integrations={},compact=false}:{integrations?:DashboardIntegrations;compact?:boolean}){
 const optional:Record<string,{href:string}|undefined>={"Adaptive quizzes":integrations.adaptiveQuizzes,"Progress analytics":integrations.analytics,"Immersive AI classroom":integrations.holographicTeacher,"Voice learning":integrations.multilingualVoice,"Career roadmap":integrations.careerRoadmap};
 return <section className={"cc-feature-nav"+(compact?" compact":"")} id={compact?undefined:"features"} aria-label="Learning feature navigation">{!compact&&<h2>Learning tools</h2>}<div className="cc-feature-grid">{items.map(item=>{const adapter=optional[item.name];const href=adapter?.href||item.path;const unavailable=item.name==="AI personal assistant"&&!integrations.personalAssistant;const body=<><span aria-hidden="true">{item.icon}</span><strong>{item.name}</strong><small>{unavailable?"Coming soon":item.detail}</small></>;return unavailable?<div className="cc-feature disabled" key={item.name} aria-label={item.name+", coming soon"}>{body}</div>:href.startsWith("#")?<a className="cc-feature" key={item.name} href={href}>{body}</a>:<Link className="cc-feature" key={item.name} to={href}>{body}</Link>;})}</div></section>;
}
