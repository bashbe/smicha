/* Hebrew calendar picker — powered by @hebcal/core (CDN)
 * API: HebrewCalendar.init(containerId, hiddenInputId, initialGregorianISO)
 */
window.HebrewCalendar = (function () {

  const HEBCAL_CDN =
    "https://cdn.jsdelivr.net/npm/@hebcal/core@4.3.4/dist/bundle.min.js";

  let _loadPromise = null;
  function loadLib() {
    if (typeof hebcal !== "undefined") return Promise.resolve();
    if (_loadPromise) return _loadPromise;
    _loadPromise = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = HEBCAL_CDN;
      s.onload = resolve;
      s.onerror = () => reject(new Error("Failed to load @hebcal/core"));
      document.head.appendChild(s);
    });
    return _loadPromise;
  }

  // ── Hebrew name helpers ──────────────────────────────────────────────────

  const MONTH_NAMES_HE = {
    1: "ניסן", 2: "אייר", 3: "סיוון", 4: "תמוז",
    5: "אב", 6: "אלול", 7: "תשרי", 8: "חשוון",
    9: "כסלו", 10: "טבת", 11: "שבט", 12: "אדר", 13: "אדר ב׳",
  };

  function hebrewMonthName(m, leap) {
    if (m === 12 && leap) return "אדר א׳";
    return MONTH_NAMES_HE[m] || "";
  }

  // Hebrew numerals (gematriya) — used if hebcal.gematriya not available
  function toHebLetters(n) {
    if (!n || n <= 0) return "";
    if (typeof hebcal !== "undefined" && hebcal.gematriya) {
      return hebcal.gematriya(n);
    }
    const h = ["", "ק", "ר", "ש", "ת", "תק", "תר", "תש", "תת", "תתק"];
    const t = ["", "י", "כ", "ל", "מ", "נ", "ס", "ע", "פ", "צ"];
    const o = ["", "א", "ב", "ג", "ד", "ה", "ו", "ז", "ח", "ט"];
    const r = h[Math.floor(n / 100)];
    const rem = n % 100;
    if (rem === 15) return r + "טו";
    if (rem === 16) return r + "טז";
    return r + t[Math.floor(rem / 10)] + o[rem % 10];
  }

  // Month order Tishri-first
  function monthOrder(y) {
    return hebcal.HDate.isLeapYear(y)
      ? [7, 8, 9, 10, 11, 12, 13, 1, 2, 3, 4, 5, 6]
      : [7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6];
  }

  // ── Widget ───────────────────────────────────────────────────────────────

  async function init(containerId, hiddenInputId, initialISO) {
    const container = document.getElementById(containerId);
    const hidden = document.getElementById(hiddenInputId);
    if (!container || !hidden) return;

    // Show a spinner while the lib loads
    container.innerHTML = '<div class="hcal-loading">טוען…</div>';
    try {
      await loadLib();
    } catch (e) {
      container.innerHTML = '<div class="hcal-error">שגיאה בטעינת הלוח</div>';
      return;
    }

    const { HDate } = hebcal;

    // Today in Hebrew
    const todayHeb = new HDate(new Date());

    // Selected date
    let selectedHeb = null;
    if (initialISO) {
      const [y, m, d] = initialISO.split("-").map(Number);
      if (y && m && d) selectedHeb = new HDate(new Date(y, m - 1, d));
    }

    let viewYear  = (selectedHeb || todayHeb).getFullYear();
    let viewMonth = (selectedHeb || todayHeb).getMonth();

    function navigate(dir) {
      const order = monthOrder(viewYear);
      const idx = order.indexOf(viewMonth);
      if (dir > 0) {
        if (idx < order.length - 1) { viewMonth = order[idx + 1]; }
        else { viewYear++; viewMonth = 7; }
      } else {
        if (idx > 0) { viewMonth = order[idx - 1]; }
        else { viewYear--; viewMonth = monthOrder(viewYear).at(-1); }
      }
      render();
    }

    function selectDay(hd) {
      selectedHeb = hd;
      const g = hd.greg();
      hidden.value =
        g.getFullYear() + "-" +
        String(g.getMonth() + 1).padStart(2, "0") + "-" +
        String(g.getDate()).padStart(2, "0");
      hidden.dispatchEvent(new Event("input",  { bubbles: true }));
      hidden.dispatchEvent(new Event("change", { bubbles: true }));
      render();
    }

    function isSameDay(a, b) {
      return a.getDate()      === b.getDate() &&
             a.getMonth()     === b.getMonth() &&
             a.getFullYear()  === b.getFullYear();
    }

    function render() {
      container.innerHTML = "";
      const leap = HDate.isLeapYear(viewYear);
      const monthLen = HDate.daysInMonth(viewMonth, viewYear);

      // Header
      const hdr = document.createElement("div");
      hdr.className = "hcal-header";

      const prevBtn = document.createElement("button");
      prevBtn.type = "button"; prevBtn.className = "hcal-nav";
      prevBtn.textContent = "<"; // RTL: › = go earlier
      prevBtn.addEventListener("click", () => navigate(-1));

      const nextBtn = document.createElement("button");
      nextBtn.type = "button"; nextBtn.className = "hcal-nav";
      nextBtn.textContent = ">"; // RTL: ‹ = go later
      nextBtn.addEventListener("click", () => navigate(1));

      const title = document.createElement("div");
      title.className = "hcal-title";
      title.textContent = hebrewMonthName(viewMonth, leap) + " " +
                          toHebLetters(viewYear % 1000);

      hdr.appendChild(prevBtn);
      hdr.appendChild(title);
      hdr.appendChild(nextBtn);
      container.appendChild(hdr);

      // Day-of-week header (Sun → Sat, RTL: appears right → left)
      const DOW = ["א׳", "ב׳", "ג׳", "ד׳", "ה׳", "ו׳", "ש׳"];
      const dowRow = document.createElement("div");
      dowRow.className = "hcal-dow-row";
      DOW.forEach((l) => {
        const c = document.createElement("div"); c.textContent = l;
        dowRow.appendChild(c);
      });
      container.appendChild(dowRow);

      // Day grid
      // First day of this Hebrew month as JS Date → get day-of-week (0=Sun)
      const firstGreg = new HDate(1, viewMonth, viewYear).greg();
      const startCol = firstGreg.getDay(); // 0=Sun … 6=Sat

      const grid = document.createElement("div");
      grid.className = "hcal-grid";

      // Empty padding cells
      for (let i = 0; i < startCol; i++) {
        grid.appendChild(document.createElement("div"));
      }

      for (let day = 1; day <= monthLen; day++) {
        const hd = new HDate(day, viewMonth, viewYear);
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "hcal-day";

        const isToday    = isSameDay(hd, todayHeb);
        const isSelected = selectedHeb && isSameDay(hd, selectedHeb);
        if (isToday)    btn.classList.add("hcal-today");
        if (isSelected) btn.classList.add("hcal-selected");

        btn.textContent = toHebLetters(day);
        btn.addEventListener("click", () => selectDay(hd));
        grid.appendChild(btn);
      }
      container.appendChild(grid);

      // Selected date info line
      if (selectedHeb) {
        const g = selectedHeb.greg();
        const info = document.createElement("div");
        info.className = "hcal-selected-info";
        info.textContent =
          selectedHeb.getDate() + " " +
          hebrewMonthName(selectedHeb.getMonth(), HDate.isLeapYear(selectedHeb.getFullYear())) +
          " " + toHebLetters(selectedHeb.getFullYear() % 1000) +
          "  ·  " +
          String(g.getDate()).padStart(2, "0") + "/" +
          String(g.getMonth() + 1).padStart(2, "0") + "/" +
          g.getFullYear();
        container.appendChild(info);
      }
    }

    render();
  }

  return { init };
})();
