// Shared behaviour for the admin question editor card, used by both
// admin/questions.html and admin/validate.html so the two tabs stay in sync.
(function () {
  const form = document.getElementById("qform") || document.getElementById("vform");
  if (!form) return;

  const qtypeSel = document.getElementById("qtype");

  function refreshType() {
    const t = qtypeSel.value;
    document.querySelectorAll(".type-block").forEach((b) => {
      b.style.display = b.dataset.type.split(" ").includes(t) ? "" : "none";
    });
  }
  qtypeSel.addEventListener("change", refreshType);
  refreshType();

  form.addEventListener("submit", () => {
    // map opinions question text into the shared question_text field
    if (qtypeSel.value === "multiple_opinions_dropdown") {
      const op = form.querySelector("[name=question_text_op]");
      const qt = form.querySelector("[name=question_text]");
      if (qt && op) qt.value = op.value;
    }
    // compute correct_options from the checked checkboxes' positions among option rows
    const rows = Array.from(document.querySelectorAll("#options .option-row"));
    const correctIndices = [];
    rows.forEach((row, i) => {
      const cb = row.querySelector(".option-correct-checkbox");
      if (cb && cb.checked) correctIndices.push(i + 1);
    });
    const hidden = document.getElementById("correct_options_hidden");
    if (hidden) hidden.value = JSON.stringify(correctIndices);
  });

  function addOption() {
    const div = document.createElement("div");
    div.className = "choice option-row";
    div.innerHTML = '<input type="checkbox" class="option-correct-checkbox" style="width:1.1rem;height:1.1rem;flex-shrink:0;" />' +
      '<input name="option_text" class="flex-1 choice-text-input" placeholder="תשובה" />' +
      '<span class="key">' + (document.querySelectorAll("#options .option-row").length + 1) + '</span>' +
      '<button type="button" class="btn btn-outline" onclick="this.closest(\'.option-row\').remove()">🗑</button>';
    document.getElementById("options").appendChild(div);
  }

  function addChoice() {
    const div = document.createElement("div");
    div.className = "row gap-2";
    div.style.marginBottom = "0.5rem";
    div.innerHTML = '<input name="dropdown_choice" class="flex-1" placeholder="לדוגמה: מותר" /><button type="button" class="btn btn-outline" onclick="this.parentNode.remove()">🗑</button>';
    document.getElementById("choices").appendChild(div);
  }

  function addDecisor() {
    const n = document.querySelectorAll("[name=decisor_id]").length + 1;
    const div = document.createElement("div");
    div.className = "row gap-2";
    div.style.marginBottom = "0.5rem";
    div.innerHTML = '<input name="decisor_id" value="dec_' + n + '" style="width:6rem;" /><input name="decisor_name" class="flex-1" placeholder="שם הפוסק" /><input name="decisor_correct" class="flex-1" placeholder="עמדה נכונה" /><button type="button" class="btn btn-outline" onclick="this.parentNode.remove()">🗑</button>';
    document.getElementById("decisors").appendChild(div);
  }
  // exposed for the inline onclick="addOption()" / addChoice() / addDecisor() handlers
  window.addOption = addOption;
  window.addChoice = addChoice;
  window.addDecisor = addDecisor;

  // ── Question card preview (mirrors the student player card: meta line + tags) ──
  const PARCOURS_LABELS = { bassar_bechalav: "בשר בחלב" };
  function toHebNum(n) {
    if (!n || n <= 0) return String(n);
    const h = ["", "ק", "ר", "ש", "ת", "תק", "תר", "תש", "תת", "תתק"];
    const t = ["", "י", "כ", "ל", "מ", "נ", "ס", "ע", "פ", "צ"];
    const o = ["", "א", "ב", "ג", "ד", "ה", "ו", "ז", "ח", "ט"];
    let r = h[Math.floor(n / 100)];
    const rem = n % 100;
    if (rem === 15) return r + "טו";
    if (rem === 16) return r + "טז";
    r += t[Math.floor(rem / 10)] + o[rem % 10];
    return r;
  }
  function updateCardPreview() {
    const metaEl = document.getElementById("admin-card-meta");
    const tagsEl = document.getElementById("admin-card-tags");
    if (!metaEl || !tagsEl) return;
    const parcoursSel = form.querySelector("[name=parcours]");
    const subjectInput = form.querySelector("[name=subject]");
    const simanInput = form.querySelector("[name=siman]");
    const seifInput = form.querySelector("[name=seif]");
    const tagsInput = form.querySelector("[name=tags]");
    const parts = [];
    if (parcoursSel && parcoursSel.value) parts.push(PARCOURS_LABELS[parcoursSel.value] || parcoursSel.value);
    if (subjectInput && subjectInput.value) parts.push(subjectInput.value);
    if (simanInput && simanInput.value) parts.push("סימן " + toHebNum(Number(simanInput.value)));
    if (seifInput && seifInput.value) parts.push("סעיף " + toHebNum(Number(seifInput.value)));
    metaEl.textContent = parts.join(" · ");

    tagsEl.innerHTML = "";
    (tagsInput && tagsInput.value ? tagsInput.value.split(",") : [])
      .map((t) => t.trim()).filter(Boolean)
      .forEach((t) => {
        const span = document.createElement("span");
        span.className = "card-tag";
        span.textContent = t;
        tagsEl.appendChild(span);
      });
  }
  ["parcours", "subject", "siman", "seif", "tags"].forEach((name) => {
    const field = form.querySelector(`[name=${name}]`);
    if (field) field.addEventListener("input", updateCardPreview);
  });
  updateCardPreview();

  // ── Highlight the correct answer(s) like the revealed state of the player card ──
  function refreshOptionCorrect() {
    document.querySelectorAll("#options .option-row").forEach((row) => {
      const cb = row.querySelector(".option-correct-checkbox");
      row.classList.toggle("is-correct", !!(cb && cb.checked));
    });
  }
  const optionsWrap = document.getElementById("options");
  if (optionsWrap) {
    optionsWrap.addEventListener("change", (e) => {
      if (e.target.classList.contains("option-correct-checkbox")) refreshOptionCorrect();
    });
  }

  function refreshTFCorrect() {
    document.querySelectorAll('.type-block[data-type="true_false"] .choice-tf').forEach((row) => {
      const radio = row.querySelector('input[type="radio"]');
      row.classList.toggle("is-correct", !!(radio && radio.checked));
    });
  }
  document.querySelectorAll('.type-block[data-type="true_false"] input[name="correct_answer"]').forEach((r) => {
    r.addEventListener("change", refreshTFCorrect);
  });
})();
