// Builds the one-case PDF report in the browser (jsPDF, vendored). Nothing leaves the page: the
// case data and photos are already loaded, and the file is saved straight to the device.
//
// Draft layout. The wording of scores, advice and the disclaimer has NOT been reviewed by the
// dentists or a lawyer yet; the footer says so on every page.
//
// Limitation: jsPDF's built-in fonts cover Latin text only. Characters outside it (for example
// Telugu or Hindi script) print as "?" until a Unicode font is added.
(function () {
  "use strict";
  const PAGE_W = 210, PAGE_H = 297, MARGIN = 16;
  const CONTENT_W = PAGE_W - 2 * MARGIN;
  const FOOTER_Y = PAGE_H - 10;

  const latin = (s) => String(s == null || s === "" ? "-" : s)
    .replace(/[^ -~ -ÿ‘’“”–—•]/g, "?");

  // data: { generatedAt: Date, doctorEmail, patient, diagnosis, images: [{label, dataUrl, w, h}] }
  function build(data) {
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF({ unit: "mm", format: "a4" });
    const d = data.diagnosis, p = data.patient;
    let y = MARGIN;

    const ensure = (needed) => { if (y + needed > FOOTER_Y - 6) { doc.addPage(); y = MARGIN; } };
    const heading = (text) => {
      ensure(14);
      y += 4;
      doc.setFont("helvetica", "bold"); doc.setFontSize(12); doc.setTextColor(11, 110, 79);
      doc.text(latin(text), MARGIN, y);
      doc.setDrawColor(200); doc.line(MARGIN, y + 1.5, PAGE_W - MARGIN, y + 1.5);
      y += 7;
      doc.setTextColor(30);
    };
    const rows = (pairs) => {
      doc.setFontSize(10);
      for (const [k, v] of pairs) {
        const lines = doc.splitTextToSize(latin(v), CONTENT_W - 52);
        ensure(lines.length * 5 + 2);
        doc.setFont("helvetica", "bold"); doc.setTextColor(90);
        doc.text(latin(k), MARGIN, y);
        doc.setFont("helvetica", "normal"); doc.setTextColor(20);
        doc.text(lines, MARGIN + 52, y);
        y += lines.length * 5 + 1.5;
      }
    };

    doc.setFont("helvetica", "bold"); doc.setFontSize(18); doc.setTextColor(20);
    doc.text("Dr. Oroscope", MARGIN, y + 4);
    doc.setFont("helvetica", "normal"); doc.setFontSize(11); doc.setTextColor(90);
    doc.text("Oral screening report", MARGIN, y + 10);
    doc.setFontSize(9);
    doc.text("Generated " + data.generatedAt.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }), PAGE_W - MARGIN, y + 4, { align: "right" });
    y += 14;

    heading("Patient");
    rows([["Name", p.name], ["Age", p.age != null ? String(p.age) : "-"], ["Gender", p.gender], ["Contact", p.contact_number]]);

    heading("Case");
    rows([["Case date", data.caseDate], ["Status", d.status], ["Case ID", d.id]]);

    heading("Clinical findings");
    rows([["Ulcer", d.ulcer], ["Patch", d.patch], ["Growth", d.growth], ["Mucosal condition", d.mucosal_condition],
      ["Sharp objects", d.sharp_objects], ["Pigmentation", d.pigmentation], ["Symptoms", d.symptoms],
      ["Habits", d.habits], ["Oral mapping", d.oral_mapping]]);

    heading("Result");
    rows([["Provisional diagnosis", d.provisional_diagnosis || "Not recorded"],
      ["Differential diagnosis", d.rules_match_result || "Not looked up"],
      ["Advice", d.advise || "-"],
      ["Image analysis band", d.image_analysis_band || "Not analysed"],
      ["Deviation index", typeof d.optical_deviation_index === "number" ? d.optical_deviation_index.toFixed(4) : "-"],
      ["Final score", d.final_score != null ? d.final_score + " / 5" : "Not available"]]);

    ensure(68); // keep the heading together with the first row of photos
    heading("Photos");
    const imgs = data.images;
    const gap = 4, cellW = (CONTENT_W - gap * 2) / 3, maxH = 55;
    let x = MARGIN, rowH = 0;
    doc.setFontSize(9);
    for (let i = 0; i < imgs.length; i++) {
      const im = imgs[i];
      let w = cellW, hgt = 20;
      if (im.dataUrl) {
        hgt = Math.min(maxH, cellW * (im.h / im.w));
        w = hgt === maxH ? maxH * (im.w / im.h) : cellW;
      }
      if (i % 3 === 0) { ensure(maxH + 10); x = MARGIN; rowH = 0; }
      doc.setFont("helvetica", "normal"); doc.setTextColor(90);
      doc.text(latin(im.label), x, y);
      if (im.dataUrl) {
        doc.addImage(im.dataUrl, "JPEG", x, y + 2, w, hgt, undefined, "FAST");
      } else {
        doc.setDrawColor(200); doc.rect(x, y + 2, cellW, 20);
        doc.text("Photo not available", x + 2, y + 11);
        if (im.reason) doc.text("(" + latin(im.reason) + ")", x + 2, y + 16);
      }
      rowH = Math.max(rowH, hgt + 6);
      x += cellW + gap;
      if (i % 3 === 2 || i === imgs.length - 1) y += rowH + 4;
    }

    // footer on every page
    const pages = doc.getNumberOfPages();
    for (let i = 1; i <= pages; i++) {
      doc.setPage(i);
      doc.setDrawColor(200); doc.line(MARGIN, FOOTER_Y - 4, PAGE_W - MARGIN, FOOTER_Y - 4);
      doc.setFont("helvetica", "normal"); doc.setFontSize(7.5); doc.setTextColor(110);
      doc.text("Screening aid, not a diagnosis. Prototype report: layout and wording not yet reviewed clinically or legally.", MARGIN, FOOTER_Y);
      doc.text("Prepared by " + latin(data.doctorEmail) + "   Page " + i + " of " + pages, PAGE_W - MARGIN, FOOTER_Y + 4, { align: "right" });
    }
    return doc;
  }

  window.OroscopeReport = { build };
})();
