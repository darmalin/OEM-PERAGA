import { BrowserQRCodeReader, type IScannerControls } from "@zxing/browser";
import { useEffect, useRef, useState } from "react";

/** Camera viewfinder that reports every decoded QR text. Stops while `paused`. */
export function Camera({ paused, onCode }: { paused: boolean; onCode: (text: string) => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const handler = useRef(onCode);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    handler.current = onCode;
  }, [onCode]);

  useEffect(() => {
    const el = video.current;
    if (paused || !el) return;
    let controls: IScannerControls | null = null;
    let cancelled = false;
    const reader = new BrowserQRCodeReader(undefined, { delayBetweenScanAttempts: 150 });
    reader
      .decodeFromConstraints({ audio: false, video: { facingMode: "environment" } }, el, (result) => {
        if (result) handler.current(result.getText());
      })
      .then((c) => {
        if (cancelled) c.stop();
        else {
          controls = c;
          setError(null);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(cameraError(e));
      });
    return () => {
      cancelled = true;
      controls?.stop();
    };
  }, [paused]);

  return (
    <div className="relative flex-1 overflow-hidden bg-black">
      <video ref={video} muted playsInline className="absolute inset-0 size-full object-cover" />
      {error ? (
        <p role="alert" className="absolute inset-x-4 top-1/2 -translate-y-1/2 rounded-control bg-bg p-4 text-center">
          {error}
        </p>
      ) : (
        <div aria-hidden className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="aspect-square w-2/3 max-w-80 rounded-card border-4 border-white/80" />
        </div>
      )}
    </div>
  );
}

function cameraError(e: unknown): string {
  const name = e instanceof Error ? e.name : "";
  if (name === "NotAllowedError" || name === "SecurityError")
    return "Camera access is blocked. Allow the camera for this site, or enter codes manually.";
  if (name === "NotFoundError" || name === "OverconstrainedError")
    return "No camera found on this device. Enter codes manually.";
  return "The camera could not start. Enter codes manually.";
}
