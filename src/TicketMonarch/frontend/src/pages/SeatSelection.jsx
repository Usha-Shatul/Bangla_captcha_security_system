import { useState, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import Header from "../components/Header.jsx";
import { getConcertById, SEAT_CATS, ROW_LABELS, SEATS_PER_ROW } from "../data/concerts.js";

function catFor(rowIdx) {
  return SEAT_CATS.find((c) => c.rows.includes(rowIdx));
}

function generateTaken(count) {
  const total = ROW_LABELS.length * SEATS_PER_ROW;
  const set = new Set();
  while (set.size < count) set.add(Math.floor(Math.random() * total));
  return set;
}

export default function SeatSelectionPage() {
  const { concertId } = useParams();
  const navigate = useNavigate();
  const concert = getConcertById(concertId);
  const takenSeats = useMemo(() => generateTaken(Math.floor(ROW_LABELS.length * SEATS_PER_ROW * 0.22)), []);
  const [selected, setSelected] = useState([]);

  if (!concert) {
    return (
      <div>
        <Header />
        <main style={{ padding: 40, textAlign: "center" }}>
          <p>কনসার্ট পাওয়া যায়নি।</p>
          <button className="btn btn-outline" onClick={() => navigate("/")}>হোমে ফিরে যান</button>
        </main>
      </div>
    );
  }

  function toggleSeat(idx, label, col, cat) {
    setSelected((prev) => {
      const exists = prev.find((s) => s.idx === idx);
      if (exists) return prev.filter((s) => s.idx !== idx);
      if (prev.length >= 8) {
        alert("সর্বোচ্চ ৮টি আসন একসাথে বাছাই করা যাবে।");
        return prev;
      }
      return [...prev, {
        idx,
        seatCode: `${label}${col + 1}`,
        cat: cat.label,
        catKey: cat.key,
        price: Math.round(concert.base * cat.mult),
      }];
    });
  }

  const total = selected.reduce((a, s) => a + s.price, 0);

  function proceed() {
    if (selected.length === 0) return;
    sessionStorage.setItem("booking", JSON.stringify({
      concert,
      seats: selected,
      total,
    }));
    navigate("/checkout");
  }

  return (
    <div>
      <Header />
      <main>
        <div className="back-link" onClick={() => navigate("/")}>← কনসার্ট তালিকায় ফিরে যান</div>
        <div className="section-title" id="seats-title">
          {concert.title} <small>{concert.venue} · {concert.date}</small>
        </div>

        <div className="seat-layout">
          <div>
            <div className="stage-curve">▶ মঞ্চ এই দিকে ◀</div>
            <div className="seat-map">
              {ROW_LABELS.map((label, rowIdx) => {
                const cat = catFor(rowIdx);
                return (
                  <div key={label} className="seat-row">
                    <div className="row-label">{label}</div>
                    {Array.from({ length: SEATS_PER_ROW }, (_, col) => {
                      const seatIdx = rowIdx * SEATS_PER_ROW + col;
                      const taken = takenSeats.has(seatIdx);
                      const sel = selected.find((s) => s.idx === seatIdx);
                      return (
                        <button
                          key={col}
                          className={`seat ${cat.key}${taken ? " taken" : ""}${sel ? " selected" : ""}`}
                          title={`${label}${col + 1} — ${cat.label} — ৳${Math.round(concert.base * cat.mult)}`}
                          disabled={taken}
                          onClick={() => !taken && toggleSeat(seatIdx, label, col, cat)}
                        >
                          {col + 1}
                        </button>
                      );
                    })}
                  </div>
                );
              })}
            </div>
            <div className="legend">
              <span><i style={{ background: "var(--gold-soft)" }} /> ভিআইপি</span>
              <span><i style={{ background: "#C79B4A" }} /> গোল্ড</span>
              <span><i style={{ background: "#9AA0AE" }} /> সিলভার</span>
              <span><i style={{ background: "#5C6478" }} /> জেনারেল</span>
              <span><i style={{ background: "#2A2735" }} /> বুকড</span>
            </div>
          </div>

          <div className="stub">
            <h3>আপনার নির্বাচন</h3>
            {selected.length === 0 ? (
              <div className="empty-note">
                এখনও কোনো আসন বাছাই করা হয়নি — উপরের ম্যাপ থেকে আসন ক্লিক করুন
              </div>
            ) : (
              <>
                {selected.map((s) => (
                  <div key={s.idx} className="stub-row">
                    <span>আসন {s.seatCode} · {s.cat}</span>
                    <strong>৳{s.price}</strong>
                  </div>
                ))}
                <div className="stub-divider" />
                <div className="stub-total">
                  <span>সর্বমোট</span>
                  <strong>৳{total}</strong>
                </div>
              </>
            )}
            <button
              className="btn btn-gold"
              style={{ width: "100%", marginTop: 18 }}
              disabled={selected.length === 0}
              onClick={proceed}
            >
              চেকআউটে যান
            </button>
          </div>
        </div>
      </main>

      <style>{`
        main { padding: 8px clamp(16px,4vw,56px) 80px; }
        .back-link {
          display: inline-flex; align-items: center; gap: 6px;
          color: var(--gold-soft); font-size: 14px; cursor: pointer; margin: 22px 0 4px;
        }
        .seat-layout {
          display: grid; grid-template-columns: 1fr 320px; gap: 28px;
          align-items: start; margin-top: 16px;
        }
        @media(max-width:860px) { .seat-layout { grid-template-columns: 1fr; } }
        .stage-curve {
          text-align: center; color: rgba(242,234,223,.45); font-size: 12px;
          letter-spacing: .3em; text-transform: uppercase;
          padding: 10px; margin-bottom: 22px;
          border-bottom: 2px solid rgba(212,169,79,.35);
          border-radius: 50%/8px;
        }
        .seat-map {
          display: flex; flex-direction: column; align-items: center; gap: 9px;
        }
        .seat-row { display: flex; gap: 7px; align-items: center; }
        .row-label {
          width: 20px; font-size: 12px; color: rgba(242,234,223,.4);
          text-align: right; margin-right: 4px;
        }
        .seat {
          width: 24px; height: 24px; border-radius: 6px 6px 8px 8px; border: none;
          cursor: pointer; display: flex; align-items: center; justify-content: center;
          font-size: 9px; color: rgba(20,18,31,.6); transition: transform .1s ease;
        }
        .seat:hover:not(.taken) { transform: scale(1.15); }
        .seat.vip { background: var(--gold-soft); }
        .seat.gold { background: #C79B4A; }
        .seat.silver { background: #9AA0AE; }
        .seat.general { background: #5C6478; }
        .seat.taken { background: #2A2735; cursor: not-allowed; }
        .seat.selected {
          outline: 2px solid #fff;
          box-shadow: 0 0 0 3px rgba(255,255,255,.25);
        }
        .legend {
          display: flex; gap: 16px; flex-wrap: wrap; justify-content: center;
          margin-top: 24px; font-size: 12px; color: rgba(242,234,223,.6);
        }
        .legend span { display: inline-flex; align-items: center; gap: 6px; }
        .legend i { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }
        .stub {
          background: var(--night-2); border-radius: var(--radius);
          position: relative; padding: 22px 22px 20px;
          border: 1px solid rgba(212,169,79,.2);
        }
        .stub h3 { font-family: var(--serif-display); margin: 0 0 14px; font-size: 18px; }
        .stub-row {
          display: flex; justify-content: space-between; font-size: 14px;
          padding: 6px 0; color: rgba(242,234,223,.75);
        }
        .stub-row strong { color: var(--cream); }
        .stub-divider {
          height: 0; border-top: 2px dashed rgba(212,169,79,.35);
          margin: 14px -22px; position: relative;
        }
        .stub-divider::before, .stub-divider::after {
          content: ''; position: absolute; top: -11px;
          width: 22px; height: 22px; border-radius: 50%; background: var(--night-2);
        }
        .stub-divider::before { left: -11px; }
        .stub-divider::after { right: -11px; }
        .stub-total {
          display: flex; justify-content: space-between; align-items: baseline; margin-top: 6px;
        }
        .stub-total strong {
          font-family: var(--serif-display); font-size: 26px; color: var(--gold-soft);
        }
        .empty-note { font-size: 13px; color: rgba(242,234,223,.5); text-align: center; padding: 20px 0; }
      `}</style>
    </div>
  );
}
