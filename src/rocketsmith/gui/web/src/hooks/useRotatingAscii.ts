import { useState, useEffect } from "react";
import frames from "@/assets/rocket-frames.json";

const FPS = 30;
const INTERVAL_MS = 1000 / FPS;

/**
 * Cycles through pre-rendered ASCII frames of a rotating rocket.
 * Returns the current frame string.
 */
export function useRotatingAscii(): string {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setIndex((prev) => (prev + 1) % frames.length);
    }, INTERVAL_MS);
    return () => clearInterval(id);
  }, []);

  return frames[index];
}
