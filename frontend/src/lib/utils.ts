import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Find the longest common substring between two strings.
 * Used for citation text matching and highlighting.
 */
export function findLongestCommonSubstring(str1: string, str2: string): string {
  if (!str1 || !str2) return "";

  const s1 = str1.toLowerCase();
  const s2 = str2.toLowerCase();
  const m = s1.length;
  const n = s2.length;

  let maxLen = 0;
  let endIdx = 0;

  // Use a single row DP approach for memory efficiency
  const prev = new Array(n + 1).fill(0);
  const curr = new Array(n + 1).fill(0);

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (s1[i - 1] === s2[j - 1]) {
        curr[j] = prev[j - 1] + 1;
        if (curr[j] > maxLen) {
          maxLen = curr[j];
          endIdx = i;
        }
      } else {
        curr[j] = 0;
      }
    }
    // Copy curr to prev
    for (let j = 0; j <= n; j++) {
      prev[j] = curr[j];
      curr[j] = 0;
    }
  }

  return str1.substring(endIdx - maxLen, endIdx);
}
