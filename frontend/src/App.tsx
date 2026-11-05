import { Link, Route, Routes } from "react-router-dom";

function Welcome() {
  return <main className="shell"><span className="eyebrow">TELUGU × ENGLISH LEARNING</span><h1>Welcome to <span>BHASHALEARN AI</span></h1><p>A bilingual AI learning experience. Your classroom is taking shape.</p><div className="actions"><Link to="/about" className="button">Explore the foundation</Link></div></main>;
}
function About() { return <main className="shell"><Link to="/" className="back">← Home</Link><h1>Built for <span>every learner.</span></h1><p>React, TypeScript, routing, and a development API proxy are ready. The landing page comes next.</p></main>; }
export default function App() { return <Routes><Route path="/" element={<Welcome/>}/><Route path="/about" element={<About/>}/><Route path="*" element={<main className="shell"><h1>Page not found</h1><Link to="/">Go home</Link></main>}/></Routes>; }
