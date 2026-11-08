import {test,expect,type Page} from "@playwright/test";
const student={id:"student-fixture",email:"fixture@example.test",display_name:"Ari Learner"};
const emptyData={
 "/progress":[],
 "/sessions":[],
 "/students/me/preferences":{preferred_language:"mixed",learning_level:"beginner",learning_goal:null},
 "/missions":{missions:[],xp:0,level:1,xp_into_level:0,xp_to_next_level:100,badges:[]},
 "/documents":[],"/courses/c1":{id:"c1",title:"Mathematics",language:"english"}
};
const activityData={
 "/progress":[{id:"p1",topic:"Fractions",mastery_score:72,attempts:2,evidence_attempts:2,evidence_status:"assessed",correct_attempts:1,incorrect_attempts:1,recommendation:"Practice equivalent fractions",updated_at:"2026-11-08T08:00:00Z"}],
 "/sessions":[{id:"s1",topic:"Fractions",language:"english",course_id:"c1",created_at:"2026-11-08T09:00:00Z"},{id:"s0",topic:"Greetings",language:"mixed",created_at:"2026-11-07T09:00:00Z"}],
 "/students/me/preferences":{preferred_language:"mixed",learning_level:"beginner",learning_goal:"Speak with confidence"},
 "/missions":{missions:[{id:"m1",title:"First Steps",completed_at:"2026-11-08T10:00:00Z"}],xp:25,level:1,xp_into_level:25,xp_to_next_level:75,badges:["First Steps"]},
 "/documents":[],"/courses/c1":{id:"c1",title:"Mathematics",language:"english"}
};
async function openDashboard(page:Page,activity=false,missionUnavailable=false){
 await page.addInitScript(()=>sessionStorage.setItem("bhashalearn_access_token","fixture-token"));
 const data=activity?activityData:emptyData;
 await page.route("**/api/v1/**",async route=>{
  const url=new URL(route.request().url()),key=url.pathname.replace("/api/v1","");
  if(key==="/auth/me")return route.fulfill({status:200,contentType:"application/json",body:JSON.stringify(student)});
  if(key==="/missions"&&missionUnavailable)return route.fulfill({status:503,contentType:"application/json",body:JSON.stringify({detail:"Unavailable"})});
  const value=data[key];
  return route.fulfill({status:200,contentType:"application/json",body:JSON.stringify(value??{})});
 });
 await page.goto("/dashboard");
}
test("dashboard route redirects when unauthenticated",async({page})=>{await page.goto("/dashboard");await expect(page).toHaveURL(/\/login$/);});
test("renders empty student data and unavailable features safely",async({page})=>{
 await openDashboard(page,false,true);
 await expect(page.getByRole("heading",{name:/good to see you, ari/i})).toBeVisible();
 await expect(page.getByText("Your learning activity will appear here when recorded.")).toBeVisible();
 await expect(page.getByLabel("AI personal assistant, coming soon").first()).toBeVisible();
 await expect(page.getByText("Streak tracking unavailable")).toBeVisible();
 await expect(page.getByText("Unavailable",{exact:true})).toBeVisible();
});
test("personalizes the next step and sorts only recorded timeline events",async({page})=>{
 await openDashboard(page,true);
 await expect(page.getByRole("heading",{name:"Practice equivalent fractions"})).toBeVisible();
 await expect(page.getByText("Course: Mathematics")).toBeVisible();
 await expect(page.getByRole("heading",{name:"Fractions",exact:true}).first()).toBeVisible();
 const events=page.locator("#timeline li");
 await expect(events).toHaveCount(4);
 await expect(events.nth(0)).toContainText("First Steps");
 await expect(events.nth(1)).toContainText("Fractions");
 await expect(page.getByText("Mission Mode XP")).toBeVisible();
});
test("feature navigation resolves to registered routes",async({page})=>{
 await openDashboard(page);
 const routes=[["Immersive AI classroom","/immersive"],["Voice learning","/voice"],["Visual lessons","/visual"],["Adaptive quizzes","/classroom"],["Mission Mode","/missions"],["Future Me simulator","/future-me"],["Career roadmap","/future-me"],["Learning documents","/documents"]];
 for(const [name,path] of routes){
  const link=page.getByRole("link",{name:new RegExp(name)}).last();
  await expect(link).toHaveAttribute("href",path);
  await link.click();
  await expect(page).toHaveURL(new RegExp(path.replace("/","\\/")+"(?:$|[?#])"));
  await page.goto("/dashboard");
  await expect(page.getByRole("heading",{name:/good to see you, ari/i})).toBeVisible();
 }
});
test("mobile layout and reduced motion remain usable",async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.emulateMedia({reducedMotion:"reduce"});await openDashboard(page);
 await expect(page.getByRole("heading",{name:/good to see you, ari/i})).toBeVisible();
 await expect(page.getByRole("button",{name:"Toggle dashboard menu"})).toBeVisible();
 const motion=await page.locator(".cc-feature").first().evaluate(el=>getComputedStyle(el).transitionDuration);
 expect(motion==="0s"||motion==="0.01ms").toBeTruthy();
});