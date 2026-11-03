'use strict';

const WORD_LENGTH = 5;
const MAX_ROWS = 6;
const NEXT_COLOUR = { B: 'Y', Y: 'G', G: 'B' };
const COLOUR_RANK = { B: 1, Y: 2, G: 3 };
const KEY_ROWS = ['qwertyuiop', 'asdfghjkl', '⏎zxcvbnm⌫'];

const state = {
  gameMode: 'assist',     // 'assist': you enter colours; 'play': colours come from a hidden answer
  answerMode: 'official', // which answer list the solver assumes
  rankBy: 'one',          // which strategy orders the suggestions and drives Tab
  rows: [],               // submitted turns: { word, feedback }
  current: '',
  colours: Array(WORD_LENGTH).fill('B'),
  secret: null,
  over: false,
  analysis: null,
  twoStep: null,
  twoStepLoading: false,
  requestId: 0,
  guesses: new Set(),
  answers: [],
};

const $ = (id) => document.getElementById(id);
const boardEl = $('board');
const tiles = [];

// --- Feedback (mirrors solver.patterns.feedback) ------------------------------------

function feedback(guess, answer) {
  const colours = Array(WORD_LENGTH).fill('B');
  const unmatched = [];
  for (let i = 0; i < WORD_LENGTH; i++) {
    if (guess[i] === answer[i]) colours[i] = 'G';
    else unmatched.push(answer[i]);
  }
  for (let i = 0; i < WORD_LENGTH; i++) {
    if (colours[i] === 'G') continue;
    const at = unmatched.indexOf(guess[i]);
    if (at !== -1) {
      colours[i] = 'Y';
      unmatched.splice(at, 1);
    }
  }
  return colours.join('');
}

// --- Building the page ----------------------------------------------------------------

function buildBoard() {
  for (let r = 0; r < MAX_ROWS; r++) {
    const row = document.createElement('div');
    row.className = 'row';
    const rowTiles = [];
    for (let c = 0; c < WORD_LENGTH; c++) {
      const tile = document.createElement('div');
      tile.className = 'tile';
      tile.addEventListener('click', () => cycleColour(r, c));
      row.appendChild(tile);
      rowTiles.push(tile);
    }
    boardEl.appendChild(row);
    tiles.push(rowTiles);
  }
}

function buildKeyboard() {
  for (const letters of KEY_ROWS) {
    const row = document.createElement('div');
    row.className = 'key-row';
    for (const ch of letters) {
      const key = document.createElement('button');
      key.className = 'key';
      key.type = 'button';
      if (ch === '⏎') { key.textContent = 'Enter'; key.classList.add('wide'); key.dataset.key = 'Enter'; }
      else if (ch === '⌫') { key.textContent = '⌫'; key.classList.add('wide'); key.dataset.key = 'Backspace'; key.title = 'Backspace'; }
      else { key.textContent = ch; key.dataset.key = ch; }
      key.addEventListener('click', () => { handleKey(key.dataset.key); key.blur(); });
      row.appendChild(key);
    }
    $('keyboard').appendChild(row);
  }
}

function bindSegment(id, onChange) {
  const seg = $(id);
  seg.addEventListener('click', (e) => {
    const button = e.target.closest('button');
    if (!button || button.classList.contains('active')) return;
    seg.querySelectorAll('button').forEach((b) => b.classList.toggle('active', b === button));
    button.blur();
    onChange(button.dataset.value);
  });
}

function setSegment(id, value) {
  $(id).querySelectorAll('button').forEach((b) => b.classList.toggle('active', b.dataset.value === value));
}

// --- Input ---------------------------------------------------------------------------

function handleKey(key) {
  if (state.over) return;
  if (key === 'Enter') return submit();
  if (key === 'Backspace') {
    if (!state.current) return;
    state.current = state.current.slice(0, -1);
    state.colours[state.current.length] = 'B';
    return renderBoard();
  }
  if (/^[a-z]$/.test(key) && state.current.length < WORD_LENGTH) {
    const i = state.current.length;
    state.current += key;
    state.colours[i] = knownGreen(i, key) ? 'G' : 'B';
    renderBoard();
    popTile(state.rows.length, i);
  }
}

function knownGreen(position, letter) {
  return state.rows.some((row) => row.word[position] === letter && row.feedback[position] === 'G');
}

function cycleColour(r, c) {
  if (state.gameMode !== 'assist' || state.over) return;
  if (r !== state.rows.length || state.current.length !== WORD_LENGTH) return;
  state.colours[c] = NEXT_COLOUR[state.colours[c]];
  renderBoard();
}

function fillWord(word) {
  if (state.over || state.rows.length >= MAX_ROWS) return;
  state.current = word;
  state.colours = [...word].map((ch, i) => (knownGreen(i, ch) ? 'G' : 'B'));
  renderBoard();
}

function bestSuggestion() {
  const list = state.rankBy === 'two' && state.twoStep ? state.twoStep : state.analysis?.one_step;
  return list?.[0]?.word;
}

function submit() {
  const word = state.current;
  const row = state.rows.length;
  if (word.length < WORD_LENGTH) return reject(row, 'Not enough letters');
  if (!state.guesses.has(word)) return reject(row, 'Not in word list');

  const colours = state.gameMode === 'play' ? feedback(word, state.secret) : state.colours.join('');
  state.rows.push({ word, feedback: colours });
  state.current = '';
  state.colours = Array(WORD_LENGTH).fill('B');

  const solved = colours === 'G'.repeat(WORD_LENGTH);
  const outOfRows = state.rows.length === MAX_ROWS;
  state.over = solved || outOfRows;

  revealRow(row, colours, () => {
    if (solved) {
      boardEl.children[row].classList.add('won');
      toast(`Solved in ${row + 1}!`);
    } else if (outOfRows) {
      toast(state.gameMode === 'play' ? `The answer was ${state.secret.toUpperCase()}` : 'Out of rows', 3000);
    }
  });
  refresh();
}

function reject(row, message) {
  const rowEl = boardEl.children[row];
  rowEl.classList.remove('shake');
  void rowEl.offsetWidth; // restart the animation
  rowEl.classList.add('shake');
  toast(message);
}

function undo() {
  if (!state.rows.length) return;
  state.rows.pop();
  state.current = '';
  state.colours = Array(WORD_LENGTH).fill('B');
  state.over = false;
  boardEl.querySelectorAll('.won').forEach((el) => el.classList.remove('won'));
  renderBoard();
  refresh();
}

function newGame() {
  state.rows = [];
  state.current = '';
  state.colours = Array(WORD_LENGTH).fill('B');
  state.over = false;
  state.secret = state.gameMode === 'play'
    ? state.answers[Math.floor(Math.random() * state.answers.length)]
    : null;
  boardEl.querySelectorAll('.won').forEach((el) => el.classList.remove('won'));
  renderBoard();
  refresh();
}

// --- Board rendering -----------------------------------------------------------------

function renderBoard() {
  const currentRow = state.rows.length;
  for (let r = 0; r < MAX_ROWS; r++) {
    const submitted = state.rows[r];
    const isCurrent = r === currentRow && !state.over;
    const editable = isCurrent && state.gameMode === 'assist' && state.current.length === WORD_LENGTH;
    boardEl.children[r].classList.toggle('current', isCurrent);

    for (let c = 0; c < WORD_LENGTH; c++) {
      const tile = tiles[r][c];
      let letter = '';
      let colour = '';
      if (submitted) {
        letter = submitted.word[c];
        colour = submitted.feedback[c];
      } else if (isCurrent) {
        letter = state.current[c] || '';
        // In Assist mode the colours being set show on the tiles once the word is complete.
        if (editable) colour = state.colours[c];
      }
      tile.textContent = letter;
      tile.classList.toggle('filled', Boolean(letter) && !colour);
      tile.classList.toggle('editable', editable);
      if (colour) tile.dataset.state = colour;
      else delete tile.dataset.state;
    }
  }
  renderKeyboard();
  renderHint();
}

function revealRow(r, colours, done) {
  tiles[r].forEach((tile, c) => {
    delete tile.dataset.state;
    tile.classList.remove('editable');
    tile.classList.add('filled');
    setTimeout(() => {
      tile.classList.add('flip');
      setTimeout(() => {
        tile.classList.remove('filled');
        tile.dataset.state = colours[c];
      }, 220);
      setTimeout(() => tile.classList.remove('flip'), 460);
    }, c * 130);
  });
  setTimeout(() => {
    renderBoard();
    done();
  }, WORD_LENGTH * 130 + 480);
}

function popTile(r, c) {
  const tile = tiles[r][c];
  tile.classList.remove('pop');
  void tile.offsetWidth;
  tile.classList.add('pop');
}

function renderKeyboard() {
  const best = {};
  for (const { word, feedback: colours } of state.rows) {
    [...word].forEach((ch, i) => {
      if (!best[ch] || COLOUR_RANK[colours[i]] > COLOUR_RANK[best[ch]]) best[ch] = colours[i];
    });
  }
  $('keyboard').querySelectorAll('.key').forEach((key) => {
    const colour = best[key.dataset.key];
    if (colour) key.dataset.state = colour;
    else delete key.dataset.state;
  });
}

function renderHint() {
  const hint = $('hint');
  if (state.over) {
    hint.innerHTML = 'Press <kbd>New game</kbd> to go again, or <kbd>Ctrl</kbd>+<kbd>Z</kbd> to undo.';
  } else if (state.gameMode === 'assist' && state.current.length === WORD_LENGTH) {
    hint.innerHTML = 'Click tiles (or press <kbd>1</kbd>–<kbd>5</kbd>) to match the colours, then <kbd>Enter</kbd>.';
  } else {
    hint.innerHTML = 'Type a guess, or press <kbd>Tab</kbd> to use the top suggestion.';
  }
}

// --- Solver panel --------------------------------------------------------------------

async function post(path, body) {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(typeof detail.detail === 'string' ? detail.detail : `Request failed (${response.status})`);
  }
  return response.json();
}

async function refresh() {
  const id = ++state.requestId;
  const query = {
    mode: state.answerMode,
    history: state.rows.map(({ word, feedback: colours }) => ({ guess: word, feedback: colours })),
    top: 10,
  };
  state.twoStep = null;
  state.twoStepLoading = true;
  renderPanel();

  try {
    const analysis = await post('/api/analyze', query);
    if (id !== state.requestId) return;
    state.analysis = analysis;
    if (analysis.remaining === 0) state.twoStepLoading = false;
    renderPanel();
    if (analysis.remaining === 0) return;

    const { two_step: twoStep } = await post('/api/two-step', query);
    if (id !== state.requestId) return;
    state.twoStep = twoStep;
  } catch (err) {
    if (id !== state.requestId) return;
    toast(err.message, 3000);
  }
  state.twoStepLoading = false;
  renderPanel();
}

function renderPanel() {
  const a = state.analysis;
  $('remaining').textContent = a ? a.remaining.toLocaleString() : '–';
  $('space-left').textContent = a ? formatShare(a.remaining / a.total) : '–';
  $('uncertainty').textContent = a ? a.uncertainty.toFixed(2) : '–';

  const notice = $('notice');
  const solved = state.rows.at(-1)?.feedback === 'G'.repeat(WORD_LENGTH);
  notice.hidden = !(solved || a?.remaining === 0);
  notice.classList.toggle('success', solved);
  notice.textContent = solved
    ? `Solved in ${state.rows.length}.`
    : 'No answers match these colours. Check the tiles, or undo the last guess.';

  renderPick('pick-one', a?.one_step?.[0], (s) => `${s.one_step.toFixed(2)} bits`, false);
  renderPick('pick-two', state.twoStep?.[0], (s) => `${s.two_step.toFixed(2)} bits over 2 guesses`, state.twoStepLoading);
  $('pick-one').classList.toggle('active', state.rankBy === 'one');
  $('pick-two').classList.toggle('active', state.rankBy === 'two');

  renderSuggestions();
  renderCandidates();
  renderGameStats();
}

function renderPick(id, suggestion, describe, loading) {
  const el = $(id);
  el.querySelector('.pick-word').textContent = suggestion ? suggestion.word : '–';
  el.querySelector('.pick-score').innerHTML = loading
    ? '<span class="spinner"></span> thinking…'
    : suggestion ? describe(suggestion) : '';
  el.dataset.word = suggestion ? suggestion.word : '';
}

function renderSuggestions() {
  const body = $('suggestions');
  const oneStep = state.analysis?.one_step ?? [];
  const twoStepByWord = new Map((state.twoStep ?? []).map((s) => [s.word, s]));
  const list = (state.rankBy === 'two' ? state.twoStep ?? [] : oneStep).slice(0, 10);

  if (!list.length) {
    const message = state.rankBy === 'two' && state.twoStepLoading
      ? '<span class="spinner"></span> Looking two guesses ahead…'
      : 'No suggestions';
    body.innerHTML = `<tr class="placeholder"><td colspan="6">${message}</td></tr>`;
    return;
  }

  body.innerHTML = '';
  list.forEach((s, i) => {
    const two = twoStepByWord.get(s.word)?.two_step;
    const tr = document.createElement('tr');
    if (i === 0) tr.className = 'top';
    tr.innerHTML = `
      <td class="word">${s.word}</td>
      <td>${s.one_step.toFixed(2)}</td>
      <td>${two != null ? two.toFixed(2) : state.twoStepLoading ? '<span class="spinner"></span>' : '–'}</td>
      <td>${formatCount(s.expected_left)}</td>
      <td>${s.worst_left ?? '–'}</td>
      <td>${formatPercent(s.p_answer)}</td>`;
    tr.addEventListener('click', () => fillWord(s.word));
    body.appendChild(tr);
  });
}

function renderCandidates() {
  const a = state.analysis;
  const el = $('candidates');
  el.innerHTML = '';
  $('candidate-count').textContent = a ? `${a.remaining.toLocaleString()} total` : '';
  if (!a) return;

  for (const { word, p } of a.candidates) {
    const chip = document.createElement('button');
    chip.className = 'chip';
    chip.type = 'button';
    chip.innerHTML = a.uniform ? word : `${word}<small>${formatPercent(p)}</small>`;
    chip.addEventListener('click', () => fillWord(word));
    el.appendChild(chip);
  }
  if (a.remaining > a.candidates.length) {
    const more = document.createElement('span');
    more.className = 'chip more';
    more.textContent = `+${(a.remaining - a.candidates.length).toLocaleString()} more`;
    el.appendChild(more);
  }
}

function formatPercent(p) {
  if (!p) return '–';
  const pct = p * 100;
  return pct >= 10 ? `${pct.toFixed(0)}%` : pct >= 0.1 ? `${pct.toFixed(1)}%` : '<0.1%';
}

// Like formatPercent, but keeps the small shares a late game produces readable (0.043%).
function formatShare(p) {
  const pct = p * 100;
  if (pct === 0) return '0%';
  if (pct >= 10) return `${pct.toFixed(0)}%`;
  if (pct >= 1) return `${pct.toFixed(1)}%`;
  if (pct >= 0.01) return `${pct.toFixed(2)}%`;
  return '<0.01%';
}

function formatCount(n) {
  if (n == null) return '–';
  return n >= 10 ? Math.round(n).toLocaleString() : n.toFixed(1);
}

function compact(n) {
  return n >= 1000 ? `${+(n / 1000).toFixed(1)}K` : String(n);
}

// --- Game stats charts ---------------------------------------------------------------

const SVG_NS = 'http://www.w3.org/2000/svg';
const BIT_SERIES = [
  { key: 'expected_bits', name: 'Expected from your guess', colour: 'var(--series-1)' },
  { key: 'best_bits', name: 'Best any guess could expect', colour: 'var(--series-2)' },
  { key: 'actual_bits', name: 'Actually gained', colour: 'var(--series-3)' },
];

function svgEl(tag, attrs = {}, parent) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [name, value] of Object.entries(attrs)) el.setAttribute(name, value);
  if (parent) parent.appendChild(el);
  return el;
}

function renderGameStats() {
  const a = state.analysis;
  const turns = a?.turns ?? [];
  $('stats-empty').hidden = turns.length > 0;
  $('charts').hidden = turns.length === 0;
  if (!turns.length) return;
  renderRemainingChart(a, turns);
  renderBitsChart(turns);
  renderTurnLog(a, turns);
}

/** Shows one tooltip inside a chart: a bold value line, then label rows. Built with textContent. */
function showTip(chart, x, y, value, rows) {
  let tip = chart.querySelector('.chart-tip');
  if (!tip) {
    tip = document.createElement('div');
    tip.className = 'chart-tip';
    chart.appendChild(tip);
  }
  tip.replaceChildren();
  const strong = document.createElement('strong');
  strong.textContent = value;
  tip.appendChild(strong);
  for (const { label, detail, colour } of rows) {
    const row = document.createElement('div');
    row.className = 'tip-row';
    if (colour) {
      const key = document.createElement('span');
      key.className = 'tip-key';
      key.style.setProperty('--c', colour);
      row.appendChild(key);
    }
    const b = document.createElement('b');
    b.textContent = detail;
    row.append(label + ' ', b);
    tip.appendChild(row);
  }
  // The tip is centred on x; keep it inside the chart so it never pushes the page wider.
  tip.hidden = false;
  const half = tip.offsetWidth / 2;
  tip.style.left = `${Math.min(Math.max(x, half), chart.clientWidth - half)}px`;
  tip.style.top = `${y}px`;
}

function hideTip(chart) {
  const tip = chart.querySelector('.chart-tip');
  if (tip) tip.hidden = true;
}

function renderRemainingChart(a, turns) {
  const chart = $('chart-remaining');
  chart.replaceChildren();
  const width = chart.clientWidth || 440;
  const height = 190;
  const m = { top: 12, right: 44, bottom: 26, left: 40 };

  const points = [
    { label: 'Start', left: a.total, bits: a.total_uncertainty },
    ...turns.map((t, i) => ({ label: t.guess.toUpperCase(), left: t.after, bits: t.uncertainty_after, turn: i + 1 })),
  ];
  const logMax = Math.log10(a.total);
  const x = (i) => m.left + (i * (width - m.left - m.right)) / Math.max(points.length - 1, 1);
  // Log scale; zero answers (inconsistent colours) sits on the floor at 1.
  const y = (v) => m.top + (1 - Math.log10(Math.max(v, 1)) / logMax) * (height - m.top - m.bottom);

  const svg = svgEl('svg', { viewBox: `0 0 ${width} ${height}`, height, role: 'img',
    'aria-label': `Answers remaining after each guess: ${points.map((p) => `${p.label} ${p.left}`).join(', ')}` }, chart);

  for (let tick = 1; tick <= a.total; tick *= 10) {
    svgEl('line', { class: 'grid', x1: m.left, x2: width - m.right, y1: y(tick), y2: y(tick) }, svg);
    svgEl('text', { x: m.left - 8, y: y(tick) + 4, 'text-anchor': 'end' }, svg).textContent = compact(tick);
  }
  points.forEach((p, i) => {
    svgEl('text', { x: x(i), y: height - 6, 'text-anchor': 'middle' }, svg).textContent = p.label;
  });

  const path = points.map((p, i) => `${i ? 'L' : 'M'}${x(i)},${y(p.left)}`).join(' ');
  svgEl('path', { d: path, fill: 'none', stroke: 'var(--series-1)', 'stroke-width': 2,
    'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, svg);

  const markers = points.map((p, i) => svgEl('circle', { class: 'marker', cx: x(i), cy: y(p.left), r: 4,
    fill: 'var(--series-1)', stroke: 'var(--surface)', 'stroke-width': 2 }, svg));

  const last = points.at(-1);
  svgEl('text', { class: 'end-label', x: x(points.length - 1) + 10, y: y(last.left) + 4 }, svg)
    .textContent = last.left.toLocaleString();

  // Hit areas: a full-height band per point, so the pointer only has to be near it.
  const band = (width - m.left - m.right) / Math.max(points.length - 1, 1);
  points.forEach((p, i) => {
    const hit = svgEl('rect', { class: 'hit', x: x(i) - band / 2, y: 0, width: band, height }, svg);
    hit.addEventListener('pointerenter', () => {
      markers[i].classList.add('hover');
      const title = p.turn ? `After guess ${p.turn} (${p.label})` : 'Before any guesses';
      showTip(chart, x(i), y(p.left), `${p.left.toLocaleString()} ${p.left === 1 ? 'answer' : 'answers'}`, [
        { label: title, detail: '' },
        { label: 'Answer space left', detail: formatShare(p.left / a.total) },
        { label: 'Uncertainty', detail: `${p.bits.toFixed(2)} bits` },
      ]);
    });
    hit.addEventListener('pointerleave', () => {
      markers[i].classList.remove('hover');
      hideTip(chart);
    });
  });
}

function renderBitsChart(turns) {
  const legend = $('bits-legend');
  legend.replaceChildren(...BIT_SERIES.map(({ name, colour }) => {
    const item = document.createElement('span');
    const swatch = document.createElement('i');
    swatch.style.setProperty('--c', colour);
    item.append(swatch, name);
    return item;
  }));

  const chart = $('chart-bits');
  chart.replaceChildren();
  const width = chart.clientWidth || 440;
  const height = 170;
  const m = { top: 10, right: 8, bottom: 26, left: 32 };

  const values = turns.flatMap((t) => BIT_SERIES.map((s) => t[s.key] ?? 0));
  const yMax = Math.max(1, Math.ceil(Math.max(...values)));
  const step = yMax <= 6 ? 1 : 2;
  const y = (v) => m.top + (1 - v / yMax) * (height - m.top - m.bottom);
  const group = (width - m.left - m.right) / turns.length;
  const barWidth = Math.min(24, (group * 0.7 - 4) / 3);

  const svg = svgEl('svg', { viewBox: `0 0 ${width} ${height}`, height, role: 'img',
    'aria-label': 'Bits per guess: expected, best available and actual for each guess' }, chart);

  for (let tick = 0; tick <= yMax; tick += step) {
    svgEl('line', { class: 'grid', x1: m.left, x2: width - m.right, y1: y(tick), y2: y(tick) }, svg);
    svgEl('text', { x: m.left - 8, y: y(tick) + 4, 'text-anchor': 'end' }, svg).textContent = tick;
  }

  turns.forEach((t, i) => {
    const centre = m.left + group * (i + 0.5);
    svgEl('text', { x: centre, y: height - 6, 'text-anchor': 'middle' }, svg).textContent = t.guess.toUpperCase();

    BIT_SERIES.forEach((s, j) => {
      const value = t[s.key];
      if (value == null) return;
      // Bars in a group touch, separated by a 2px gap.
      const left = centre + (j - 1.5) * (barWidth + 2) + 1;
      const top = y(value);
      const h = y(0) - top;
      const r = Math.min(4, h, barWidth / 2);
      const bar = svgEl('path', {
        class: 'bar',
        fill: s.colour,
        d: `M${left},${y(0)} V${top + r} Q${left},${top} ${left + r},${top} H${left + barWidth - r} ` +
           `Q${left + barWidth},${top} ${left + barWidth},${top + r} V${y(0)} Z`,
      }, svg);

      const hit = svgEl('rect', { class: 'hit', x: left - 1, y: m.top, width: barWidth + 2, height: y(0) - m.top }, svg);
      hit.addEventListener('pointerenter', () => {
        bar.classList.add('hover');
        const detail = s.key === 'best_bits' ? `(${t.best_word.toUpperCase()})` : '';
        showTip(chart, left + barWidth / 2, top, `${value.toFixed(2)} bits`, [
          { label: s.name, detail, colour: s.colour },
          { label: `Guess ${i + 1}:`, detail: t.guess.toUpperCase() },
        ]);
      });
      hit.addEventListener('pointerleave', () => {
        bar.classList.remove('hover');
        hideTip(chart);
      });
    });
  });
}

function renderTurnLog(a, turns) {
  const body = $('turn-log');
  body.replaceChildren();
  turns.forEach((t, i) => {
    const tr = document.createElement('tr');
    const cells = [
      String(i + 1),
      null, // the guess, drawn as mini tiles below
      t.expected_bits.toFixed(2),
      `${t.best_bits.toFixed(2)}`,
      t.actual_bits == null ? '–' : t.actual_bits.toFixed(2),
      t.after.toLocaleString(),
      formatShare(t.after / a.total),
    ];
    cells.forEach((text, c) => {
      const td = document.createElement('td');
      if (c === 1) {
        const word = document.createElement('span');
        word.className = 'mini-word';
        word.title = t.guess.toUpperCase();
        [...t.guess].forEach((ch, k) => {
          const tile = document.createElement('span');
          tile.dataset.state = t.feedback[k];
          tile.textContent = ch;
          word.appendChild(tile);
        });
        td.appendChild(word);
      } else {
        td.textContent = text;
      }
      if (c === 3) td.title = `Best guess was ${t.best_word.toUpperCase()}`;
      tr.appendChild(td);
    });
    body.appendChild(tr);
  });
}

// Charts size to their container, so redraw them when it changes width.
let lastChartWidth = 0;
new ResizeObserver(([entry]) => {
  const width = Math.round(entry.contentRect.width);
  if (width !== lastChartWidth && state.analysis?.turns?.length) {
    lastChartWidth = width;
    renderGameStats();
  }
}).observe($('charts'));

let toastTimer;
function toast(message, duration = 1800) {
  const el = $('toast');
  el.textContent = message;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), duration);
}

// --- Wiring --------------------------------------------------------------------------

document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
    e.preventDefault();
    return undo();
  }
  if (e.ctrlKey || e.metaKey || e.altKey) return;

  if (e.key === 'Tab') {
    e.preventDefault();
    const word = bestSuggestion();
    if (word) fillWord(word);
    return;
  }
  if (/^[1-5]$/.test(e.key)) return cycleColour(state.rows.length, Number(e.key) - 1);
  if (e.key === 'Enter' || e.key === 'Backspace') {
    e.preventDefault();
    return handleKey(e.key);
  }
  if (/^[a-zA-Z]$/.test(e.key)) handleKey(e.key.toLowerCase());
});

bindSegment('game-mode', (value) => { state.gameMode = value; newGame(); });
bindSegment('answer-mode', (value) => { state.answerMode = value; refresh(); });
bindSegment('rank-by', (value) => { state.rankBy = value; renderPanel(); });
$('undo').addEventListener('click', (e) => { e.currentTarget.blur(); undo(); });
$('new-game').addEventListener('click', (e) => { e.currentTarget.blur(); newGame(); });
document.querySelectorAll('.pick').forEach((pick) => {
  pick.addEventListener('click', () => {
    state.rankBy = pick.dataset.strategy;
    setSegment('rank-by', state.rankBy);
    renderPanel();
    if (pick.dataset.word) fillWord(pick.dataset.word);
  });
});

async function init() {
  buildBoard();
  buildKeyboard();
  renderBoard();
  try {
    const words = await (await fetch('/api/words')).json();
    state.guesses = new Set(words.guesses);
    state.answers = words.answers;
  } catch {
    toast('Could not reach the solver server', 4000);
    return;
  }
  newGame();
}

init();
