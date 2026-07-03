// Chapter question player
(function () {
  const root = document.getElementById("player");
  const origQuestions = JSON.parse(root.dataset.questions);
  const cfg = {
    parcours: root.dataset.parcoursUrl,
    home: root.dataset.homeUrl,
    answer: root.dataset.answerUrl,
    todayStats: root.dataset.todayStatsUrl,
    subject: root.dataset.subject,
    siman: root.dataset.siman,
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
    results: new Array(origQuestions.length).fill(null),
    chosen: null,
    opinionAnswers: {},
    revealed: false,
    feedback: null,
    showNext: false,
    start: Date.now(),
  };

  const refs = {};

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
    if (nq.type !== "multiple_opinions_dropdown") return nq.correctKey === key;
    const given = parseAnswerMap(key);
    return (nq.decisors || []).every((d) => given[d.id] === d.correctChoice);
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

    let data;
    try {
      const res = await fetch(cfg.answer, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question_id: q.id, given_answer: key, response_time_ms: elapsed, combo: state.combo,
        }),
      });
      data = await res.json();
    } catch (e) {
      data = { is_correct: guessCorrect, correct_key: nq.correctKey, points: 0,
               combo: guessCorrect ? state.combo + 1 : 0,
               explanation: nq.explanation, seif: q.seif, rating_badge: "", rating_tone: "" };
    }

    state.combo = data.combo;
    state.results[origIdx] = data.is_correct ? "correct" : "wrong";

    if (data.is_correct) {
      state.sessionPoints += data.points;
      if (prevResult !== "correct") state.correctCount++;
    } else {
      queue.push(q);
    }

    state.feedback = {
      pts: data.points, isCorrect: data.is_correct,
      ratingBadge: data.rating_badge, ratingTone: data.rating_tone,
      explanation: data.explanation, seif: data.seif,
      isRetry: prevResult === "wrong",
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
      if (refs.exp) refs.exp.appendChild(nextButton());
    }, 800);
  }

  function nextButton() {
    const isLast = state.idx + 1 >= queue.length;
    const btn = document.createElement("button");
    btn.className = "btn btn-primary btn-block btn-lg animate-slide-up mt-5";
    btn.textContent = isLast
      ? (isRevision ? "סיים חזרות יומיות" : "סיים סימן")
      : "שאלה הבאה ←";
    btn.addEventListener("click", next);
    return btn;
  }

  function submitOpinions() {
    const nq = queue[state.idx].normalized;
    const missing = nq.decisors.some((d) => !state.opinionAnswers[d.id]);
    if (missing) { alert("בחר תשובה לכל פוסק"); return; }
    const ordered = {};
    nq.decisors.forEach((d) => { ordered[d.id] = state.opinionAnswers[d.id]; });
    pick(JSON.stringify(ordered));
  }

  function next() {
    if (state.idx + 1 >= queue.length) { renderComplete(); return; }
    state.idx++;
    state.chosen = null; state.opinionAnswers = {}; state.revealed = false;
    state.feedback = null; state.showNext = false; state.start = Date.now();
    render();
  }

  // ── screens ────────────────────────────────────────────────────────────────

  function renderComplete() {
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
    wrap.appendChild(el("h2", "text-2xl bold mt-4", "סיום חזרות היומיות!"));
    wrap.appendChild(el("p", "text-sm muted", "עשית עבודה מצוינת היום"));

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
    const totalDots = Math.min(10, origQuestions.length);
    const isTrueFalse = nq.type === "true_false";
    const isOpinions = nq.type === "multiple_opinions_dropdown";
    root.innerHTML = "";
    refs.exp = null;
    refs.ratingBadge = null;

    // header
    const backBtn = el("button", "btn btn-outline");
    backBtn.style.cssText = "height:2.5rem;width:2.5rem;border-radius:999px;padding:0;display:flex;align-items:center;justify-content:center;";
    backBtn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="9 18 15 12 9 6"/></svg>';
    backBtn.addEventListener("click", () => { window.location.href = cfg.parcours; });
    const header = el("div", "row between");
    header.appendChild(backBtn);
    if (isRevision) {
      const revLabel = el("span", "");
      revLabel.textContent = "חזרה יומית";
      revLabel.style.cssText = "font-family:'Secular One',sans-serif;font-size:var(--text-sm);color:var(--muted);";
      header.appendChild(revLabel);
    } else {
      header.appendChild(el("div", "pill pill-accent", icon("coin", 14), String(state.sessionPoints)));
    }
    root.appendChild(header);

    // dots
    const dots = el("div", "row center gap-1 player-dots");
    for (let i = 0; i < totalDots; i++) {
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
    cardUnified.appendChild(card);

    // answers
    const answers = el("div", (isTrueFalse ? "choice-grid" : "stack-sm") + " player-answers");

    if (isOpinions) {
      const useButtons = window.innerWidth >= 640 && (nq.dropdownChoices || []).length <= 4;
      const wrap = el("div", "stack-sm");
      nq.decisors.forEach((d) => {
        const selected = state.opinionAnswers[d.id];
        const good = selected === d.correctChoice;
        const box = el("div", "card");
        if (state.revealed) {
          box.style.border = "2px solid " + (good ? "var(--success)" : "var(--destructive)");
          box.style.background = good ? "rgba(16,185,129,0.15)" : "rgba(239,68,68,0.15)";
        } else {
          box.style.border = "2px solid var(--border)";
        }
        box.appendChild(el("div", "bold mb-2", d.name));

        if (useButtons) {
          const grid = el("div", "opinions-btn-grid");
          (nq.dropdownChoices || []).forEach((c) => {
            const isChosen = selected === c;
            const isCorrectChoice = c === d.correctChoice;
            let btnCls = "btn btn-outline opinions-choice-btn";
            if (state.revealed) {
              if (isCorrectChoice) btnCls += " opi-correct";
              else if (isChosen) btnCls += " opi-wrong";
              else btnCls += " opi-dim";
            } else if (isChosen) {
              btnCls += " opi-selected";
            }
            const btn = el("button", btnCls, c);
            if (!state.revealed) {
              btn.addEventListener("click", () => {
                state.opinionAnswers[d.id] = c;
                render();
              });
            } else {
              btn.disabled = true;
            }
            grid.appendChild(btn);
          });
          box.appendChild(grid);
        } else {
          const sel = document.createElement("select");
          sel.addEventListener("change", (e) => { state.opinionAnswers[d.id] = e.target.value; });
          const placeholder = el("option", "");
          placeholder.value = "";
          placeholder.textContent = "בחר עמדה";
          sel.appendChild(placeholder);
          (nq.dropdownChoices || []).forEach((c) => {
            const opt = el("option", "");
            opt.value = c;
            opt.textContent = c;
            if (selected === c) opt.selected = true;
            sel.appendChild(opt);
          });
          if (state.revealed) sel.disabled = true;
          box.appendChild(sel);
        }

        if (state.revealed && !good) {
          box.appendChild(el("div", "text-sm success mt-2", "התשובה: " + d.correctChoice));
        }
        wrap.appendChild(box);
      });
      if (!state.revealed) {
        const submitBtn = el("button", "btn btn-primary btn-block btn-lg", "בדוק תשובות");
        submitBtn.addEventListener("click", submitOpinions);
        wrap.appendChild(submitBtn);
      }
      answers.appendChild(wrap);
    } else {
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
          btn.appendChild(mark || el("span", "key", c.label || String(i + 1)));
        }
        answers.appendChild(btn);
      });
    }

    if (state.feedback && state.feedback.isCorrect && state.feedback.pts > 0) {
      answers.appendChild(el("div", "animate-float-up extrabold accent points-float", "+" + state.feedback.pts));
    }
    cardUnified.appendChild(answers);
    root.appendChild(cardUnified);

    // explanation panel
    if (state.revealed && state.feedback) {
      const exp = el("div", "animate-slide-up player-exp");
      if (!state.feedback.isCorrect && state.combo === 0) {
        exp.appendChild(el("div", "exp-combo-break", "הקומבו נשבר"));
      }
      if (q.seif !== null && q.seif !== undefined) {
        const srcSubject = q.subject || cfg.subject;
        const srcSiman = q.siman != null ? q.siman : Number(cfg.siman);
        exp.appendChild(el("div", "exp-source",
          "מקור: " + srcSubject + " · סימן " + toHebNum(srcSiman) + " · סעיף " + toHebNum(q.seif)));
      }
      if (state.feedback.explanation) {
        exp.appendChild(el("p", "text-sm line-height-loose", state.feedback.explanation));
      }
      if (state.showNext) exp.appendChild(nextButton());
      refs.exp = exp;
      root.appendChild(exp);
    }
  }

  render();
})();
