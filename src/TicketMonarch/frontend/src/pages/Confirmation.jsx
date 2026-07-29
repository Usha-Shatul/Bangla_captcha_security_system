import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Header from "../components/Header.jsx";

export default function ConfirmationPage() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);

  useEffect(() => {
    const raw = sessionStorage.getItem("booking");
    if (!raw) { navigate("/"); return; }
    setData(JSON.parse(raw));
  }, [navigate]);

  if (!data) return null;

  const orderId = data.orderId || "TM" + Math.floor(100000 + Math.random() * 899999);
  const qrCells = Array.from({ length: 64 }, () => Math.random() > 0.52);

  return (
    <div>
      <Header />
      <main>
        <div className="confirm-wrap">
          <div className="confirm-badge">✓</div>
          <h1 className="confirm-title">টিকেট বুকিং সম্পন্ন হয়েছে!</h1>
          <p className="confirm-sub">
            অর্ডার নম্বর <strong style={{ color: "var(--gold-soft)" }}>#{orderId}</strong> —
            বিস্তারিত ইমেইলে পাঠানো হয়েছে
          </p>

          <div className="stub" style={{ textAlign: "left" }}>
            <h3>{data.concert.title} — {data.buyer?.name || ""}</h3>
            {data.seats.map((s) => (
              <div key={s.idx} className="stub-row">
                <span>আসন {s.seatCode} · {s.cat}</span>
                <strong>৳{s.price}</strong>
              </div>
            ))}
            <div className="stub-row">
              <span>ভেন্যু ও তারিখ</span>
              <strong style={{ textAlign: "right" }}>
                {data.concert.venue}<br />{data.concert.date}
              </strong>
            </div>
            <div className="stub-divider" />
            <div className="stub-total">
              <span>পরিশোধিত মোট</span>
              <strong>৳{data.total}</strong>
            </div>
            <div className="qr-block">
              {qrCells.map((on, i) => (
                <i key={i} className={on ? "" : "off"} />
              ))}
            </div>
            <div className="qr-label">প্রবেশপথে এই কোড দেখান</div>
          </div>

          <button
            className="btn btn-outline"
            style={{ marginTop: 22 }}
            onClick={() => { sessionStorage.removeItem("booking"); navigate("/"); }}
          >
            আরও কনসার্ট দেখুন
          </button>
        </div>
      </main>

      <style>{`
        main { padding: 8px clamp(16px,4vw,56px) 80px; }
        .confirm-wrap { max-width: 560px; margin: 20px auto 0; text-align: center; }
        .confirm-badge {
          width: 64px; height: 64px; border-radius: 50%; margin: 0 auto 18px;
          background: linear-gradient(140deg, var(--gold-soft), var(--gold));
          display: flex; align-items: center; justify-content: center;
          font-size: 30px; color: var(--night);
        }
        .confirm-title {
          font-family: var(--serif-display); font-size: 26px; margin: 0 0 6px;
        }
        .confirm-sub {
          color: rgba(242,234,223,.7); margin: 0 0 20px; font-size: 15px;
        }
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
        .qr-block {
          width: 110px; height: 110px; margin: 18px auto; border-radius: 10px;
          background: var(--cream);
          display: grid; grid-template-columns: repeat(8,1fr); grid-template-rows: repeat(8,1fr);
          padding: 8px; gap: 2px;
        }
        .qr-block i { background: var(--night); border-radius: 1px; }
        .qr-block i.off { background: transparent; }
        .qr-label {
          text-align: center; font-size: 12px; color: rgba(242,234,223,.5); margin-top: 4px;
        }
      `}</style>
    </div>
  );
}
