// Chapter question player
(function () {
  const root = document.getElementById("player");
  const origQuestions = JSON.parse(root.dataset.questions);

  // Mélange l'ordre des options à chaque affichage (nouveau tirage à chaque
  // session) pour empêcher l'étudiant de mémoriser la position visuelle de
  // la bonne réponse plutôt que la réponse elle-même. Ne touche pas aux
  // "key" des options : la correction se fait toujours par clé, jamais par
  // position.
  function shuffleInPlace(arr) {
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
  }
  origQuestions.forEach((q) => {
    if (q.normalized && q.normalized.type === "multiple_choice" && Array.isArray(q.normalized.choices)) {
      shuffleInPlace(q.normalized.choices);
    }
  });

  const cfg = {
    parcours: root.dataset.parcoursUrl,
    home: root.dataset.homeUrl,
    answer: root.dataset.answerUrl,
    report: root.dataset.reportUrl,
    adminEditUrl: root.dataset.adminEditUrl,
    canSuggest: root.dataset.canSuggest === "true",
    todayStats: root.dataset.todayStatsUrl,
    subject: root.dataset.subject,
    siman: root.dataset.siman,
    mode: root.dataset.mode || "study",
    modeLabel: root.dataset.modeLabel || "חזרה",
    back: root.dataset.backUrl || root.dataset.parcoursUrl,
  };

  const isRevision = root.dataset.revision === "true";

  const queue = origQuestions.slice();
  const origIdxMap = {};
  origQuestions.forEach((q, i) => { origIdxMap[q.id] = i; });

  const state = {
    idx: 0,
    combo: 0,
    sessionPoints: 0,
    correctCount: 0,
    dailyBonus: 0,
    dailyBonusParcours: [],
    results: new Array(origQuestions.length).fill(null),
    chosen: null,
    multiSelected: new Set(),
    opinionAnswers: {},
    activeOpinionId: null,
    revealed: false,
    feedback: null,
    showNext: false,
    start: Date.now(),
    reportedIds: new Set(),
  };

  const refs = {};

  // The explanation/next-button bar is fixed to the screen, so it must live outside
  // #player: an ancestor (#player itself) carries .animate-slide-up, whose keyframe
  // leaves a lingering `transform` (fill-mode "both"), which would turn it into a
  // containing block for position:fixed descendants and break the fixed positioning.
  function removeExpPanel() {
    const existing = document.querySelector("body > .player-exp");
    if (existing) existing.remove();
    document.body.classList.remove("has-player-exp");
    document.body.style.removeProperty("--player-exp-height");
  }

  // Reserve exactly as much scroll space as the fixed bottom panel actually takes,
  // so revealed content (e.g. the correct answer on a wrong opinions row) never
  // renders hidden behind it — see body.has-player-exp .container in styles.css.
  function updateExpHeight() {
    const exp = document.querySelector("body > .player-exp");
    if (!exp) return;
    document.body.style.setProperty("--player-exp-height", exp.offsetHeight + "px");
  }

  // ── helpers ────────────────────────────────────────────────────────────────

  function el(tag, cls, ...children) {
    // cls can be a string (className) or an object of props
    const node = document.createElement(tag);
    if (typeof cls === "string") {
      if (cls) node.className = cls;
    } else if (cls && typeof cls === "object") {
      for (const [k, v] of Object.entries(cls)) {
        if (k === "class") node.className = v;
        else if (k === "style") node.style.cssText = v;
        else if (k === "html") node.innerHTML = v;
        else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
        else if (v !== null && v !== undefined) node.setAttribute(k, v);
      }
    }
    for (const c of children.flat()) {
      if (c === null || c === undefined) continue;
      node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    }
    return node;
  }

  // Icônes SVG inline (miroir de templates/_icons.html) — pas d'emojis.
  const ICON_PATHS = {
    flame: '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/>',
    coin: '<circle cx="12" cy="12" r="9"/><path d="M12 7v1m0 8v1M9.5 9.5C9.5 8.67 10.17 8 11 8h2a1.5 1.5 0 0 1 0 3h-2a1.5 1.5 0 0 0 0 3h2a1.5 1.5 0 0 0 0-3"/>',
    check: '<polyline points="20 6 9 17 4 12"/>',
    x: '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
    flag: '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/>',
  };
  function icon(name, size) {
    size = size || 16;
    return el("span", {
      style: "display:inline-flex;align-items:center;",
      html: '<svg width="' + size + '" height="' + size + '" viewBox="0 0 24 24" fill="none" ' +
        'stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" ' +
        'aria-hidden="true">' + ICON_PATHS[name] + '</svg>',
    });
  }

  function comboLabel(combo) {
    if (combo < 2) return null;
    if (combo >= 5) return "×" + combo + " ומעלה!";
    return "×" + combo;
  }

  function parseAnswerMap(value) {
    try {
      const parsed = JSON.parse(value);
      return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
    } catch (e) { return {}; }
  }

  function isCorrectAnswer(nq, key) {
    if (nq.type === "multiple_opinions_dropdown") {
      const given = parseAnswerMap(key);
      return (nq.decisors || []).every((d) => given[d.id] === d.correctChoice);
    }
    if (nq.type === "multiple_choice" && nq.multiSelect) {
      let given;
      try {
        given = JSON.parse(key);
        if (!Array.isArray(given)) given = [];
      } catch (e) { given = []; }
      const correct = nq.correctKeys || [];
      return given.length === correct.length && correct.every((k) => given.includes(k));
    }
    return nq.correctKey === key;
  }

  const PARCOURS_LABELS = { bassar_bechalav: "בשר בחלב" };
  function parcoursLabel(p) { return PARCOURS_LABELS[p] || p || ""; }

  // Mirrors the section labels used in templates/admin/questions.html and
  // templates/student/settings.html.
  const SECTION_LABELS = {
    shulchan_aruch: 'שו"ע', tur: "טור", psikei_admur: 'פסקי אדה"ז', ptei_teshuva: "פתחי תשובה",
  };
  function sectionLabel(sections) {
    if (!sections || !sections.length) return "";
    return sections.map((s) => SECTION_LABELS[s] || s).join(" + ");
  }

  function toHebNum(n) {
    if (!n || n <= 0) return String(n);
    const h = ["","ק","ר","ש","ת","תק","תר","תש","תת","תתק"];
    const t = ["","י","כ","ל","מ","נ","ס","ע","פ","צ"];
    const o = ["","א","ב","ג","ד","ה","ו","ז","ח","ט"];
    let r = h[Math.floor(n / 100)];
    const rem = n % 100;
    if (rem === 15) return r + "טו";
    if (rem === 16) return r + "טז";
    r += t[Math.floor(rem / 10)] + o[rem % 10];
    return r;
  }

  // ── answer flow ────────────────────────────────────────────────────────────

  function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

  // Envoie la réponse au serveur, seule source de vérité pour la sauvegarde
  // (FSRS, points, "apprise"). Une réponse HTTP non-2xx (ex: session expirée)
  // était auparavant traitée comme un succès silencieux — la carte
  // s'affichait comme corrigée côté client sans jamais être enregistrée, et
  // ni les points ni le statut "apprise" ne survivaient à la fermeture de
  // l'app. On retente les échecs transitoires (réseau / 5xx) et on distingue
  // explicitement l'expiration de session (401), qui n'a aucune chance de
  // réussir sans reconnexion.
  async function submitAnswer(payload, guessCorrect, nq, q) {
    const attempts = 3;
    for (let i = 0; i < attempts; i++) {
      try {
        const res = await fetch(cfg.answer, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (res.status === 401) return { data: null, sessionExpired: true };
        if (!res.ok) throw new Error("http " + res.status);
        return { data: await res.json(), sessionExpired: false };
      } catch (e) {
        if (i < attempts - 1) await sleep(400 * (i + 1));
      }
    }
    // Échec persistant (réseau hors-ligne...) : on garde l'app jouable en
    // mode dégradé, mais rien de tout cela n'est enregistré côté serveur —
    // 0 point, pas de mise à jour FSRS, la question réapparaîtra donc comme
    // non apprise à la prochaine visite.
    return {
      data: {
        is_correct: guessCorrect, correct_key: nq.correctKey, points: 0,
        combo: guessCorrect ? state.combo + 1 : 0, explanation: nq.explanation, seif: q.seif,
        rating_badge: "", rating_tone: "", daily_bonus: 0, unsaved: true,
      },
      sessionExpired: false,
    };
  }

  async function pick(key) {
    if (state.revealed) return;
    const q = queue[state.idx];
    const nq = q.normalized;
    const origIdx = origIdxMap[q.id];
    const elapsed = Date.now() - state.start;
    const prevResult = state.results[origIdx];
    state.chosen = key;
    state.revealed = true;

    const guessCorrect = isCorrectAnswer(nq, key);
    state.results[origIdx] = guessCorrect ? "correct" : "wrong";
    render();

    const { data, sessionExpired } = await submitAnswer({
      question_id: q.id, given_answer: key, response_time_ms: elapsed, combo: state.combo,
      mode: cfg.mode,
    }, guessCorrect, nq, q);

    if (sessionExpired) {
      window.alert("החיבור שלך פג — מתחבר מחדש. התשובה האחרונה לא נשמרה, יש לענות עליה שוב.");
      window.location.reload();
      return;
    }

    state.combo = data.combo;
    state.results[origIdx] = data.is_correct ? "correct" : "wrong";
    if (data.daily_bonus) {
      state.dailyBonus += data.daily_bonus;
      // Bonus par parcours : en mode "הכל" chaque parcours vidé déclenche le
      // sien — on retient les libellés pour l'écran de fin.
      if (data.daily_bonus_parcours) state.dailyBonusParcours.push(data.daily_bonus_parcours);
    }

    if (data.is_correct) {
      state.sessionPoints += data.points;
      if (prevResult !== "correct") state.correctCount++;
    } else if (!state.reportedIds.has(q.id)) {
      // Ne pas remettre en file une question déjà signalée : sinon elle
      // réapparaît plus tard dans la même session malgré le signalement.
      queue.push(q);
    }

    state.feedback = {
      pts: data.points, isCorrect: data.is_correct,
      ratingBadge: data.rating_badge, ratingTone: data.rating_tone,
      explanation: data.explanation, seif: data.seif,
      isRetry: prevResult === "wrong",
      unsaved: !!data.unsaved,
    };
    render();

    const turn = state.idx;
    setTimeout(() => {
      if (!state.feedback || state.idx !== turn) return;
      state.feedback.ratingBadge = "";
      if (refs.ratingBadge) { refs.ratingBadge.remove(); refs.ratingBadge = null; }
    }, 1500);
    setTimeout(() => {
      if (!state.feedback || state.idx !== turn || state.showNext) return;
      state.showNext = true;
      if (refs.exp) { refs.exp.appendChild(nextButton()); updateExpHeight(); }
    }, 800);
  }

  // Modale de signalement : remplace window.prompt par un dialogue habillé,
  // cohérent avec le reste de l'UI. Résout avec le motif saisi (peut être
  // vide) ou `null` si l'utilisateur annule.
  function openReportModal() {
    return new Promise((resolve) => {
      const backdrop = el("div", "report-modal-backdrop");
      const modal = el("div", "report-modal animate-pop-in");
      modal.appendChild(el("div", "report-modal-icon", icon("flag", 20)));
      modal.appendChild(el("h3", "report-modal-title", cfg.canSuggest ? "הצעה לשיפור שאלה" : "דיווח על שאלה"));
      modal.appendChild(el("p", "report-modal-subtitle", cfg.canSuggest ? "ההצעה תישלח לאישור ולא תשנה את השאלה." : "מה הבעיה בשאלה הזו? הדיווח יסתיר אותה עבורך מיד."));

      const textarea = document.createElement("textarea");
      textarea.className = "report-modal-textarea";
      textarea.placeholder = "לדוגמה: הניסוח לא ברור, התשובה הנכונה שגויה... (אופציונלי)";
      textarea.rows = 3;
      modal.appendChild(textarea);

      const actions = el("div", "report-modal-actions");
      const cancelBtn = el("button", "btn btn-outline", "ביטול");
      cancelBtn.type = "button";
      const submitBtn = el("button", "btn btn-primary", cfg.canSuggest ? "שלח הצעה" : "שלח דיווח");
      submitBtn.type = "button";
      actions.appendChild(submitBtn);
      actions.appendChild(cancelBtn);
      modal.appendChild(actions);
      backdrop.appendChild(modal);

      function close(result) {
        document.removeEventListener("keydown", onKey);
        backdrop.remove();
        resolve(result);
      }
      function onKey(e) { if (e.key === "Escape") close(null); }
      document.addEventListener("keydown", onKey);
      backdrop.addEventListener("click", (e) => { if (e.target === backdrop) close(null); });
      cancelBtn.addEventListener("click", () => close(null));
      submitBtn.addEventListener("click", () => close(textarea.value.trim()));

      document.body.appendChild(backdrop);
      textarea.focus();
    });
  }

  async function reportQuestion(qId, btn) {
    if (state.reportedIds.has(qId)) return;
    const reason = await openReportModal();
    if (reason === null) return; // annulé

    btn.disabled = true;

    let ok = false;
    try {
      const res = await fetch(cfg.report, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question_id: qId, reason }),
      });
      ok = res.ok;
    } catch (e) { ok = false; }

    if (!ok) {
      // Le serveur n'a pas confirmé le signalement (session expirée, erreur
      // réseau...) — on ne masque pas l'échec : la question doit rester
      // signalable et continuer d'apparaître dans la file.
      btn.disabled = false;
      window.alert("הדיווח נכשל, נסה שוב");
      return;
    }

    state.reportedIds.add(qId);
    // Retire toute copie déjà remise en file (retry suite à une mauvaise
    // réponse) pour qu'elle ne réapparaisse pas plus tard dans cette session.
    for (let i = queue.length - 1; i > state.idx; i--) {
      if (queue[i].id === qId) queue.splice(i, 1);
    }
    // La question signalée disparaît immédiatement — pas d'attente d'une
    // réponse ni d'une prochaine ouverture du paquet.
    if (queue[state.idx] && queue[state.idx].id === qId) next();
  }

  function nextButton() {
    const isLast = state.idx + 1 >= queue.length;
    const btn = document.createElement("button");
    btn.className = "btn btn-primary btn-block btn-lg animate-slide-up mt-5";
    btn.textContent = isLast
      ? (isRevision ? "סיים חזרה" : "סיים סימן")
      : "שאלה הבאה ←";
    btn.addEventListener("click", next);
    return btn;
  }

  function submitMultiSelect() {
    if (state.multiSelected.size === 0) return;
    pick(JSON.stringify(Array.from(state.multiSelected)));
  }

  function submitOpinions() {
    const nq = queue[state.idx].normalized;
    const missing = nq.decisors.some((d) => !state.opinionAnswers[d.id]);
    if (missing) { alert("בחר תשובה לכל פוסק"); return; }
    const ordered = {};
    nq.decisors.forEach((d) => { ordered[d.id] = state.opinionAnswers[d.id]; });
    pick(JSON.stringify(ordered));
  }

  function activeOpinionId(nq) {
    const decisors = nq.decisors || [];
    if (state.activeOpinionId && decisors.some((d) => d.id === state.activeOpinionId)) {
      return state.activeOpinionId;
    }
    const firstEmpty = decisors.find((d) => !state.opinionAnswers[d.id]);
    return firstEmpty ? firstEmpty.id : null;
  }

  function assignOpinionChoice(nq, choice) {
    if (state.revealed) return;
    const id = activeOpinionId(nq);
    if (!id) return;
    state.opinionAnswers[id] = choice;

    const decisors = nq.decisors || [];
    const currentIndex = decisors.findIndex((d) => d.id === id);
    const nextEmpty = decisors.find((d, index) => index > currentIndex && !state.opinionAnswers[d.id])
      || decisors.find((d) => !state.opinionAnswers[d.id]);
    state.activeOpinionId = nextEmpty ? nextEmpty.id : null;
    render();
  }

  function next() {
    if (state.idx + 1 >= queue.length) { renderComplete(); return; }
    state.idx++;
    state.chosen = null; state.multiSelected = new Set(); state.opinionAnswers = {}; state.activeOpinionId = null; state.revealed = false;
    state.feedback = null; state.showNext = false; state.start = Date.now();
    render();
  }

  // ── screens ────────────────────────────────────────────────────────────────

  function renderComplete() {
    removeExpPanel();
    root.innerHTML = "";
    if (isRevision) { renderRevisionComplete(); }
    else { renderParcoursComplete(); }
  }

  function renderParcoursComplete() {
    const total = origQuestions.length;
    const score = total ? Math.round((state.correctCount / total) * 100) : 0;

    const wrap = el("div", "stack center-text animate-slide-up player-complete");

    const circle = el("div", "score-circle");
    circle.appendChild(el("div", "score-circle-inner"));
    const circleText = el("div", "score-circle-text");
    circleText.appendChild(el("div", "text-3xl extrabold", String(state.correctCount)));
    circleText.appendChild(el("div", "text-xs muted", "מתוך " + total));
    circle.appendChild(circleText);
    wrap.appendChild(circle);

    wrap.appendChild(el("h2", "text-2xl bold mt-6", "כל הכבוד!"));
    wrap.appendChild(el("p", "text-sm muted", score + "% תשובות נכונות"));

    const stats = el("div", "row gap-4 player-complete-stats");
    const ptsCol = el("div", "center-text");
    ptsCol.appendChild(el("div", "text-3xl extrabold accent", "+" + state.sessionPoints));
    ptsCol.appendChild(el("div", "text-xs muted", "נקודות"));
    stats.appendChild(ptsCol);
    stats.appendChild(el("div", "divider-v"));
    const comboCol = el("div", "center-text");
    comboCol.appendChild(el("div", "row center gap-1 text-3xl extrabold accent", icon("flame", 24), String(state.combo)));
    comboCol.appendChild(el("div", "text-xs muted", "רצף קומבו"));
    stats.appendChild(comboCol);
    wrap.appendChild(stats);

    const actions = el("div", "stack-sm player-complete-actions");
    const homeLink = el("a", "btn btn-primary btn-block");
    homeLink.href = cfg.home;
    homeLink.textContent = "חזור לבית";
    const moreLink = el("a", "btn btn-block muted");
    moreLink.href = cfg.parcours;
    moreLink.textContent = "עוד שאלות";
    actions.appendChild(homeLink);
    actions.appendChild(moreLink);
    wrap.appendChild(actions);
    wrap.appendChild(el("div", "text-xs muted mt-2", "חוזר לבית אוטומטית..."));

    root.appendChild(wrap);
    setTimeout(() => { window.location.href = cfg.home; }, 4000);
  }

  async function renderRevisionComplete() {
    const spinner = el("div", "stack center-text animate-slide-up player-complete");
    spinner.appendChild(el("div", "spinner mx-auto"));
    root.appendChild(spinner);

    let data = { points_today: 0, cards_reviewed: 0, correct_today: 0 };
    try {
      const res = await fetch(cfg.todayStats);
      if (res.ok) data = await res.json();
    } catch (_) {}

    root.innerHTML = "";
    const wrap = el("div", "stack center-text animate-slide-up player-complete");

    const doneMark = el("div", {
      style: "height:4rem;width:4rem;border-radius:999px;background:var(--brand-dim);color:var(--brand);" +
        "display:flex;align-items:center;justify-content:center;margin:0 auto;",
    }, icon("check", 32));
    wrap.appendChild(doneMark);
    wrap.appendChild(el("h2", "text-2xl bold mt-4", "סיום " + cfg.modeLabel + "!"));
    wrap.appendChild(el("p", "text-sm muted", "עשית עבודה מצוינת היום"));

    if (state.dailyBonus > 0) {
      let bonusText = "בונוס השלמה יומית +" + state.dailyBonus;
      if (state.dailyBonusParcours.length) bonusText += " (" + state.dailyBonusParcours.join(", ") + ")";
      const bonusPill = el("div", "pill pill-accent animate-pop-in mt-3", icon("flame", 14), bonusText);
      wrap.appendChild(bonusPill);
    }

    const grid = el("div", "grid grid-3 mt-6");

    const col1 = el("div", "card center-text");
    col1.appendChild(el("div", "text-2xl extrabold accent", "+" + data.points_today));
    col1.appendChild(el("div", "text-xs muted mt-1", "נקודות היום"));
    grid.appendChild(col1);

    const col2 = el("div", "card center-text");
    col2.appendChild(el("div", "text-2xl extrabold", String(data.cards_reviewed)));
    col2.appendChild(el("div", "text-xs muted mt-1", "כרטיסים"));
    grid.appendChild(col2);

    const col3 = el("div", "card center-text");
    const pct = data.cards_reviewed
      ? Math.round((data.correct_today / data.cards_reviewed) * 100)
      : 0;
    col3.appendChild(el("div", "text-2xl extrabold success", pct + "%"));
    col3.appendChild(el("div", "text-xs muted mt-1", "דיוק"));
    grid.appendChild(col3);

    wrap.appendChild(grid);

    const actions = el("div", "stack-sm player-complete-actions");
    const homeLink = el("a", "btn btn-primary btn-block");
    homeLink.href = cfg.home;
    homeLink.textContent = "חזור לבית";
    const learnLink = el("a", "btn btn-outline btn-block");
    learnLink.href = cfg.parcours;
    learnLink.textContent = "המשך ללמוד";
    actions.appendChild(homeLink);
    actions.appendChild(learnLink);
    wrap.appendChild(actions);

    root.appendChild(wrap);
  }

  function render() {
    const q = queue[state.idx];
    const nq = q.normalized;
    const origIdx = origIdxMap[q.id];
    const isTrueFalse = nq.type === "true_false";
    const isOpinions = nq.type === "multiple_opinions_dropdown";
    root.innerHTML = "";
    removeExpPanel();
    refs.exp = null;
    refs.ratingBadge = null;

    // header
    const backBtn = el("button", "btn btn-outline");
    backBtn.style.cssText = "height:2.5rem;width:2.5rem;border-radius:999px;padding:0;display:flex;align-items:center;justify-content:center;";
    backBtn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="9 18 15 12 9 6"/></svg>';
    backBtn.addEventListener("click", () => { window.location.href = cfg.back; });
    const header = el("div", "row between");
    header.appendChild(backBtn);

    const headerRight = el("div", "row gap-2");
    const reportBtn = el("button", "btn btn-outline report-btn");
    reportBtn.type = "button";
    reportBtn.title = "דווח על שאלה זו";
    reportBtn.style.cssText = "height:2.5rem;width:2.5rem;border-radius:999px;padding:0;display:flex;align-items:center;justify-content:center;";
    reportBtn.appendChild(icon("flag", 16));
    if (state.reportedIds.has(q.id)) {
      reportBtn.disabled = true;
      reportBtn.title = "השאלה כבר דווחה";
    } else {
      reportBtn.addEventListener("click", () => reportQuestion(q.id, reportBtn));
    }
    headerRight.appendChild(reportBtn);
    if (cfg.adminEditUrl) {
      const editLink = el("a", "btn btn-outline", "✏️ ערוך");
      editLink.href = cfg.adminEditUrl + "?id=" + encodeURIComponent(q.id);
      editLink.title = "עריכת השאלה בניהול";
      headerRight.appendChild(editLink);
    }

    if (isRevision) {
      const revLabel = el("span", "");
      revLabel.textContent = cfg.modeLabel;
      revLabel.style.cssText = "font-family:'Secular One',sans-serif;font-size:var(--text-sm);color:var(--muted);";
      headerRight.appendChild(revLabel);
    } else {
      headerRight.appendChild(el("div", "pill pill-accent", icon("coin", 14), String(state.sessionPoints)));
    }
    header.appendChild(headerRight);
    root.appendChild(header);

    // dots — fenêtre glissante centrée sur la question courante (5 de chaque
    // côté) ; une fois qu'il ne reste plus que 5 questions après la question
    // courante, la fenêtre cesse d'avancer et se fige sur la fin du paquet.
    const DOT_RADIUS = 5;
    const totalQuestions = origQuestions.length;
    const windowSize = Math.min(totalQuestions, DOT_RADIUS * 2 + 1);
    const dotsStart = Math.min(
      Math.max(0, origIdx - DOT_RADIUS),
      Math.max(0, totalQuestions - windowSize)
    );
    const dots = el("div", "row center gap-1 player-dots");
    for (let i = dotsStart; i < dotsStart + windowSize; i++) {
      const r = state.results[i];
      let cls = "dot";
      if (r === "correct") cls += " correct";
      else if (r === "wrong") cls += " wrong";
      if (i === origIdx) cls += " current";
      dots.appendChild(el("span", cls));
    }
    root.appendChild(dots);

    // retry badge
    if (state.feedback && state.feedback.isRetry) {
      root.appendChild(el("div", "retry-hint", "חזרה על שאלה זו"));
    }

    // enveloppe unifiée : question + réponses sur la même feuille
    const cardUnified = el("div", "player-card-unified");

    // question card
    const card = el("div", "glass-card player-card" + (state.revealed ? "" : " glow-indigo"));
    const metaParts = [];
    const pLabel = parcoursLabel(q.parcours);
    if (pLabel) metaParts.push(pLabel);
    const srcSiman = q.siman != null ? q.siman : Number(cfg.siman);
    if (srcSiman) metaParts.push("סימן " + toHebNum(srcSiman));
    if (q.seif !== null && q.seif !== undefined) metaParts.push("סעיף " + toHebNum(q.seif));
    const secLabel = sectionLabel(q.section);
    if (secLabel) metaParts.push(secLabel);
    if (metaParts.length) {
      card.appendChild(el("div", "card-meta", metaParts.join(" · ")));
    }
    const srcSubject = q.subject || cfg.subject;
    if (srcSubject) {
      card.appendChild(el("div", "card-meta card-meta-subject", srcSubject));
    }
    if (nq.scenario) {
      card.appendChild(el("div", "text-sm muted scenario-box", nq.scenario));
    }
    card.appendChild(el("p", "question-prompt", nq.prompt));
    if (state.combo >= 2 && !state.revealed) {
      card.appendChild(el("div", "pill animate-pop-in combo-pill row gap-1", icon("flame", 13), comboLabel(state.combo)));
    }
    if (state.feedback && state.feedback.ratingBadge) {
      refs.ratingBadge = el("div", "pill animate-pop-in rating-badge-pos " + state.feedback.ratingTone, state.feedback.ratingBadge);
      card.appendChild(refs.ratingBadge);
    }
    if (q.tags && q.tags.length) {
      const tagsRow = el("div", "card-tags");
      q.tags.forEach((t) => tagsRow.appendChild(el("span", "card-tag", t)));
      card.appendChild(tagsRow);
    }
    cardUnified.appendChild(card);

    // answers
    const answers = el("div", (isTrueFalse ? "choice-grid" : "stack-sm") + " player-answers");

    if (isOpinions) {
      const wrap = el("div", "opinions-match");
      const activeId = activeOpinionId(nq);
      const rows = el("div", "opinions-rows");
      nq.decisors.forEach((d) => {
        const selected = state.opinionAnswers[d.id];
        const good = selected === d.correctChoice;
        const isActive = !state.revealed && activeId === d.id;
        let rowCls = "opinions-row";
        if (state.revealed) {
          rowCls += good ? " is-correct" : " is-wrong";
        } else if (isActive) {
          rowCls += " is-active";
        } else if (selected) {
          rowCls += " is-filled";
        }

        const row = el("button", rowCls);
        row.type = "button";
        if (!state.revealed) {
          row.addEventListener("click", () => {
            state.activeOpinionId = d.id;
            render();
          });
        } else {
          row.disabled = true;
        }

        row.appendChild(el("span", "opinions-decisor", d.name));
        row.appendChild(el("span", selected ? "opinions-slot is-filled" : "opinions-slot", selected || "בחר תשובה"));

        if (state.revealed && !good) {
          row.appendChild(el("span", "opinions-correct-answer", d.correctChoice));
        }
        rows.appendChild(row);
      });
      wrap.appendChild(rows);

      if (!state.revealed) {
        const bank = el("div", "opinions-bank");
        (nq.dropdownChoices || []).forEach((c) => {
          const btn = el("button", "opinions-bank-choice", c);
          btn.type = "button";
          btn.addEventListener("click", () => assignOpinionChoice(nq, c));
          bank.appendChild(btn);
        });
        wrap.appendChild(bank);
      }
      if (!state.revealed) {
        const submitBtn = el("button", "btn btn-primary btn-block btn-lg", "בדוק תשובות");
        submitBtn.addEventListener("click", submitOpinions);
        wrap.appendChild(submitBtn);
      }
      answers.appendChild(wrap);
    } else if (nq.multiSelect) {
      answers.appendChild(el("div", "text-xs muted mb-2", "לשאלה זו יש כמה תשובות נכונות — סמן את כולן"));
      nq.choices.forEach((c, i) => {
        const isCorrect = (nq.correctKeys || []).includes(c.key);
        const isChosen = state.multiSelected.has(c.key);
        let cls = "choice";
        let mark = null;
        if (state.revealed) {
          if (isCorrect) { cls += " is-correct"; mark = el("span", "success", icon("check", 18)); }
          else if (isChosen) { cls += " is-wrong"; mark = el("span", "destructive", icon("x", 18)); }
          else cls += " is-dim";
        } else if (isChosen) {
          cls += " is-selected";
        }
        const btn = el("button", cls);
        if (!state.revealed) {
          btn.addEventListener("click", () => {
            if (state.multiSelected.has(c.key)) state.multiSelected.delete(c.key);
            else state.multiSelected.add(c.key);
            render();
          });
        } else {
          btn.disabled = true;
        }
        btn.appendChild(el("span", "flex-1 line-height-loose", c.text));
        btn.appendChild(mark || el("span", "key", String(i + 1)));
        answers.appendChild(btn);
      });
      if (!state.revealed) {
        const submitBtn = el("button", "btn btn-primary btn-block btn-lg mt-3", "בדוק תשובות");
        submitBtn.disabled = state.multiSelected.size === 0;
        submitBtn.addEventListener("click", submitMultiSelect);
        answers.appendChild(submitBtn);
      }
    } else {
      if (!isTrueFalse) {
        answers.appendChild(el("div", "text-xs muted mb-2", "לשאלה זו יש תשובה נכונה אחת בלבד"));
      }
      nq.choices.forEach((c, i) => {
        const isCorrect = nq.correctKey === c.key;
        const isChosen = state.chosen === c.key;
        let cls = "choice" + (isTrueFalse ? " choice-tf" : "");
        let mark = null;
        if (state.revealed) {
          if (isCorrect) { cls += " is-correct"; mark = el("span", "success", icon("check", 18)); }
          else if (isChosen) { cls += " is-wrong"; mark = el("span", "destructive", icon("x", 18)); }
          else cls += " is-dim";
        }
        const btn = el("button", cls);
        btn.addEventListener("click", () => pick(c.key));
        if (state.revealed) btn.disabled = true;
        if (isTrueFalse) {
          btn.appendChild(el("span", { style: "font-size:1.5rem;" }, c.label));
          btn.appendChild(el("span", "text-lg bold", c.text));
        } else {
          btn.appendChild(el("span", "flex-1 line-height-loose", c.text));
          btn.appendChild(mark || el("span", "key", String(i + 1)));
        }
        answers.appendChild(btn);
      });
    }

    if (state.feedback && state.feedback.isCorrect && state.feedback.pts > 0) {
      answers.appendChild(el("div", "animate-float-up extrabold accent points-float", "+" + state.feedback.pts));
    }
    cardUnified.appendChild(answers);
    root.appendChild(cardUnified);

    // explanation panel — a full-width bar fixed to the bottom of the screen, outside the page flow.
    // Appended to <body> (not #player) so it isn't caught by an ancestor's transform — see removeExpPanel().
    if (state.revealed && state.feedback) {
      const exp = el("div", "animate-slide-up player-exp");
      const inner = el("div", "player-exp-inner");
      if (!state.feedback.isCorrect && state.combo === 0) {
        inner.appendChild(el("div", "exp-combo-break", "הקומבו נשבר"));
      }
      if (state.feedback.unsaved) {
        inner.appendChild(el("div", "exp-combo-break", "אין חיבור לשרת — התשובה לא נשמרה, נא לבדוק את החיבור"));
      }
      if (state.feedback.explanation) {
        inner.appendChild(el("p", "text-sm line-height-loose", state.feedback.explanation));
      }
      if (state.showNext) inner.appendChild(nextButton());
      exp.appendChild(inner);
      refs.exp = inner;
      document.body.appendChild(exp);
      document.body.classList.add("has-player-exp");
      updateExpHeight();
    }
  }

  render();
})();
