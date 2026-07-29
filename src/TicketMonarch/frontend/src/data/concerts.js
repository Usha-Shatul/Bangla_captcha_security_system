export const CONCERTS = [
  {
    id: 1,
    title: "নগরবাউল লাইভ",
    artist: "জেমস ও নগরবাউল",
    genre: "রক",
    venue: "আর্মি স্টেডিয়াম, ঢাকা",
    date: "৩ আগস্ট, ২০২৬",
    base: 1200,
    art: "rock",
  },
  {
    id: 2,
    title: "লালন মেলা সন্ধ্যা",
    artist: "অর্ণব ও দল",
    genre: "লোক-ফিউশন",
    venue: "শিল্পকলা একাডেমি, ঢাকা",
    date: "১০ আগস্ট, ২০২৬",
    base: 900,
    art: "folk",
  },
  {
    id: 3,
    title: "চিরকুট আনপ্লাগড",
    artist: "চিরকুট ব্যান্ড",
    genre: "ইনডি",
    venue: "বসুন্ধরা কনভেনশন সেন্টার",
    date: "১৭ আগস্ট, ২০২৬",
    base: 1000,
    art: "indie",
  },
  {
    id: 4,
    title: "সুরের ভেলা ট্যুর",
    artist: "হাবিব ওয়াহিদ",
    genre: "পপ",
    venue: "চট্টগ্রাম আউটার স্টেডিয়াম",
    date: "২৪ আগস্ট, ২০২৬",
    base: 1500,
    art: "pop",
  },
  {
    id: 5,
    title: "অ্যাকুস্টিক নাইট",
    artist: "তাহসান খান",
    genre: "অ্যাকুস্টিক",
    venue: "বাংলা একাডেমি চত্বর, ঢাকা",
    date: "৩১ আগস্ট, ২০২৬",
    base: 800,
    art: "acoustic",
  },
];

export const SEAT_CATS = [
  { key: "vip", label: "ভিআইপি", mult: 3, rows: [0] },
  { key: "gold", label: "গোল্ড", mult: 2, rows: [1, 2] },
  { key: "silver", label: "সিলভার", mult: 1.4, rows: [3, 4] },
  { key: "general", label: "জেনারেল", mult: 1, rows: [5, 6, 7] },
];

export const ROW_LABELS = ["A", "B", "C", "D", "E", "F", "G", "H"];
export const SEATS_PER_ROW = 10;

export function artSVG(kind) {
  const bg = {
    rock: "#3A1420",
    folk: "#1E3326",
    indie: "#2A1F3D",
    pop: "#3D1F33",
    acoustic: "#1F2A3D",
  }[kind] || "#222";
  const shapes = {
    rock: `<path d="M0 90 L40 40 L70 70 L110 20 L150 90 Z" fill="#D4A94F" opacity=".55"/>`,
    folk: `<circle cx="60" cy="55" r="30" fill="none" stroke="#D4A94F" stroke-width="3" opacity=".6"/><circle cx="60" cy="55" r="14" fill="#D4A94F" opacity=".4"/>`,
    indie: `<rect x="30" y="30" width="24" height="50" fill="#D4A94F" opacity=".5"/><rect x="60" y="45" width="24" height="35" fill="#D4A94F" opacity=".3"/><rect x="90" y="20" width="24" height="60" fill="#D4A94F" opacity=".6"/>`,
    pop: `<path d="M20 70 Q60 10 100 70 T180 70" stroke="#D4A94F" stroke-width="4" fill="none" opacity=".6"/>`,
    acoustic: `<path d="M50 20 Q30 55 50 90 Q70 55 50 20 Z" fill="#D4A94F" opacity=".45"/>`,
  }[kind];
  return `<svg viewBox="0 0 150 100" preserveAspectRatio="xMidYMid slice"><rect width="150" height="100" fill="${bg}"/>${shapes}</svg>`;
}

export function getConcertById(id) {
  return CONCERTS.find((c) => c.id === Number(id));
}
