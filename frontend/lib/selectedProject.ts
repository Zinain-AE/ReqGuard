// The project that Sources, Messages and later pages work on, chosen in the sidebar.
// Kept in localStorage (per browser, a convenience only); falls back to memory if storage is blocked.

import { useSyncExternalStore } from "react";

const KEY = "rg_project";
const EVENT = "rg-project-change";

let memoryValue: string | null = null;

export function readSelected(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return memoryValue;
  }
}

function subscribe(onChange: () => void) {
  window.addEventListener(EVENT, onChange);
  window.addEventListener("storage", onChange); // other tabs
  return () => {
    window.removeEventListener(EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

export function setSelectedProject(id: number | string | null) {
  memoryValue = id === null ? null : String(id);
  try {
    if (memoryValue === null) localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, memoryValue);
  } catch {
    // storage blocked (private window): memoryValue still works for this tab
  }
  window.dispatchEvent(new Event(EVENT));
}

// Id of the selected project, or null. Always null during server rendering.
export function useSelectedProject(): string | null {
  return useSyncExternalStore(subscribe, readSelected, () => null);
}
