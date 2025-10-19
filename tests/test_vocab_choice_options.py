"""Tests that inspect the vocab-choice option list sizing logic.

The front-end logic that determines how many options to show for a
``vocab-choice`` question lives in ``app/static/index.html``.  To test that
behaviour without a browser we spin up Node, provide a very small DOM stub, and
evaluate the real client script inside a ``vm`` context.  The helper below
invokes ``renderQuestion`` for a single vocab-choice entry and captures the
buttons that would have been rendered to the choice list.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parent.parent


def run_node(code: str) -> str:
    """Execute ``code`` in Node and return its stdout."""

    result = subprocess.run(
        ["node", "-e", code],
        check=True,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    return result.stdout.strip()


NODE_TEMPLATE = r"""
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const deckData = __DECK_DATA__;
const statsMapInit = __STATS_MAP__;
const mathRandomValue = __MATH_RANDOM__;
const questionIndex = __QUESTION_INDEX__;

class FakeElement {
  constructor(tag) {
    this.tag = tag;
    this.id = '';
    this.style = {};
    this.attributes = new Map();
    this.children = [];
    this.parent = null;
    this.textContent = '';
    this._innerHTML = '';
    this.disabled = false;
    this.tabIndex = 0;
    this.value = '';
    this.onclick = null;
    this._classSet = new Set();
  }
  set innerHTML(value) {
    const str = String(value ?? '');
    this._innerHTML = str;
    if (str === '') {
      this.children.forEach(child => { child.parent = null; });
      this.children = [];
    }
  }
  get innerHTML() {
    return this._innerHTML;
  }
  setAttribute(name, value) {
    const key = String(name);
    const val = String(value);
    this.attributes.set(key, val);
    if (key === 'id') {
      this.id = val;
    } else if (key === 'class') {
      this.className = val;
    }
  }
  getAttribute(name) {
    const key = String(name);
    if (key === 'id') return this.id || null;
    if (key === 'class') return this.className;
    return this.attributes.has(key) ? this.attributes.get(key) : null;
  }
  appendChild(child) {
    if (!child) return child;
    child.parent = this;
    this.children.push(child);
    registerElement(child);
    return child;
  }
  removeChild(child) {
    const idx = this.children.indexOf(child);
    if (idx >= 0) {
      this.children.splice(idx, 1);
      child.parent = null;
    }
  }
  remove() {
    if (this.parent) {
      this.parent.removeChild(this);
    }
  }
  addEventListener() {}
  removeEventListener() {}
  focus() {}
  blur() {}
  get className() {
    return Array.from(this._classSet).join(' ');
  }
  set className(value) {
    const str = String(value ?? '');
    this._classSet = new Set(str.split(/\s+/).filter(Boolean));
    if (str) {
      this.attributes.set('class', str);
    } else {
      this.attributes.delete('class');
    }
  }
  get classList() {
    const element = this;
    return {
      add(cls) {
        element._classSet.add(cls);
        element.attributes.set('class', element.className);
      },
      remove(cls) {
        element._classSet.delete(cls);
        const clsName = element.className;
        if (clsName) {
          element.attributes.set('class', clsName);
        } else {
          element.attributes.delete('class');
        }
      },
      contains(cls) {
        return element._classSet.has(cls);
      },
      toggle(cls, force) {
        if (force === undefined) {
          if (element._classSet.has(cls)) {
            element._classSet.delete(cls);
            const clsName = element.className;
            if (clsName) {
              element.attributes.set('class', clsName);
            } else {
              element.attributes.delete('class');
            }
            return false;
          }
          element._classSet.add(cls);
          element.attributes.set('class', element.className);
          return true;
        }
        if (force) {
          element._classSet.add(cls);
          element.attributes.set('class', element.className);
        } else {
          element._classSet.delete(cls);
          const clsName = element.className;
          if (clsName) {
            element.attributes.set('class', clsName);
          } else {
            element.attributes.delete('class');
          }
        }
        return !!force;
      },
    };
  }
}

const elementsById = new Map();
const allElements = new Set();

function registerElement(el) {
  if (el) {
    allElements.add(el);
  }
}

function ensureElement(id) {
  if (!elementsById.has(id)) {
    const el = new FakeElement('div');
    el.id = id;
    elementsById.set(id, el);
    registerElement(el);
  }
  return elementsById.get(id);
}

function gatherByClass(root, className, acc) {
  if (!root) return;
  root.children.forEach(child => {
    if (child._classSet && child._classSet.has(className)) {
      acc.push(child);
    }
    gatherByClass(child, className, acc);
  });
}

function querySelector(selector) {
  if (typeof selector !== 'string') return null;
  const trimmed = selector.trim();
  if (trimmed.startsWith('#')) {
    return ensureElement(trimmed.slice(1));
  }
  if (trimmed.startsWith('.')) {
    const target = trimmed.slice(1);
    for (const node of allElements) {
      if (node._classSet && node._classSet.has(target)) {
        return node;
      }
    }
    return null;
  }
  const parts = trimmed.split(/\s+/);
  if (parts.length === 2 && parts[0].startsWith('#') && parts[1].startsWith('.')) {
    const root = ensureElement(parts[0].slice(1));
    const results = [];
    gatherByClass(root, parts[1].slice(1), results);
    return results.length ? results[0] : null;
  }
  return null;
}

function querySelectorAll(selector) {
  if (typeof selector !== 'string') return [];
  const trimmed = selector.trim();
  if (trimmed.startsWith('#')) {
    return [ensureElement(trimmed.slice(1))];
  }
  if (trimmed.startsWith('.')) {
    const target = trimmed.slice(1);
    return Array.from(allElements).filter(node => node._classSet && node._classSet.has(target));
  }
  const parts = trimmed.split(/\s+/);
  if (parts.length === 2 && parts[0].startsWith('#') && parts[1].startsWith('.')) {
    const root = ensureElement(parts[0].slice(1));
    const results = [];
    gatherByClass(root, parts[1].slice(1), results);
    return results;
  }
  return [];
}

const documentStub = {
  getElementById(id) {
    return ensureElement(id);
  },
  querySelector,
  querySelectorAll,
  createElement(tag) {
    const el = new FakeElement(tag);
    registerElement(el);
    return el;
  },
};

const localStore = new Map();
const localStorageStub = {
  getItem(key) {
    return localStore.has(key) ? localStore.get(key) : null;
  },
  setItem(key, value) {
    localStore.set(key, String(value));
  },
  removeItem(key) {
    localStore.delete(key);
  },
};

const statsMap = new Map(Object.entries(statsMapInit || {}));

async function fetchStub(url, options = {}) {
  if (typeof url === 'string' && url.includes('/data/english/questions.json')) {
    return {
      ok: true,
      async json() {
        return { vocabChoice: deckData, vocabInput: [], reorder: [], rewrite: [] };
      },
    };
  }
  if (url === '/api/stats/bulk') {
    const body = JSON.parse(options.body || '{}');
    const ids = Array.isArray(body.ids) ? body.ids : [];
    const results = ids.map(id => {
      const key = String(id);
      const stat = statsMap.get(key) || { stage: 'F', streak: 0, nextDueAt: null };
      return { id: key, stage: stat.stage, streak: stat.streak, nextDueAt: stat.nextDueAt };
    });
    return { ok: true, async json() { return { results }; } };
  }
  if (typeof url === 'string' && url.startsWith('/api/stats/stage-f')) {
    return { ok: true, async json() { return { keys: [] }; } };
  }
  if (typeof url === 'string' && url.startsWith('/api/wrong-queue')) {
    return { ok: true, async json() { return { items: [] }; } };
  }
  if (typeof url === 'string' && url.startsWith('/api/history')) {
    return { ok: true, async json() { return { history: [] }; } };
  }
  return { ok: true, async json() { return {}; } };
}

const context = {
  console: { log() {}, warn() {}, error() {} },
  Math: Object.assign(Object.create(Math), { random: () => mathRandomValue }),
  document: documentStub,
  localStorage: localStorageStub,
  fetch: fetchStub,
  alert: () => {},
  performance: { now: () => 0 },
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval,
  AbortController,
  URL,
};

context.window = {
  document: documentStub,
  addEventListener() {},
  location: { href: '' },
  __stagePriority: require('./app/static/stage_priority.js'),
};
context.window.window = context.window;
context.window.__quizFallbackExtras = require('./app/static/fallback_extras.js');
context.__quizFallbackExtras = context.window.__quizFallbackExtras;
context.SpeechSynthesisUtterance = function() {};
context.globalThis = context;

vm.createContext(context);

const htmlPath = path.join(__dirname, 'app/static/index.html');
const html = fs.readFileSync(htmlPath, 'utf8');
const scriptMatch = html.match(/<script>\s*([\s\S]*)\s*<\/script>\s*<\/body>/);
if (!scriptMatch) {
  throw new Error('script block not found');
}
vm.runInContext(scriptMatch[1], context, { filename: 'index.html' });

const requiredIds = [
  'setup','quiz','finished','status','explain','ui-reorder','ui-vocab','ui-vocab-choice','ui-rewrite',
  'prompt','vocab-choice-tip','vocab-choice-options','btn-hint','btn-next','btn-check',
  'stat-correct','stat-wrong','stat-streak','stat-accuracy','stat-bucket','stat-stage',
  'vocab-input','rewrite-input'
];
requiredIds.forEach(id => { const el = documentStub.getElementById(id); el.id = id; });

(async () => {
  await vm.runInContext('ensureQuestions()', context);
  await vm.runInContext(`
    state.qType = 'vocab-choice';
    state.mode = 'normal';
    state.user = 'tester';
    state.totalPerSet = 5;
    state.unitFilter = '';
    state.levelMax = 'Lv5';
    state.fallbackExtras = [];
    state.fallbackStageOverrides = new Map();
    show('quiz');
  `, context);

  await vm.runInContext(`
    (async () => {
      const deckArray = deck();
      const indexes = [${questionIndex}];
      state.order = await createOrderEntriesFromIndexes(indexes, deckArray);
      state.qIndex = 0;
      renderQuestion();
    })();
  `, context);

  const result = vm.runInContext(`
    (() => {
      const optionsEl = document.getElementById('vocab-choice-options');
      const optionNodes = optionsEl ? optionsEl.children.slice() : [];
      return {
        optionCount: optionNodes.length,
        optionValues: optionNodes.map(opt => opt.getAttribute('data-value')),
        optionTexts: optionNodes.map(opt => opt.textContent),
      };
    })();
  `, context);

  process.stdout.write(JSON.stringify(result));
})().catch(err => {
  process.stderr.write(String(err && err.stack ? err.stack : err));
  process.exit(1);
});
"""


def render_vocab_choice_options(
    deck_data: List[Dict[str, Any]],
    stats_map: Dict[str, Dict[str, Any]],
    *,
    math_random: float = 0.23456,
    question_index: int = 0,
) -> Dict[str, Any]:
    """Run the vocab-choice renderer and return the captured option metadata."""

    deck_json = json.dumps(deck_data, ensure_ascii=False)
    stats_json = json.dumps(stats_map, ensure_ascii=False)
    node_code = NODE_TEMPLATE
    for placeholder, value in [
        ("__DECK_DATA__", deck_json),
        ("__STATS_MAP__", stats_json),
        ("__MATH_RANDOM__", repr(math_random)),
        ("__QUESTION_INDEX__", str(question_index)),
    ]:
        node_code = node_code.replace(placeholder, value)
    output = run_node(node_code)
    return json.loads(output)


def build_deck() -> List[Dict[str, Any]]:
    base = {"id": "base", "en": "alpha", "jp": "意味A", "unit": "U1", "level": "Lv1"}
    distractors = [
        {
            "id": f"d{i}",
            "en": f"word{i}",
            "jp": f"意味{i}",
            "unit": f"U{(i % 3) + 1}",
            "level": "Lv1",
        }
        for i in range(1, 8)
    ]
    return [base, *distractors]


def test_vocab_choice_options_respect_minimum_count():
    deck = build_deck()
    stats = {"base": {"stage": "F", "streak": 0, "nextDueAt": None}}

    result = render_vocab_choice_options(deck, stats)

    assert result["optionCount"] == 3
    assert "意味A" in result["optionValues"]


def test_vocab_choice_options_scale_with_streak():
    deck = build_deck()
    stats = {"base": {"stage": "F", "streak": 2, "nextDueAt": None}}

    result = render_vocab_choice_options(deck, stats)

    assert result["optionCount"] == 5
    assert "意味A" in result["optionValues"]
