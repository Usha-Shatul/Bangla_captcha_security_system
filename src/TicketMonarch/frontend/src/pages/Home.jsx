import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import Header from "../components/Header.jsx";
import { CONCERTS, artSVG } from "../data/concerts.js";

function MarqueeBulbs({ position }) {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    for (let i = 0; i < 24; i++) {
      const b = document.createElement("div");
      b.className = "bulb";
      b.style.animationDelay = (i * 0.07 + (position === "bottom" ? 0.3 : 0)) + "s";
      el.appendChild(b);
    }
    return () => { el.innerHTML = ""; };
  }, [position]);
  return <div ref={ref} className={`marquee-row ${position}`} />;
}

export default function HomePage() {
  const navigate = useNavigate();

  return (
    <div>
      <Header />

      <div className="hero">
        <MarqueeBulbs position="top" />
        <MarqueeBulbs position="bottom" />
        <h1>মঞ্চের আলো জ্বলবে, আপনার আসন বাঁধা থাকুক আগেই</h1>
        <p>
          দেশের সেরা লাইভ কনসার্টের টিকেট বুক করুন কয়েক ক্লিকেই — আসন বাছাই
          থেকে পেমেন্ট, সবকিছু এক জায়গায়।
        </p>
        <div className="hero-stats">
          <div><strong>৫</strong>চলতি কনসার্ট</div>
          <div><strong>১২টি</strong>ভেন্যু জুড়ে</div>
          <div><strong>৪ ক্যাটাগরি</strong>আসনের ধরন</div>
        </div>
      </div>

      <main>
        <div className="section-title">
          এই সপ্তাহের কনসার্ট{" "}
          <small>আসন খালি থাকা অবস্থায় বুক করুন</small>
        </div>
        <div className="grid">
          {CONCERTS.map((c) => (
            <div
              key={c.id}
              className="concert-card"
              onClick={() => navigate(`/seats/${c.id}`)}
            >
              <div
                className="concert-art"
                dangerouslySetInnerHTML={{ __html: artSVG(c.art) }}
              />
              <div className="concert-body">
                <div className="genre-tag">{c.genre}</div>
                <div className="concert-title">{c.title}</div>
                <div className="concert-artist">{c.artist}</div>
                <div className="concert-meta">
                  <span>📍 {c.venue}</span>
                  <span>🗓️ {c.date}</span>
                </div>
                <div className="price-row">
                  <div className="price-from">
                    শুরু <strong>৳{c.base}</strong> থেকে
                  </div>
                  <button className="btn btn-outline">টিকেট দেখুন</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </main>

      <footer className="site-footer">
        টিকেটমুকুট — একটি ডেমো ওয়েবসাইট, স্থানীয়ভাবে চালানোর জন্য তৈরি। কোনো
        প্রকৃত পেমেন্ট প্রক্রিয়া করা হয় না।
      </footer>

      <style>{`
        .hero {
          position: relative;
          margin: 28px clamp(16px,4vw,56px) 8px;
          padding: 56px clamp(20px,5vw,64px);
          border-radius: 20px;
          background:
            linear-gradient(180deg, rgba(122,31,43,.55), rgba(20,18,31,.2)),
            repeating-linear-gradient(115deg, rgba(255,255,255,.03) 0 2px, transparent 2px 22px);
          overflow: hidden;
          border: 1px solid rgba(212,169,79,.25);
        }
        .marquee-row {
          position: absolute; left: 0; right: 0;
          display: flex; justify-content: space-between; padding: 0 18px;
        }
        .marquee-row.top { top: 10px; }
        .marquee-row.bottom { bottom: 10px; }
        .bulb {
          width: 8px; height: 8px; border-radius: 50%;
          background: var(--gold-soft);
          box-shadow: 0 0 8px 2px rgba(232,199,122,.7);
          animation: twinkle 1.6s ease-in-out infinite;
        }
        @keyframes twinkle {
          0%, 100% { opacity: .35; transform: scale(.85); }
          50% { opacity: 1; transform: scale(1); }
        }
        .hero h1 {
          font-family: var(--serif-display); font-weight: 800;
          font-size: clamp(30px, 5vw, 52px);
          margin: 0 0 12px; max-width: 16ch;
        }
        .hero p {
          max-width: 52ch; color: rgba(242,234,223,.8);
          font-size: 17px; margin: 0 0 22px;
        }
        .hero-stats {
          display: flex; gap: 28px; flex-wrap: wrap; margin-top: 8px;
        }
        .hero-stats div {
          font-size: 13px; color: rgba(242,234,223,.6);
        }
        .hero-stats strong {
          display: block; font-family: var(--serif-display);
          font-size: 22px; color: var(--gold-soft);
        }
        main { padding: 8px clamp(16px,4vw,56px) 80px; }
        .grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
          gap: 20px;
        }
        .concert-card {
          background: var(--night-2);
          border: 1px solid rgba(212,169,79,.15);
          border-radius: var(--radius);
          overflow: hidden;
          cursor: pointer;
          transition: transform .18s ease, border-color .18s ease;
          display: flex; flex-direction: column;
        }
        .concert-card:hover {
          transform: translateY(-4px);
          border-color: rgba(212,169,79,.5);
        }
        .concert-art { height: 130px; position: relative; }
        .concert-art svg { width: 100%; height: 100%; display: block; }
        .concert-body { padding: 16px 18px 18px; }
        .genre-tag {
          font-size: 11px; letter-spacing: .06em; color: var(--gold-soft);
          text-transform: uppercase; font-weight: 600;
        }
        .concert-title {
          font-family: var(--serif-display); font-size: 19px;
          font-weight: 700; margin: 4px 0 2px;
        }
        .concert-artist {
          font-size: 14px; color: rgba(242,234,223,.65); margin-bottom: 10px;
        }
        .concert-meta {
          font-size: 13px; color: rgba(242,234,223,.55);
          display: flex; flex-direction: column; gap: 3px; margin-bottom: 14px;
        }
        .price-row {
          display: flex; justify-content: space-between; align-items: center;
        }
        .price-from {
          font-size: 13px; color: rgba(242,234,223,.55);
        }
        .price-from strong {
          color: var(--gold-soft); font-size: 16px;
          font-family: var(--serif-display);
        }
        .site-footer {
          text-align: center; padding: 28px 16px 40px;
          font-size: 12.5px; color: rgba(242,234,223,.35);
        }
        @media (prefers-reduced-motion: reduce) {
          .bulb { animation: none; }
        }
      `}</style>
    </div>
  );
}
