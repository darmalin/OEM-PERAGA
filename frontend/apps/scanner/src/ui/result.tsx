import { cn } from "@ems/ui/cn";
import { AlertTriangle, Check, CircleHelp, Repeat, X } from "lucide-react";
import { useEffect } from "react";

import type { Outcome } from "@/lib/engine";
import { NO_DECISION_REASON, REJECT_REASON, RESULT_WORD, type Tone, toneOf, VIBRATION } from "@/lib/labels";

export const RESULT_MS = 2000;

const TONE_CLASS: Record<Tone, string> = {
  first: "bg-scan-first text-on-scan-first",
  repeat: "bg-scan-repeat text-on-scan-repeat",
  rejected: "bg-scan-rejected text-on-scan-rejected",
  neutral: "bg-scan-neutral text-on-scan-neutral",
};

function view(outcome: Outcome) {
  if (outcome.kind === "result") {
    const tone = toneOf(outcome.result);
    const Icon = tone === "first" ? Check : tone === "repeat" ? Repeat : X;
    const who = [outcome.firstName, outcome.registrationCode].filter(Boolean).join(" · ");
    return {
      tone,
      Icon,
      word: RESULT_WORD[outcome.result],
      lines: [REJECT_REASON[outcome.result], who || undefined],
      provisional: outcome.provisional,
    };
  }
  if (outcome.kind === "undecided") {
    return {
      tone: "neutral" as const,
      Icon: CircleHelp,
      word: "NOT CHECKED",
      lines: [NO_DECISION_REASON[outcome.reason], "Scan saved. The result comes when the device is online."],
      provisional: false,
    };
  }
  return { tone: "neutral" as const, Icon: AlertTriangle, word: "CANNOT CHECK", lines: [outcome.message], provisional: false };
}

/** Full-screen result for 2 s, tap to dismiss early (DESIGN.md "Scanner"). */
export function Result({ outcome, onDone }: { outcome: Outcome; onDone: () => void }) {
  const v = view(outcome);

  useEffect(() => {
    navigator.vibrate?.(VIBRATION[v.tone]);
    const t = setTimeout(onDone, RESULT_MS);
    return () => clearTimeout(t);
  }, [outcome, onDone, v.tone]);

  return (
    <button
      type="button"
      onClick={onDone}
      aria-label="Dismiss result"
      className={cn("fixed inset-0 z-10 flex flex-col items-center justify-center gap-4 px-6 text-center", TONE_CLASS[v.tone])}
    >
      <v.Icon aria-hidden className="size-24" strokeWidth={2.5} />
      <div role="alert" className="space-y-3">
        <p className="text-result font-bold tracking-wide">{v.word}</p>
        {v.lines.filter(Boolean).map((line) => (
          <p key={line} className="text-xl font-medium">
            {line}
          </p>
        ))}
        {v.provisional && <p className="text-lg">Provisional, will confirm when online.</p>}
      </div>
    </button>
  );
}
