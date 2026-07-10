// Shared behaviour for the admin question editor card, used by both
// admin/questions.html and admin/validate.html so the two tabs stay in sync.
(function () {
  const form = document.getElementById("qform") || document.getElementById("vform");
  if (!form) return;

  const qtypeSel = document.getElementById("qtype");

  // ── Auto-growing textareas: option text, dropdown choices, decisor name/answer ──
  // These look like single-line fields but must never hide overflow text the way a
  // real <input> would on a narrow screen — grow to fit their content instead.
  // Elements inside a display:none ancestor always report scrollHeight 0, so this
  // must run AFTER refreshType() has made the active type-block visible, and again
  // whenever the type changes (a field hidden at load time was never sized).
  function autoGrow(el) {
    el.style.height = "auto";
    el.style.height = el.scrollHeight + "px";
  }
  function autoGrowAll() {
    form.querySelectorAll("textarea.auto-grow").forEach(autoGrow);
  }
  form.addEventListener("input", (e) => {
    if (e.target.classList && e.target.classList.contains("auto-grow")) autoGrow(e.target);
  });

  function refreshType() {
    const t = qtypeSel.value;
    document.querySelectorAll(".type-block").forEach((b) => {
      b.style.display = b.dataset.type.split(" ").includes(t) ? "" : "none";
    });
    autoGrowAll();
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
      '<textarea name="option_text" rows="1" class="flex-1 choice-text-input auto-grow" placeholder="תשובה"></textarea>' +
      '<span class="key">' + (document.querySelectorAll("#options .option-row").length + 1) + '</span>' +
      '<button type="button" class="btn btn-outline" onclick="this.closest(\'.option-row\').remove()">🗑</button>';
    document.getElementById("options").appendChild(div);
  }

  function addChoice() {
    const div = document.createElement("div");
    div.className = "row gap-2 opinions-field-row";
    div.style.marginBottom = "0.5rem";
    div.innerHTML = '<textarea name="dropdown_choice" rows="1" class="flex-1 auto-grow" placeholder="לדוגמה: מותר"></textarea><button type="button" class="btn btn-outline" onclick="this.parentNode.remove()">🗑</button>';
    document.getElementById("choices").appendChild(div);
  }

  function addDecisor() {
    const n = document.querySelectorAll("[name=decisor_id]").length + 1;
    const div = document.createElement("div");
    div.className = "decisor-row";
    div.innerHTML = '<div class="row between decisor-row-head">' +
      '<input name="decisor_id" value="dec_' + n + '" class="decisor-id-input" />' +
      '<button type="button" class="btn btn-outline" onclick="this.closest(\'.decisor-row\').remove()">🗑</button>' +
      '</div>' +
      '<textarea name="decisor_name" rows="1" class="auto-grow" placeholder="שם הפוסק"></textarea>' +
      '<textarea name="decisor_correct" rows="1" class="auto-grow" placeholder="עמדה נכונה"></textarea>';
    document.getElementById("decisors").appendChild(div);
  }
  // exposed for the inline onclick="addOption()" / addChoice() / addDecisor() handlers
  window.addOption = addOption;
  window.addChoice = addChoice;
  window.addDecisor = addDecisor;

  // ── Parcours/sujet preview text (siman, seif and tags are edited directly in the card) ──
  const PARCOURS_LABELS = { bassar_bechalav: "בשר בחלב" };
  function updateParcoursSubject() {
    const el = document.getElementById("admin-card-parcours-subject");
    if (!el) return;
    const parcoursSel = form.querySelector("[name=parcours]");
    const subjectInput = form.querySelector("[name=subject]");
    const parts = [];
    if (parcoursSel && parcoursSel.value) parts.push(PARCOURS_LABELS[parcoursSel.value] || parcoursSel.value);
    if (subjectInput && subjectInput.value) parts.push(subjectInput.value);
    el.textContent = parts.join(" · ");
  }
  ["parcours", "subject"].forEach((name) => {
    const field = form.querySelector(`[name=${name}]`);
    if (field) field.addEventListener("input", updateParcoursSubject);
  });
  updateParcoursSubject();

  // ── Editable tag pills in the card ──
  const tagsHidden = document.getElementById("admin-tags-hidden");
  const tagsWrap = document.getElementById("admin-card-tags");
  const tagInput = document.getElementById("admin-tag-input");

  function syncTagsHidden() {
    if (!tagsHidden || !tagsWrap) return;
    const tags = Array.from(tagsWrap.querySelectorAll(".card-tag-editable")).map((el) => el.dataset.tag);
    tagsHidden.value = tags.join(",");
  }

  function addTagPill(text) {
    const value = text.trim();
    if (!value || !tagsWrap) return;
    const existing = Array.from(tagsWrap.querySelectorAll(".card-tag-editable")).map((el) => el.dataset.tag);
    if (existing.includes(value)) return;
    const span = document.createElement("span");
    span.className = "card-tag card-tag-editable";
    span.dataset.tag = value;
    span.textContent = value;
    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "card-tag-remove";
    removeBtn.textContent = "×";
    removeBtn.addEventListener("click", () => removeTag(removeBtn));
    span.appendChild(removeBtn);
    tagsWrap.insertBefore(span, tagInput);
    syncTagsHidden();
  }

  function removeTag(btn) {
    const pill = btn.closest(".card-tag-editable");
    if (pill) pill.remove();
    syncTagsHidden();
  }
  window.removeTag = removeTag;

  if (tagsWrap) {
    tagsWrap.querySelectorAll(".card-tag-editable").forEach((pill) => {
      pill.dataset.tag = pill.dataset.tag || pill.textContent.replace("×", "").trim();
      const btn = pill.querySelector(".card-tag-remove");
      if (btn) btn.addEventListener("click", () => removeTag(btn));
    });
  }
  if (tagInput) {
    tagInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === ",") {
        e.preventDefault();
        addTagPill(tagInput.value);
        tagInput.value = "";
      } else if (e.key === "Backspace" && !tagInput.value && tagsWrap) {
        const pills = tagsWrap.querySelectorAll(".card-tag-editable");
        if (pills.length) removeTag(pills[pills.length - 1].querySelector(".card-tag-remove"));
      }
    });
    tagInput.addEventListener("blur", () => {
      if (tagInput.value.trim()) { addTagPill(tagInput.value); tagInput.value = ""; }
    });
  }

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
