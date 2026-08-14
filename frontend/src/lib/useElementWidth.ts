"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Measure an element's width and track it across resizes.
 *
 * Used instead of Recharts' ResponsiveContainer, which measured zero inside a
 * flex/grid panel here and rendered nothing. Owning the measurement means the
 * chart's size comes from the same layout pass as everything else.
 */
export function useElementWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    const measure = () => setWidth(element.getBoundingClientRect().width);
    measure();

    const observer = new ResizeObserver(measure);
    observer.observe(element);
    window.addEventListener("resize", measure);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, []);

  return { ref, width };
}
