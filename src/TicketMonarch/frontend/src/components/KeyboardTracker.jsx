import { useEffect, useRef } from "react";

export default function KeyboardTracker({ sessionId, onBehaviorUpdate }) {
  const eventsRef = useRef([]);
  const lastKeyTimeRef = useRef(null);

  useEffect(() => {
    const handleKeyDown = (e) => {
      const now = Date.now();
      const holdStart = now;

      eventsRef.current.push({
        type: "keydown",
        key: e.key,
        code: e.code,
        timestamp: now,
        interval: lastKeyTimeRef.current ? now - lastKeyTimeRef.current : null,
      });

      lastKeyTimeRef.current = now;

      const handler = (upEvent) => {
        if (upEvent.key === e.key) {
          const holdDuration = Date.now() - holdStart;
          eventsRef.current.push({
            type: "keyup",
            key: e.key,
            code: e.code,
            timestamp: Date.now(),
            hold_duration: holdDuration,
          });
          document.removeEventListener("keyup", handler);
        }
      };
      document.addEventListener("keyup", handler);
    };

    const handlePaste = (e) => {
      eventsRef.current.push({
        type: "paste",
        timestamp: Date.now(),
        paste_length: (e.clipboardData || window.clipboardData).getData("text").length,
      });
    };

    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("paste", handlePaste);

    const interval = setInterval(() => {
      if (eventsRef.current.length > 0) {
        onBehaviorUpdate?.({
          events: [...eventsRef.current],
          total_keystrokes: eventsRef.current.filter((e) => e.type === "keydown").length,
          avg_hold_duration: calculateAvgHold(eventsRef.current),
          typing_rhythm_std: calculateRhythmStd(eventsRef.current),
          has_paste: eventsRef.current.some((e) => e.type === "paste"),
        });
        eventsRef.current = [];
      }
    }, 2000);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("paste", handlePaste);
      clearInterval(interval);
    };
  }, [sessionId, onBehaviorUpdate]);

  return null;
}

function calculateAvgHold(events) {
  const holds = events
    .filter((e) => e.type === "keyup" && e.hold_duration != null)
    .map((e) => e.hold_duration);
  if (holds.length === 0) return 0;
  return holds.reduce((a, b) => a + b, 0) / holds.length;
}

function calculateRhythmStd(events) {
  const intervals = events
    .filter((e) => e.type === "keydown" && e.interval != null)
    .map((e) => e.interval);
  if (intervals.length < 2) return 0;
  const mean = intervals.reduce((a, b) => a + b, 0) / intervals.length;
  const variance =
    intervals.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) /
    intervals.length;
  return Math.sqrt(variance);
}
