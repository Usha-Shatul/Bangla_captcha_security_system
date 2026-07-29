import { useNavigate, useLocation } from "react-router-dom";

const STEPS = [
  { key: "home", label: "কনসার্ট বাছাই", path: "/" },
  { key: "seats", label: "আসন নির্বাচন", path: "/seats" },
  { key: "checkout", label: "চেকআউট", path: "/checkout" },
  { key: "confirm", label: "নিশ্চিতকরণ", path: "/confirm" },
];

export default function Header() {
  const navigate = useNavigate();
  const location = useLocation();

  const activeKey = (() => {
    const p = location.pathname;
    if (p.startsWith("/seats")) return "seats";
    if (p.startsWith("/checkout")) return "checkout";
    if (p.startsWith("/confirm")) return "confirm";
    return "home";
  })();

  return (
    <header className="site-header">
      <div className="brand" onClick={() => navigate("/")}>
        <div className="mark">টি</div>
        <div className="name">টিকেটমুকুট</div>
      </div>
      <nav className="steps">
        {STEPS.map((s) => (
          <span
            key={s.key}
            className={activeKey === s.key ? "active" : ""}
          >
            {s.label}
          </span>
        ))}
      </nav>

      <style>{`
        .site-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 20px clamp(16px, 4vw, 56px);
          position: sticky;
          top: 0;
          z-index: 50;
          background: rgba(20, 18, 31, .85);
          backdrop-filter: blur(8px);
          border-bottom: 1px solid rgba(212, 169, 79, .18);
        }
        .brand {
          display: flex;
          align-items: center;
          gap: 10px;
          cursor: pointer;
        }
        .brand .mark {
          width: 34px;
          height: 34px;
          border-radius: 8px;
          background: linear-gradient(145deg, var(--gold), var(--curtain));
          display: flex;
          align-items: center;
          justify-content: center;
          font-family: var(--serif-display);
          font-weight: 800;
          color: var(--night);
          font-size: 18px;
        }
        .brand .name {
          font-family: var(--serif-display);
          font-weight: 700;
          font-size: 20px;
          letter-spacing: .3px;
        }
        .steps {
          display: flex;
          gap: 6px;
          font-size: 14px;
          color: rgba(242, 234, 223, .55);
        }
        .steps span {
          padding: 6px 10px;
          border-radius: 999px;
        }
        .steps span.active {
          background: rgba(212, 169, 79, .15);
          color: var(--gold-soft);
          font-weight: 600;
        }
        @media (max-width: 600px) {
          .steps { display: none; }
        }
      `}</style>
    </header>
  );
}
