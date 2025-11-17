import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List


def run_node(code: str) -> str:
    result = subprocess.run(
        ["node", "-e", code],
        check=True,
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent.parent,
    )
    return result.stdout.strip()


def execute_build_order(
    deck_data: List[Dict[str, Any]],
    stats_map: Dict[str, Dict[str, Any]],
    *,
    total_per_set: int = 5,
    math_random: float = 0.11111,
) -> Dict[str, Any]:
    deck_json = json.dumps(deck_data)
    stats_json = json.dumps(stats_map)
    node_code = f"""
    const fs = require('fs');
    const path = require('path');
    const vm = require('vm');

    const deckData = {deck_json};
    const statsMapInit = {stats_json};

    class Element {{
      constructor(id){{
        this.id = id;
        this.children = [];
        this.style = {{}};
        this.attributes = {{}};
        this._textContent = '';
        this.value = '';
        this.disabled = false;
        this.innerHTML = '';
      }}
      appendChild(child){{ this.children.push(child); return child; }}
      removeChild(child){{ this.children = this.children.filter(c => c !== child); }}
      set textContent(val){{ this._textContent = val; }}
      get textContent(){{ return this._textContent; }}
      addEventListener(){{ }}
      removeEventListener(){{ }}
      setAttribute(name, value){{ this.attributes[name] = value; }}
      getAttribute(name){{ return this.attributes[name]; }}
      focus(){{ }}
      blur(){{ }}
      remove(){{ }}
      get classList(){{
        return {{
          add(){{}},
          remove(){{}},
          contains(){{ return false; }},
        }};
      }}
    }}

    const elements = new Map();
    const getElement = (id)=>{{
      if(!elements.has(id)){{
        elements.set(id, new Element(id));
      }}
      return elements.get(id);
    }};

    const documentStub = {{
      getElementById(id){{ return getElement(id); }},
      querySelector(selector){{ return selector.startsWith('#') ? getElement(selector.slice(1)) : new Element(selector); }},
      querySelectorAll(){{ return []; }},
      createElement(tag){{ return new Element(tag); }},
    }};

    const localStore = new Map();
    const localStorageStub = {{
      getItem(key){{ return localStore.has(key) ? localStore.get(key) : null; }},
      setItem(key, value){{ localStore.set(key, String(value)); }},
      removeItem(key){{ localStore.delete(key); }},
    }};

    const statsMap = new Map(Object.entries(statsMapInit || {{}}));

    const fetchStub = async (url, options={{}})=>{{
      if(typeof url === 'string' && url.includes('/data/english/questions.json')){{
        return {{ ok: true, json: async ()=>({{ vocabChoice: deckData, reorder: [], rewrite: [] }}) }};
      }}
      if(url === '/api/stats/bulk'){{
        const body = JSON.parse(options.body || '{{}}');
        const ids = Array.isArray(body.ids) ? body.ids : [];
        const results = ids.map(id => {{
          const key = String(id);
          const stat = statsMap.get(key) || {{ stage: 'F', streak: 0, nextDueAt: null }};
          return {{ id: key, stage: stat.stage, streak: stat.streak, nextDueAt: stat.nextDueAt }};
        }});
        return {{ ok: true, json: async ()=>({{ results }}) }};
      }}
      return {{ ok: true, json: async ()=>({{}}) }};
    }};

    const context = {{
      console: {{ log(){{}}, warn(){{}}, error(){{}} }},
      Math: Object.assign(Object.create(Math), {{ random: () => {math_random} }}),
      document: documentStub,
      localStorage: localStorageStub,
      fetch: fetchStub,
      alert: ()=>{{}},
      performance: {{ now: () => 0 }},
    }};
    context.window = {{
      document: documentStub,
      addEventListener(){{}},
      location: {{ href: '' }},
      __stagePriority: require('./app/static/stage_priority.js'),
    }};
    context.window.window = context.window;
    context.globalThis = context;
    context.SpeechSynthesisUtterance = function(){{}};
    context.AbortController = AbortController;

    vm.createContext(context);
    const htmlPath = path.join(__dirname, 'app/static/index.html');
    const html = fs.readFileSync(htmlPath, 'utf8');
    const match = html.match(/<script>\\s*([\\s\\S]*)\\s*<\\/script>\\s*<\\/body>/);
    if(!match){{ throw new Error('script block not found'); }}
    vm.runInContext(match[1], context, {{ filename: 'index.html' }});

    vm.runInContext(`
      state.qType = "vocab-choice";
      state.mode = "normal";
      state.totalPerSet = {total_per_set};
      state.unitFilter = '';
      state.user = "tester";
    `, context);

    (async ()=>{{
      await vm.runInContext('ensureQuestions()', context);
      const buildOrderFromBank = vm.runInContext('buildOrderFromBank', context);
      const order = await buildOrderFromBank();
      const deckSnapshot = vm.runInContext('deck({{ includeExtras: true }})', context);
      const orderWithIds = order.map(entry => {{
        const question = deckSnapshot[entry.idx];
        return {{ id: question ? question.id : undefined, bucket: entry.bucket, streak: entry.streak }};
      }});
      process.stdout.write(JSON.stringify({{ orderWithIds, orderLength: order.length }}));
    }})();
    """
    output = run_node(node_code)
    return json.loads(output)


def test_promotable_items_are_prioritized():
    deck = [
        {
            "id": "1",
            "type": "vocab-choice",
            "level": "Lv1",
            "unit": "U1",
            "en": "en1",
            "jp": "jp1",
            "answers": ["en1"],
        },
        {
            "id": "2",
            "type": "vocab-choice",
            "level": "Lv1",
            "unit": "U1",
            "en": "en2",
            "jp": "jp2",
            "answers": ["en2"],
        },
        {
            "id": "3",
            "type": "vocab-choice",
            "level": "Lv1",
            "unit": "U1",
            "en": "en3",
            "jp": "jp3",
            "answers": ["en3"],
        },
        {
            "id": "4",
            "type": "vocab-choice",
            "level": "Lv1",
            "unit": "U1",
            "en": "en4",
            "jp": "jp4",
            "answers": ["en4"],
        },
        {
            "id": "5",
            "type": "vocab-choice",
            "level": "Lv1",
            "unit": "U1",
            "en": "en5",
            "jp": "jp5",
            "answers": ["en5"],
        },
    ]
    stats = {
        "1": {"stage": "D", "streak": 2, "nextDueAt": "2000-01-01T00:00:00.000Z"},
        "2": {"stage": "B", "streak": 1, "nextDueAt": "2000-01-01T00:00:00.000Z"},
        "3": {"stage": "C", "streak": 4, "nextDueAt": "2099-01-01T00:00:00.000Z"},
        "4": {"stage": "F", "streak": 0, "nextDueAt": None},
        "5": {"stage": "E", "streak": 3, "nextDueAt": "2000-01-01T00:00:00.000Z"},
    }

    result = execute_build_order(deck, stats, total_per_set=3)

    ids_with_buckets = [(item["id"], item["bucket"]) for item in result["orderWithIds"]]
    assert ids_with_buckets == [
        ("2", "Stage B"),
        ("1", "Stage D"),
        ("5", "Stage E"),
    ]


def test_higher_levels_fill_shortage():
    deck = [
        {
            "id": "base1",
            "type": "vocab-choice",
            "level": "Lv1",
            "unit": "U1",
            "en": "en-base1",
            "jp": "jp-base1",
            "answers": ["en-base1"],
        },
        {
            "id": "base2",
            "type": "vocab-choice",
            "level": "Lv1",
            "unit": "U1",
            "en": "en-base2",
            "jp": "jp-base2",
            "answers": ["en-base2"],
        },
        {
            "id": "high1",
            "type": "vocab-choice",
            "level": "Lv2",
            "unit": "U1",
            "en": "en-high1",
            "jp": "jp-high1",
            "answers": ["en-high1"],
        },
        {
            "id": "high2",
            "type": "vocab-choice",
            "level": "Lv3",
            "unit": "U1",
            "en": "en-high2",
            "jp": "jp-high2",
            "answers": ["en-high2"],
        },
    ]
    stats = {
        "base1": {"stage": "F", "streak": 0, "nextDueAt": None},
        "base2": {"stage": "F", "streak": 0, "nextDueAt": None},
        "high1": {"stage": "C", "streak": 1, "nextDueAt": None},
        "high2": {"stage": "D", "streak": 1, "nextDueAt": None},
    }

    result = execute_build_order(deck, stats, total_per_set=2)

    ids_with_buckets = [(item["id"], item["bucket"]) for item in result["orderWithIds"]]
    assert ids_with_buckets == [
        ("base1", None),
        ("base2", None),
    ]


def test_shortage_then_fill_with_remaining_questions():
    deck = [
        {
            "id": "base1",
            "type": "vocab-choice",
            "level": "Lv1",
            "unit": "U1",
            "en": "en-base1",
            "jp": "jp-base1",
            "answers": ["en-base1"],
        },
        {
            "id": "base2",
            "type": "vocab-choice",
            "level": "Lv1",
            "unit": "U1",
            "en": "en-base2",
            "jp": "jp-base2",
            "answers": ["en-base2"],
        },
        {
            "id": "due1",
            "type": "vocab-choice",
            "level": "Lv1",
            "unit": "U1",
            "en": "en-due1",
            "jp": "jp-due1",
            "answers": ["en-due1"],
        },
    ]
    stats = {
        "base1": {"stage": "F", "streak": 0, "nextDueAt": None},
        "base2": {"stage": "F", "streak": 0, "nextDueAt": None},
        "due1": {"stage": "B", "streak": 2, "nextDueAt": "2000-01-01T00:00:00.000Z"},
    }

    result = execute_build_order(deck, stats, total_per_set=2)

    ids_with_buckets = [(item["id"], item["bucket"]) for item in result["orderWithIds"]]
    assert ids_with_buckets == [
        ("due1", "Stage B"),
        ("base1", None),
    ]
    streaks = [item["streak"] for item in result["orderWithIds"]]
    assert streaks == [2, 0]
