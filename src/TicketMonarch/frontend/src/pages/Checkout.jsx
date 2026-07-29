import { useState, useRef, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Header from "../components/Header.jsx";
import BanglaCaptcha from "../components/BanglaCaptcha.jsx";
import KeyboardTracker from "../components/KeyboardTracker.jsx";
import MouseTracker from "../components/MouseTracker.jsx";
import { bookTicket, trackBehavior } from "../services/api.js";

export default function CheckoutPage() {
  const navigate = useNavigate();
  const [bookingData, setBookingData] = useState(null);
  const [captchaVerified, setCaptchaVerified] = useState(false);
  const [securityAction, setSecurityAction] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ name: "", email: "", phone: "", card: "", exp: "", cvv: "" });
  const [errors, setErrors] = useState({});
  const [sessionId] = useState(() => crypto.randomUUID());
  const behaviorRef = useRef({ keyboard: { events: [] }, mouse: { events: [] }, session_start: Date.now(), session_duration_ms: 0 });
  const timerRef = useRef(null);

  useEffect(() => {
    const raw = sessionStorage.getItem("booking");
    if (!raw) { navigate("/"); return; }
    setBookingData(JSON.parse(raw));
  }, [navigate]);

  const handleBehaviorUpdate = useCallback((type, data) => {
    behaviorRef.current[type] = {
      ...behaviorRef.current[type],
      ...data,
      events: [...(behaviorRef.current[type].events || []), ...(data.events || [])].slice(-500),
    };
    behaviorRef.current.session_duration_ms = Date.now() - behaviorRef.current.session_start;
    if (!timerRef.current) {
      timerRef.current = setTimeout(() => {
        trackBehavior({
          mouse: behaviorRef.current.mouse.events,
          keyboard: behaviorRef.current.keyboard.events,
          session_duration_ms: behaviorRef.current.session_duration_ms,
        }).catch(() => {});
        timerRef.current = null;
      }, 5000);
    }
  }, []);

  const handleSecurityAction = useCallback((action) => {
    setSecurityAction(action);
    if (action?.action_name === "allow") setCaptchaVerified(true);
  }, []);

  const handleCaptchaVerified = useCallback((result) => {
    const nextAction = result?.security_action;
    if (nextAction?.action_name === "allow") {
      setCaptchaVerified(true);
    } else {
      setCaptchaVerified(false);
    }
  }, []);

  function handleChange(e) {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
    setErrors((prev) => ({ ...prev, [name]: "" }));
  }

  function validate() {
    const errs = {};
    if (form.name.trim().length < 2) errs.name = "নাম লিখুন";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) errs.email = "সঠিক ইমেইল দিন";
    if (!/^[0-9০-৯]{11}$/.test(form.phone.replace(/\s/g, ""))) errs.phone = "১১ সংখ্যার নম্বর দিন";
    if (form.card.replace(/\s/g, "").length !== 16) errs.card = "১৬ সংখ্যার কার্ড নম্বর দিন";
    if (!/^[0-9০-৯]{1,2}\/[0-9০-৯]{2}$/.test(form.exp)) errs.exp = "সঠিক ফরম্যাট দিন";
    if (form.cvv.length !== 3) errs.cvv = "৩ সংখ্যার CVV দিন";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const actionName = securityAction?.action_name || securityAction?.action;
    if (actionName === "block") { setError("আপনার সেশন ব্লক করা হয়েছে।"); return; }
    if (!captchaVerified && actionName !== "allow") { setError("প্রথমে ক্যাপচা সমাধান করুন।"); return; }
    if (!validate()) return;

    setSubmitting(true);
    setError("");
    try {
      const result = await bookTicket({
        session_id: sessionId,
        destination: bookingData.concert.title,
        date: bookingData.concert.date,
        passengers: bookingData.seats.length,
        seat: bookingData.seats.map((s) => s.seatCode).join(", "),
      });
      sessionStorage.setItem("booking", JSON.stringify({
        ...bookingData,
        buyer: form,
        orderId: result.booking_id || "TM" + Math.floor(100000 + Math.random() * 899999),
      }));
      navigate("/confirm");
    } catch (err) {
      setError(err.response?.data?.detail || err.response?.data?.error || "বুকিং ব্যর্থ হয়েছে।");
    } finally {
      setSubmitting(false);
    }
  }

  if (!bookingData) return null;

  const isBlocked = securityAction?.action_name === "block";

  return (
    <div>
      <Header />
      <KeyboardTracker sessionId={sessionId} onBehaviorUpdate={(d) => handleBehaviorUpdate("keyboard", d)} />
      <MouseTracker sessionId={sessionId} onBehaviorUpdate={(d) => handleBehaviorUpdate("mouse", d)} />

      <main>
        <div className="back-link" onClick={() => navigate(-1)}>← আসন নির্বাচনে ফিরে যান</div>
        <div className="section-title">তথ্য দিন <small>টিকেট এই ইমেইলে পাঠানো হবে</small></div>

        <div className="seat-layout">
          <div className="form-wrap">
            <div className={`field${errors.name ? " invalid" : ""}`} id="f-name">
              <label>পুরো নাম</label>
              <input type="text" name="name" value={form.name} onChange={handleChange} placeholder="যেমন: রাহাত হোসেন" disabled={isBlocked} />
              <div className="error-text">{errors.name}</div>
            </div>
            <div className={`field${errors.email ? " invalid" : ""}`} id="f-email">
              <label>ইমেইল</label>
              <input type="email" name="email" value={form.email} onChange={handleChange} placeholder="you@example.com" disabled={isBlocked} />
              <div className="error-text">{errors.email}</div>
            </div>
            <div className={`field${errors.phone ? " invalid" : ""}`} id="f-phone">
              <label>মোবাইল নম্বর</label>
              <input type="tel" name="phone" value={form.phone} onChange={handleChange} placeholder="০১৭XXXXXXXX" disabled={isBlocked} />
              <div className="error-text">{errors.phone}</div>
            </div>
            <div className={`field${errors.card ? " invalid" : ""}`} id="f-card">
              <label>কার্ড নম্বর</label>
              <input type="text" name="card" value={form.card} onChange={handleChange} maxLength="19" placeholder="•••• •••• •••• ••••" disabled={isBlocked} />
              <div className="error-text">{errors.card}</div>
            </div>
            <div className="field-row">
              <div className={`field${errors.exp ? " invalid" : ""}`} id="f-exp">
                <label>মেয়াদ (MM/YY)</label>
                <input type="text" name="exp" value={form.exp} onChange={handleChange} maxLength="5" placeholder="১২/২৮" disabled={isBlocked} />
                <div className="error-text">{errors.exp}</div>
              </div>
              <div className={`field${errors.cvv ? " invalid" : ""}`} id="f-cvv">
                <label>CVV</label>
                <input type="text" name="cvv" value={form.cvv} onChange={handleChange} maxLength="3" placeholder="•••" disabled={isBlocked} />
                <div className="error-text">{errors.cvv}</div>
              </div>
            </div>

            <BanglaCaptcha
              sessionId={sessionId}
              onVerified={handleCaptchaVerified}
              onSecurityAction={handleSecurityAction}
              behaviorData={behaviorRef.current}
            />

            {captchaVerified && (
              <div className="captcha-ok-badge">✓ ক্যাপচা যাচাইকৃত</div>
            )}

            {error && <div className="error-banner">{error}</div>}

            <button
              className="btn btn-gold"
              style={{ width: "100%", padding: 13, marginTop: 18 }}
              disabled={submitting || isBlocked || !captchaVerified}
              onClick={handleSubmit}
            >
              {submitting ? "অর্ডার প্রক্রিয়া হচ্ছে..." : "অর্ডার নিশ্চিত করুন"}
            </button>
          </div>

          <div className="stub">
            <h3>অর্ডার সারাংশ</h3>
            <div className="stub-row"><span>{bookingData.concert.title}</span></div>
            {bookingData.seats.map((s) => (
              <div key={s.idx} className="stub-row">
                <span>আসন {s.seatCode} · {s.cat}</span>
                <strong>৳{s.price}</strong>
              </div>
            ))}
            <div className="stub-divider" />
            <div className="stub-total">
              <span>সর্বমোট</span>
              <strong>৳{bookingData.total}</strong>
            </div>
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
        .form-wrap { max-width: 520px; margin-top: 16px; }
        .field { margin-bottom: 16px; }
        .field label {
          display: block; font-size: 13px; color: rgba(242,234,223,.65); margin-bottom: 6px;
        }
        .field input {
          width: 100%; padding: 12px 14px; border-radius: 10px;
          border: 1px solid rgba(212,169,79,.25);
          background: var(--night-2); color: var(--cream);
          font-family: var(--body); font-size: 15px;
        }
        .field input:focus { outline: 2px solid var(--gold); outline-offset: 1px; }
        .field-row { display: flex; gap: 14px; }
        .field-row .field { flex: 1; }
        .error-text { color: #E07A6B; font-size: 12.5px; margin-top: 5px; display: none; }
        .field.invalid input { border-color: #E07A6B; }
        .field.invalid .error-text { display: block; }
        .error-banner {
          background: rgba(224,122,107,.12); border: 1px solid rgba(224,122,107,.3);
          color: #E07A6B; padding: 10px 14px; border-radius: 8px; font-size: 13px;
          margin-top: 12px;
        }
        .captcha-ok-badge {
          background: rgba(63,143,108,.12); border: 1px solid rgba(63,143,108,.3);
          color: var(--green-ok); padding: 10px 14px; border-radius: 8px;
          font-weight: 600; font-size: 13px; margin-top: 12px; text-align: center;
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
      `}</style>
    </div>
  );
}
