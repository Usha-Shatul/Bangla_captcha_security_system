import { useEffect, useRef } from "react";

const MIN_MOVEMENT_PX = 1;

export default function MouseTracker({ sessionId, onBehaviorUpdate }) {
  const eventsRef = useRef([]);
  const positionsRef = useRef([]);
  const lastMoveTimeRef = useRef(null);
  const lastPosRef = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const handleMouseMove = (e) => {
      const now = Date.now();
      const prev = lastMoveTimeRef.current;
      const dx = e.movementX;
      const dy = e.movementY;
      const distFromLast = Math.sqrt(
        (e.clientX - lastPosRef.current.x) ** 2 +
        (e.clientY - lastPosRef.current.y) ** 2
      );

      if (distFromLast < MIN_MOVEMENT_PX) return;

      const speed = prev ? Math.sqrt(dx * dx + dy * dy) / ((now - prev) / 1000) : 0;

      positionsRef.current.push({ x: e.clientX, y: e.clientY, t: now });

      eventsRef.current.push({
        type: "mousemove",
        x: e.clientX,
        y: e.clientY,
        movement_x: dx,
        movement_y: dy,
        speed,
        timestamp: now,
      });

      lastMoveTimeRef.current = now;
      lastPosRef.current = { x: e.clientX, y: e.clientY };
    };

    const handleClick = (e) => {
      eventsRef.current.push({
        type: "click",
        x: e.clientX,
        y: e.clientY,
        button: e.button,
        timestamp: Date.now(),
      });
    };

    const handleScroll = (e) => {
      eventsRef.current.push({
        type: "scroll",
        scroll_x: e.target.scrollLeft || 0,
        scroll_y: e.target.scrollTop || 0,
        timestamp: Date.now(),
      });
    };

    const handleContextMenu = (e) => {
      e.preventDefault();
      eventsRef.current.push({
        type: "contextmenu",
        x: e.clientX,
        y: e.clientY,
        timestamp: Date.now(),
      });
    };

    document.addEventListener("mousemove", handleMouseMove, { passive: true });
    document.addEventListener("click", handleClick);
    document.addEventListener("scroll", handleScroll, { passive: true });
    document.addEventListener("contextmenu", handleContextMenu);

    const interval = setInterval(() => {
      if (eventsRef.current.length > 0) {
        const positions = positionsRef.current;
        onBehaviorUpdate?.({
          events: [...eventsRef.current],
          total_clicks: eventsRef.current.filter((e) => e.type === "click").length,
          avg_mouse_speed: calculateAvgSpeed(eventsRef.current),
          mouse_path_length: calculatePathLength(positions),
          idle_periods: detectIdlePeriods(positions),
          has_context_menu: eventsRef.current.some((e) => e.type === "contextmenu"),
        });
        eventsRef.current = [];
        positionsRef.current = [];
      }
    }, 2000);

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("click", handleClick);
      document.removeEventListener("scroll", handleScroll);
      document.removeEventListener("contextmenu", handleContextMenu);
      clearInterval(interval);
    };
  }, [sessionId, onBehaviorUpdate]);

  return null;
}

function calculateAvgSpeed(events) {
  const speeds = events
    .filter((e) => e.type === "mousemove" && e.speed > 0)
    .map((e) => e.speed);
  if (speeds.length === 0) return 0;
  return speeds.reduce((a, b) => a + b, 0) / speeds.length;
}

function calculatePathLength(positions) {
  if (positions.length < 2) return 0;
  let length = 0;
  for (let i = 1; i < positions.length; i++) {
    const dx = positions[i].x - positions[i - 1].x;
    const dy = positions[i].y - positions[i - 1].y;
    length += Math.sqrt(dx * dx + dy * dy);
  }
  return length;
}

function detectIdlePeriods(positions) {
  if (positions.length < 2) return 0;
  let idles = 0;
  for (let i = 1; i < positions.length; i++) {
    if (positions[i].t - positions[i - 1].t > 1000) {
      idles++;
    }
  }
  return idles;
}
