# ADR 0017: Camera capture, DL photo step, problem reports, browser-built PDF

Status: accepted (Oct 2026)

## Context
Doctors take the photos with a dental camera (a USB camera with built-in lights) plugged into a PC,
tablet or phone. The deep-learning classifier will need a close-up photo, the optical analysis needs a
red-light and a blue-light photo, and doctors need to hand over a readable report and tell us when
something breaks.

## Decisions
1. **One reusable photo picker** (`capture.js`): "Use camera" opens a live preview with the browser's
   `getUserMedia`, a camera list (dental cameras appear as ordinary webcams) with Refresh, and "Take
   photo", which saves one JPEG frame. "Or choose an image file" stays for uploads. The chosen camera is
   remembered on that device. The camera is released after each capture and whenever the screen changes.
   Rejected: `<input capture>` alone (opens the phone's own camera app, ignores an external camera).
2. **DL photo step.** New `POST /diagnoses/{id}/dl-upload-url` stores the photo under a server-chosen key
   (`diagnoses/<id>/dl_image`, column `dl_image_s3_key` already existed). The model is not connected, so
   the photo is only stored and the provisional diagnosis is still picked by the doctor. When the model
   exists, a classify endpoint reads this key and fills the provisional diagnosis; the UI order stays.
3. **Problem reports.** `POST /problem-reports` stores the message in `problem_reports` plus automatic
   context (app version, screen, browser, last error shown; no patient data). The API prints
   `PROBLEM_REPORT id=...` (never the text); a CloudWatch metric filter and alarm email the owner through the
   existing alerts topic. Rejected for now: emailing the text itself (needs SNS publish rights and the text may
   hold patient details by mistake).
4. **PDF built in the browser** (jsPDF 4.2.1, MIT, vendored): the case data and photos are already on the
   page, nothing extra is sent anywhere, and the Lambda package stays small. Photos are fetched from their
   signed links and re-encoded as <=1200 px JPEGs, which needs the images bucket to allow GET from the site
   (CORS). Layout and wording are a draft (the footer says so); dentists and a lawyer must approve them.
5. The old "Download patient data" button is now "Export all data (JSON)" (owner/portability copy, ADR 0016).

## Consequences
- Needs HTTPS and camera permission; the browser asks once per site and shows a readable message if blocked.
- jsPDF's built-in fonts are Latin only: non-Latin patient names (Telugu, Hindi) print as "?" in the PDF
  until a Unicode font is embedded (about 0.5 to 1 MB per script). Open item.
- PDF generation is client-side, so it is not audited separately; opening the case already is (`diagnosis.view`).
- Photo capture quality depends on the camera and lighting; the app does not judge photo quality yet (needs
  dentists' definition of a usable photo).
