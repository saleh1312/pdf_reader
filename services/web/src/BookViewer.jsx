import { useEffect, useRef, useState } from "react";
import { getDocument, GlobalWorkerOptions } from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

GlobalWorkerOptions.workerSrc = workerUrl;

export default function BookViewer({ url }) {
  const host = useRef(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const parent = host.current;
    let cancelled = false;
    setError("");
    const task = getDocument({ url, disableRange: true, disableStream: true });
    task.promise
      .then(async (pdf) => {
        parent.replaceChildren();
        for (let number = 1; number <= pdf.numPages; number += 1) {
          if (cancelled) return;
          const page = await pdf.getPage(number);
          const viewport = page.getViewport({ scale: 1.3 });
          const canvas = document.createElement("canvas");
          canvas.width = viewport.width;
          canvas.height = viewport.height;
          canvas.className = "page";
          parent.appendChild(canvas);
          await page.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || "The book could not be opened.");
      });
    return () => {
      cancelled = true;
      task.destroy();
    };
  }, [url]);

  return (
    <>
      {error && <p className="empty">{error}</p>}
      <div className="viewer" ref={host} hidden={Boolean(error)} />
    </>
  );
}
