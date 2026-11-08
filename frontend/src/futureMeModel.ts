export type CareerId = "software-engineer" | "doctor" | "scientist" | "entrepreneur";

export type ScenarioChoice = {
  id: string;
  label: string;
  outcome: string;
  explanation: string;
  skills: string[];
  nextPrompt?: string;
};

export type ScenarioStep = {
  setting: string;
  prompt: string;
  choices: ScenarioChoice[];
};

export type CareerScenario = {
  id: CareerId;
  title: string;
  icon: string;
  color: "cyan" | "violet" | "mint" | "amber";
  summary: string;
  workplace: string;
  steps: ScenarioStep[];
  nextSteps: string[];
};

export const careerScenarios: CareerScenario[] = [
  {
    id: "software-engineer", title: "Software engineer", icon: "⌘", color: "cyan",
    summary: "Work with a small team to improve a learning app.", workplace: "Product studio · Sprint day 04",
    steps: [
      { setting: "A student reports that lesson progress disappears after refreshing the page. The team has a short planning meeting.", prompt: "What would you do first?", choices: [
        { id: "reproduce", label: "Reproduce the issue and note when it happens", outcome: "You find that progress is saved only in the current page state.", explanation: "Reproducing a problem gives the team evidence and a clear starting point.", skills: ["Debugging", "Careful observation"], nextPrompt: "Your teammate suggests a quick fix, but it may hide the underlying cause." },
        { id: "patch", label: "Add a quick refresh button so students can try again", outcome: "The page can reload, but the progress still disappears.", explanation: "A visible workaround can help temporarily, while the root cause still needs investigation.", skills: ["Rapid prototyping", "User empathy"], nextPrompt: "A student tester says the workaround is confusing." },
      ] },
      { setting: "The team has reproduced the issue and needs to choose a small improvement for this sprint.", prompt: "How will you make the next step useful for the student?", choices: [
        { id: "save", label: "Add a save indicator and test that progress returns after refresh", outcome: "The team can verify the fix and students get clear feedback when progress is saved.", explanation: "A visible status and a focused test help confirm the improvement from the learner's point of view.", skills: ["Testing", "Communication"] },
        { id: "refactor", label: "Rewrite the whole progress screen before testing", outcome: "The redesign starts, but the original issue is still unverified.", explanation: "Keeping a change small makes it easier to test and learn from feedback.", skills: ["Planning", "Scope management"] },
      ] },
      { setting: "The fix is ready for a review with a designer and another developer.", prompt: "How do you close the loop?", choices: [
        { id: "demo", label: "Demo the fix, share the test result, and ask for feedback", outcome: "The team sees the change working and has a clear next improvement to consider.", explanation: "A short demo connects technical work to the people using it.", skills: ["Collaboration", "Presentation"] },
        { id: "merge", label: "Merge it without a review to finish quickly", outcome: "The change ships, but the team misses a chance to catch usability issues.", explanation: "Review gives teammates a chance to spot issues and share context.", skills: ["Ownership", "Decision making"] },
      ] },
    ],
    nextSteps: ["Try a beginner coding puzzle and explain each step aloud.", "Build a tiny webpage and ask someone to test it."],
  },
  {
    id: "doctor", title: "Doctor", icon: "＋", color: "mint",
    summary: "Practice listening, organizing information, and explaining a care plan.", workplace: "Community clinic · Learning scenario",
    steps: [
      { setting: "A patient says they have felt tired lately and are worried. This is a communication practice scenario, not medical advice.", prompt: "How do you begin the conversation?", choices: [
        { id: "listen", label: "Listen without interrupting, then ask an open question", outcome: "The patient shares more about their concern and what they have noticed.", explanation: "Listening first can help people feel heard and helps gather context.", skills: ["Active listening", "Empathy"] },
        { id: "assume", label: "Guess what is wrong before hearing more", outcome: "The patient is unsure whether their concern has been understood.", explanation: "A guess can miss important context. Asking before concluding keeps the conversation open.", skills: ["Reflection", "Communication"] },
      ] },
      { setting: "You have heard the patient's concern. The care team needs an organized summary.", prompt: "What is a helpful next move?", choices: [
        { id: "summarize", label: "Summarize what you heard and check you understood", outcome: "The patient can correct or add details before the team continues.", explanation: "Checking a summary helps reduce misunderstandings.", skills: ["Clear communication", "Attention to detail"] },
        { id: "rush", label: "Move on without checking the details", outcome: "Some of the patient's context may not be carried into the discussion.", explanation: "A brief check can make a conversation more accurate and collaborative.", skills: ["Organization", "Responsibility"] },
      ] },
      { setting: "The care team has discussed appropriate next steps with the patient.", prompt: "How do you make the plan easier to follow?", choices: [
        { id: "plain", label: "Explain the agreed plan in simple language and invite questions", outcome: "The patient knows what the team discussed and can ask about anything unclear.", explanation: "Plain language and questions support shared understanding.", skills: ["Teaching", "Empathy"] },
        { id: "jargon", label: "Use technical terms and end the conversation quickly", outcome: "The patient may leave uncertain about the plan.", explanation: "Checking for understanding helps make information more accessible.", skills: ["Adaptability", "Communication"] },
      ] },
    ],
    nextSteps: ["Practice summarizing a short story in your own words.", "Explore a biology lesson about how body systems work."],
  },
  {
    id: "scientist", title: "Scientist", icon: "⚗", color: "violet",
    summary: "Explore a question, plan a fair test, and share what evidence shows.", workplace: "Research lab · Water clarity study",
    steps: [
      { setting: "Your team notices that water samples look different after rain. You are exploring why, using classroom-safe sample data.", prompt: "How do you shape the investigation?", choices: [
        { id: "question", label: "Write one testable question and list what you will measure", outcome: "The team agrees to compare clarity across samples collected at different times.", explanation: "A focused question makes it easier to plan what evidence to collect.", skills: ["Curiosity", "Planning"] },
        { id: "conclude", label: "Decide the cause from appearance alone", outcome: "The team has a guess, but no evidence to compare it with yet.", explanation: "An early idea can guide a test, but observation alone may not explain the cause.", skills: ["Observation", "Critical thinking"] },
      ] },
      { setting: "The question is ready. Your group wants results it can compare fairly.", prompt: "What helps make the comparison fair?", choices: [
        { id: "control", label: "Use the same container and method for every sample", outcome: "The team can compare samples with fewer differences in how they were measured.", explanation: "Keeping the method consistent makes comparisons more meaningful.", skills: ["Fair testing", "Precision"] },
        { id: "vary", label: "Change the container and method for each sample", outcome: "The measurements may differ because of the setup, not the samples.", explanation: "Changing several things at once makes it harder to interpret a result.", skills: ["Method design", "Attention to detail"] },
      ] },
      { setting: "The team has recorded its observations and is preparing to share them.", prompt: "How do you report the result?", choices: [
        { id: "evidence", label: "Show the observations and mention what remains uncertain", outcome: "Others can review the evidence and suggest a useful follow-up question.", explanation: "Sharing limits as well as findings helps keep conclusions grounded in evidence.", skills: ["Data literacy", "Honesty"] },
        { id: "claim", label: "Present the first explanation as proven", outcome: "The claim goes beyond what this small investigation can show.", explanation: "A careful conclusion matches the strength of the evidence.", skills: ["Scientific reasoning", "Communication"] },
      ] },
    ],
    nextSteps: ["Keep a question journal and pick one idea to investigate safely.", "Practice making a simple table or graph from sample observations."],
  },
  {
    id: "entrepreneur", title: "Entrepreneur", icon: "↗", color: "amber",
    summary: "Learn about a need, test an idea, and make a thoughtful plan.", workplace: "Student venture studio · Idea week",
    steps: [
      { setting: "Your group is thinking about a service that helps students find quiet places to study.", prompt: "How do you check whether the idea solves a real need?", choices: [
        { id: "interview", label: "Ask a few students about their study routines", outcome: "You learn that some students need quiet space while others need reliable group rooms.", explanation: "Listening to potential users helps shape an idea around real experiences.", skills: ["Customer discovery", "Listening"] },
        { id: "assume", label: "Build the full service based on your own routine", outcome: "You have a concept, but have not checked whether it fits other students.", explanation: "Your experience is a useful start, and more viewpoints can reveal different needs.", skills: ["Initiative", "Reflection"] },
      ] },
      { setting: "You have heard a few different needs and need to test a manageable idea.", prompt: "What is a sensible experiment?", choices: [
        { id: "prototype", label: "Sketch a simple room-booking flow and ask students to try it", outcome: "Feedback shows which parts are clear and which need another pass.", explanation: "A small prototype can test an assumption before a team invests more effort.", skills: ["Experimentation", "Design thinking"] },
        { id: "launch", label: "Announce a finished service before checking the flow", outcome: "Students are interested, but the team does not yet know if the flow works.", explanation: "Testing the experience first helps a team learn before making a larger promise.", skills: ["Communication", "Risk awareness"] },
      ] },
      { setting: "Your team has notes from the prototype. Now it needs to choose what to improve.", prompt: "How will you decide what comes next?", choices: [
        { id: "prioritize", label: "Choose one improvement based on feedback and explain why", outcome: "The team has a clear, evidence-informed next step and can check its impact.", explanation: "Prioritizing one change makes learning from the next test more manageable.", skills: ["Prioritization", "Teamwork"] },
        { id: "everything", label: "Try to add every suggested feature at once", outcome: "The scope grows and it becomes hard to tell which change helped.", explanation: "A focused improvement makes the next round of feedback easier to interpret.", skills: ["Focus", "Planning"] },
      ] },
    ],
    nextSteps: ["Notice a small everyday problem and write down who experiences it.", "Make a paper prototype for an idea and ask a friend what is confusing."],
  },
];

export type SimulationState = { careerId: CareerId; stepIndex: number; choices: ScenarioChoice[] };

export function startSimulation(careerId: CareerId): SimulationState {
  return { careerId, stepIndex: 0, choices: [] };
}

export function chooseScenarioOption(state: SimulationState, choiceId: string): SimulationState {
  const scenario = careerScenarios.find(item => item.id === state.careerId);
  const step = scenario?.steps[state.stepIndex];
  const choice = step?.choices.find(item => item.id === choiceId);
  if (!scenario || !step || !choice || state.choices.length !== state.stepIndex) return state;
  return { ...state, stepIndex: state.stepIndex + 1, choices: [...state.choices, choice] };
}

export function isSimulationComplete(state: SimulationState): boolean {
  const scenario = careerScenarios.find(item => item.id === state.careerId);
  return Boolean(scenario && state.choices.length === scenario.steps.length);
}

export function demonstratedSkills(state: SimulationState): string[] {
  return [...new Set(state.choices.flatMap(choice => choice.skills))];
}
