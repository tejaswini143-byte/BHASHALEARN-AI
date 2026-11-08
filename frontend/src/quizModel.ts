export type QuizQuestion = {
  attempt_id: string;
  question_id: string;
  position: number;
  type: "multiple_choice" | "true_false" | "fill_blank" | "short_answer";
  difficulty: string;
  source: string;
  prompt: string;
  options: string[];
};

export type QuizResultQuestion = {
  attempt_id: string;
  question_id: string;
  position: number;
  type: string;
  prompt: string;
  answer: string;
  is_correct: boolean;
  correct_answer: string;
  explanation: string;
};

export type Quiz = {
  quiz_id: string;
  session_id: string;
  subject: string;
  topic: string;
  language: string;
  difficulty: string;
  adaptive_difficulty: boolean;
  source: string;
  questions: QuizQuestion[];
};

export type QuizSummary = {
  quiz_id: string;
  subject: string;
  topic: string;
  language: string;
  difficulty: string;
  question_count: number;
  score: number;
  mastery_score: number;
  completed: boolean;
  issued_at: string;
};

export type QuizResults = QuizSummary & {
  questions: QuizResultQuestion[];
  topic_recommendation?: string;
  replayed?: boolean;
};

export function progressPercent(currentIndex: number, questionCount: number): number {
  if (questionCount <= 0) return 0;
  return Math.round((Math.max(0, Math.min(currentIndex + 1, questionCount)) / questionCount) * 100);
}

export function answeredCount(questions: QuizQuestion[], answers: Record<string, string>): number {
  return questions.filter(question => Boolean(answers[question.attempt_id]?.trim())).length;
}

export function resultFeedback(result: Pick<QuizResults, "score" | "question_count">) {
  const ratio = result.question_count > 0 ? result.score / result.question_count : 0;
  return ratio >= 0.8 ? "strong" : ratio >= 0.5 ? "building" : "review";
}
