import { useState } from "react";

type Language = "en" | "te";

const words = {
  house: { en: "house", te: "ఇల్లు" },
  door: { en: "door", te: "తలుపు" },
  window: { en: "window", te: "కిటికీ" },
  tree: { en: "tree", te: "చెట్టు" },
  sun: { en: "sun", te: "సూర్యుడు" },
} as const;

export function HouseLessonScene({ language, step }: { language: Language; step: number }) {
  const [selected, setSelected] = useState<keyof typeof words>("house");
  const label = (word: keyof typeof words) => words[word][language];
  return <div className="house-scene-wrap">
    <svg className="house-scene" viewBox="0 0 720 400" role="img" aria-labelledby="house-scene-title house-scene-desc">
      <title id="house-scene-title">A house in a green garden</title>
      <desc id="house-scene-desc">An interactive bilingual English and Telugu learning picture with a house, door, window, trees, and sun.</desc>
      <defs>
        <linearGradient id="house-sky" x2="0" y2="1"><stop stopColor="#8cddff"/><stop offset="1" stopColor="#d8f5ff"/></linearGradient>
        <linearGradient id="house-hill" x2="0" y2="1"><stop stopColor="#7cca66"/><stop offset="1" stopColor="#39a842"/></linearGradient>
        <linearGradient id="house-wall" x2="0" y2="1"><stop stopColor="#ffca78"/><stop offset="1" stopColor="#ee9349"/></linearGradient>
        <linearGradient id="house-roof" x2="0" y2="1"><stop stopColor="#c85632"/><stop offset="1" stopColor="#9f3429"/></linearGradient>
      </defs>
      <rect width="720" height="400" rx="20" fill="url(#house-sky)"/>
      <circle cx="555" cy="65" r="29" fill="#ffd344"/><g stroke="#ffd344" strokeWidth="5" strokeLinecap="round"><path d="M555 18V7M555 123v-11M508 65h-11M613 65h-11M522 32l-8-8M596 106l-8-8M588 32l8-8M514 106l8-8"/></g>
      <path d="M0 162 Q105 83 216 162 T433 155 T720 147V275H0Z" fill="#89c9ec"/><path d="M0 193 Q132 115 266 187 T513 184 T720 176V291H0Z" fill="#63aee0"/>
      <g fill="#fff" opacity=".84"><path d="M70 74c0-12 10-21 22-21 8-18 35-16 40 3 13-4 25 5 25 18H70Z"/><path d="M278 58c2-11 12-18 23-16 10-17 35-12 38 6 11-2 21 6 20 17H278Z"/></g>
      <path d="M0 247 Q92 184 192 236 T386 228 T564 219 T720 236V400H0Z" fill="url(#house-hill)"/>
      <path d="M0 309 Q163 273 328 308 T720 296V400H0Z" fill="#54b843"/>
      <g className="house-hotspot" role="button" tabIndex={0} aria-label={`Learn ${label("tree")}`} onClick={() => setSelected("tree")} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelected("tree"); } }}>
        <rect x="77" y="192" width="31" height="92" rx="7" fill="#8b563c"/><circle cx="93" cy="165" r="46" fill="#299a55"/><circle cx="62" cy="186" r="29" fill="#3dae5c"/><circle cx="121" cy="185" r="32" fill="#44b95d"/>
      </g>
      <g className="house-hotspot" role="button" tabIndex={0} aria-label={`Learn ${label("tree")}`} onClick={() => setSelected("tree")} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelected("tree"); } }}>
        <rect x="617" y="206" width="29" height="79" rx="7" fill="#8b563c"/><circle cx="632" cy="173" r="43" fill="#21934f"/><circle cx="602" cy="191" r="29" fill="#41ad57"/><circle cx="661" cy="192" r="27" fill="#4fbb5c"/>
      </g>
      <g className="house-hotspot" role="button" tabIndex={0} aria-label={`Learn ${label("house")}`} onClick={() => setSelected("house")} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelected("house"); } }}>
        <rect x="224" y="186" width="290" height="172" rx="5" fill="url(#house-wall)" stroke="#b85a39" strokeWidth="5"/>
        <path d="M198 199 365 91l171 108-16 20-155-96-151 96Z" fill="url(#house-roof)" stroke="#89322b" strokeWidth="5"/>
        <path d="M429 120V75h31v65" fill="#a44b35" stroke="#87332b" strokeWidth="5"/><path d="M426 75h37l7 11h-51Z" fill="#8b3f34"/>
        <g className="house-hotspot" role="button" tabIndex={0} aria-label={`Learn ${label("window")}`} onClick={e => { e.stopPropagation(); setSelected("window"); }} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); setSelected("window"); } }}>
          <rect x="258" y="222" width="66" height="58" rx="4" fill="#74d7ee" stroke="#9b4b32" strokeWidth="7"/><path d="M291 222v58m-33-29h66" stroke="#fff3cd" strokeWidth="5"/>
          <rect x="432" y="222" width="61" height="58" rx="4" fill="#74d7ee" stroke="#9b4b32" strokeWidth="7"/><path d="M462 222v58m-30-29h61" stroke="#fff3cd" strokeWidth="5"/>
        </g>
        <g className="house-hotspot" role="button" tabIndex={0} aria-label={`Learn ${label("door")}`} onClick={e => { e.stopPropagation(); setSelected("door"); }} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); setSelected("door"); } }}>
          <rect x="343" y="258" width="51" height="100" rx="24 24 0 0" fill="#8a4436" stroke="#6e382f" strokeWidth="5"/><circle cx="382" cy="309" r="4" fill="#f5d16b"/>
        </g>
      </g>
      <g fill="#ffd64e"><circle cx="55" cy="344" r="4"/><circle cx="139" cy="375" r="4"/><circle cx="566" cy="352" r="4"/><circle cx="684" cy="333" r="4"/></g>
      <g fill="#fff"><path d="m48 349 3-7 3 7 7 3-7 3-3 7-3-7-7-3Zm510 5 3-7 3 7 7 3-7 3-3 7-3-7-7-3Z"/></g>
      <g transform="translate(526 276)"><rect width="154" height="87" rx="16" fill="#fff" stroke="#ded8f4" strokeWidth="2"/><path d="M-15 44 0 34v22Z" fill="#fff"/><text x="77" y="34" textAnchor="middle" fontFamily="Inter,Arial,sans-serif" fontSize="22" fontWeight="800" fill="#211b58">{label(selected)}</text><text x="77" y="64" textAnchor="middle" fontFamily="Inter,Arial,sans-serif" fontSize="20" fontWeight="700" fill="#51449a">{selected === "window" ? "కిటికీ" : selected === "door" ? "తలుపు" : selected === "tree" ? "చెట్టు" : selected === "sun" ? "సూర్యుడు" : "ఇల్లు"}</text></g>
    </svg>
    <div className="house-word-chips" aria-label="Choose a picture word">{(Object.keys(words) as (keyof typeof words)[]).map(word => <button type="button" key={word} aria-pressed={selected === word} onClick={() => setSelected(word)}>{label(word)}</button>)}</div>
    <p className="house-scene-caption" aria-live="polite">{language === "en" ? `Step ${step + 1}: ${step === 0 ? "Learn the word" : step === 1 ? "Say it aloud" : step === 2 ? "Find the picture" : "Choose the right room"}. Select a word or picture to explore.` : `దశ ${step + 1}: ${step === 0 ? "పదాన్ని నేర్చుకోండి" : step === 1 ? "గట్టిగా పలకండి" : step === 2 ? "చిత్రాన్ని కనుగొనండి" : "సరైన గదిని ఎంచుకోండి"}. అన్వేషించడానికి పదం లేదా చిత్రాన్ని ఎంచుకోండి.`}</p>
  </div>;
}
