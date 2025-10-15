import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


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
    level_max: str = "Lv1",
    total_per_set: int = 7,
    unit_filter: str = "",
    math_random: float = 0.11111,
    force_stage_priority_quota: Optional[int] = None,
    stage_f_history: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    deck_json = json.dumps(deck_data)
    stats_json = json.dumps(stats_map)
    level_max_json = json.dumps(level_max)
    unit_filter_json = json.dumps(unit_filter)
    stage_f_history_json = json.dumps(list(stage_f_history or []))
    override_snippet = ""
    if force_stage_priority_quota is not None:
        override_snippet = (
            "      if(typeof determineStagePriorityQuota === 'function'){\n"
            f"        determineStagePriorityQuota = () => {force_stage_priority_quota};\n"
            "      }\n"
        )
    node_code = f"""
    const fs = require('fs');
    const path = require('path');
    const vm = require('vm');
    const {{ URL }} = require('url');

    const deckData = {deck_json};
    const statsMapInit = {stats_json};
    const stageFHistoryInit = {stage_f_history_json};
    const wrongQueueStore = new Map();

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
      set onclick(fn){{ this._onclick = fn; }}
      get onclick(){{ return this._onclick; }}
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
        return {{ ok: true, json: async ()=>({{ vocabInput: deckData, vocabChoice: [], reorder: [], rewrite: [] }}) }};
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
      if(typeof url === 'string' && url.startsWith('/api/stats/stage-f')){{
        const list = Array.isArray(stageFHistoryInit) ? stageFHistoryInit : [];
        return {{ ok: true, json: async ()=>({{ keys: list }}) }};
      }}
      if(typeof url === 'string' && url.startsWith('/api/wrong-queue')){{
        const method = (options.method || 'GET').toUpperCase();
        if(method === 'POST'){{
          const body = JSON.parse(options.body || '{{}}');
          const user = (body.user || '').trim() || 'guest';
          const qType = (body.qType || '').trim() || '';
          const key = `${{user}}::${{qType}}`;
          const items = Array.isArray(body.items) ? body.items : [];
          wrongQueueStore.set(key, items);
          return {{ ok: true, json: async ()=>({{ ok: true }}) }};
        }}
        const parsed = new URL(url, 'https://example.invalid');
        const user = (parsed.searchParams.get('user') || '').trim() || 'guest';
        const qType = (parsed.searchParams.get('qType') || '').trim() || '';
        const key = `${{user}}::${{qType}}`;
        const items = wrongQueueStore.get(key) || [];
        return {{ ok: true, json: async ()=>({{ items }}) }};
      }}
      if(typeof url === 'string' && url.startsWith('/api/history')){{
        const method = (options.method || 'GET').toUpperCase();
        if(method === 'POST'){{
          return {{ ok: true, json: async ()=>({{ ok: true }}) }};
        }}
        return {{ ok: true, json: async ()=>({{ history: [] }}) }};
      }}
      return {{ ok: true, json: async ()=>({{}}) }};
    }};

    const context = {{
      console: {{ log(){{}}, warn(){{}}, error(){{}} }},
      setTimeout,
      clearTimeout,
      setInterval,
      clearInterval,
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
    context.window.__quizFallbackExtras = require('./app/static/fallback_extras.js');
    context.__quizFallbackExtras = context.window.__quizFallbackExtras;
    context.globalThis = context;
    context.SpeechSynthesisUtterance = function(){{}};
    context.AbortController = AbortController;
    context.URL = URL;

    vm.createContext(context);
    const htmlPath = path.join(__dirname, 'app/static/index.html');
    const html = fs.readFileSync(htmlPath, 'utf8');
    const match = html.match(/<script>\\s*([\\s\\S]*)\\s*<\\/script>\\s*<\\/body>/);
    if(!match){{ throw new Error('script block not found'); }}
    vm.runInContext(match[1], context, {{ filename: 'index.html' }});

    vm.runInContext(`
      state.qType = "vocab";
      state.mode = "normal";
      state.levelMax = {level_max_json};
      state.totalPerSet = {total_per_set};
      state.unitFilter = {unit_filter_json};
      state.fallbackExtras = [];
      state.fallbackStageOverrides = new Map();
      state.user = "tester";
{override_snippet}
    `, context);

    (async ()=>{{
      await vm.runInContext('ensureQuestions()', context);
      const buildOrderFromBank = vm.runInContext('buildOrderFromBank', context);
      const order = await buildOrderFromBank();
      const extrasIds = vm.runInContext('state.fallbackExtras.map(q => q.id)', context);
      const overrides = vm.runInContext('Array.from(state.fallbackStageOverrides.entries())', context);
      const deckSnapshot = vm.runInContext('deck({{ includeExtras: true }})', context);
      const stageFHistoryParsed = vm.runInContext('Array.from(getStageFHistory())', context);
      const orderWithIds = order.map(entry => {{
        const question = deckSnapshot[entry.idx];
        return {{ id: question ? question.id : undefined, bucket: entry.bucket }};
      }});
      process.stdout.write(JSON.stringify({{ extrasIds, overrides, orderWithIds, orderLength: order.length, stageFHistory: stageFHistoryParsed }}));
    }})();
    """
    output = run_node(node_code)
    return json.loads(output)


def test_stage_f_shortage_promotes_higher_level_items():
    deck = [
        {
            "id": "1",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en1",
            "jp": "jp1",
            "answers": ["en1"],
        },
        {
            "id": "2",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en2",
            "jp": "jp2",
            "answers": ["en2"],
        },
        {
            "id": "3",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en3",
            "jp": "jp3",
            "answers": ["en3"],
        },
        {
            "id": "4",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en4",
            "jp": "jp4",
            "answers": ["en4"],
        },
        {
            "id": "5",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en5",
            "jp": "jp5",
            "answers": ["en5"],
        },
        {
            "id": "6",
            "type": "vocab",
            "level": "Lv2",
            "unit": "U1",
            "en": "en6",
            "jp": "jp6",
            "answers": ["en6"],
        },
        {
            "id": "7",
            "type": "vocab",
            "level": "Lv2",
            "unit": "U1",
            "en": "en7",
            "jp": "jp7",
            "answers": ["en7"],
        },
    ]
    stats = {
        "1": {"stage": "F", "streak": 1, "nextDueAt": None},
        "2": {"stage": "F", "streak": 2, "nextDueAt": None},
        "3": {"stage": "F", "streak": 0, "nextDueAt": None},
        "4": {"stage": "F", "streak": 1, "nextDueAt": None},
        "5": {"stage": "F", "streak": 3, "nextDueAt": None},
        "6": {"stage": "C", "streak": 4, "nextDueAt": None},
        "7": {"stage": "D", "streak": 1, "nextDueAt": None},
    }

    result = execute_build_order(deck, stats)

    assert set(result["extrasIds"]) == {"6", "7"}
    overrides = dict(result["overrides"])
    assert overrides.get("id:6") == "F"
    assert overrides.get("id:7") == "F"
    stage_f_ids = [
        item for item in result["orderWithIds"] if item.get("id") in {"6", "7"}
    ]
    assert len(stage_f_ids) == 2
    assert all(item["bucket"] == "Stage F" for item in stage_f_ids)


def test_stage_f_topups_prioritize_previously_seen_questions():
    deck = [
        {
            "id": "f1",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en-f1",
            "jp": "jp-f1",
            "answers": ["en-f1"],
        },
        {
            "id": "f2",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en-f2",
            "jp": "jp-f2",
            "answers": ["en-f2"],
        },
        {
            "id": "f3",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en-f3",
            "jp": "jp-f3",
            "answers": ["en-f3"],
        },
        {
            "id": "f4",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en-f4",
            "jp": "jp-f4",
            "answers": ["en-f4"],
        },
        {
            "id": "f5",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en-f5",
            "jp": "jp-f5",
            "answers": ["en-f5"],
        },
        {
            "id": "v052",
            "type": "vocab",
            "level": "Lv2",
            "unit": "U1",
            "en": "en-v052",
            "jp": "jp-v052",
            "answers": ["en-v052"],
        },
        {
            "id": "x1",
            "type": "vocab",
            "level": "Lv2",
            "unit": "U1",
            "en": "en-x1",
            "jp": "jp-x1",
            "answers": ["en-x1"],
        },
        {
            "id": "v053",
            "type": "vocab",
            "level": "Lv2",
            "unit": "U1",
            "en": "en-v053",
            "jp": "jp-v053",
            "answers": ["en-v053"],
        },
    ]
    stats = {
        "f1": {"stage": "F", "streak": 1, "nextDueAt": None},
        "f2": {"stage": "F", "streak": 1, "nextDueAt": None},
        "f3": {"stage": "F", "streak": 1, "nextDueAt": None},
        "f4": {"stage": "F", "streak": 1, "nextDueAt": None},
        "f5": {"stage": "F", "streak": 1, "nextDueAt": None},
        "v052": {"stage": "C", "streak": 0, "nextDueAt": None},
        "x1": {"stage": "C", "streak": 0, "nextDueAt": None},
        "v053": {"stage": "C", "streak": 0, "nextDueAt": None},
    }

    result = execute_build_order(
        deck,
        stats,
        total_per_set=7,
        force_stage_priority_quota=0,
        stage_f_history=["id:v052", "id:v053"],
    )

    stage_f_ids = [
        item.get("id")
        for item in result["orderWithIds"]
        if item.get("bucket") == "Stage F" and item.get("id") in {"v052", "v053", "x1"}
    ]
    assert len(stage_f_ids) == 2
    assert set(stage_f_ids) == {"v052", "v053"}
    assert {"id:v052", "id:v053"}.issubset(set(result["stageFHistory"]))


def test_stage_f_pool_prefers_previously_seen_questions():
    deck = [
        {
            "id": "s1",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en-s1",
            "jp": "jp-s1",
            "answers": ["en-s1"],
        },
        {
            "id": "s2",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en-s2",
            "jp": "jp-s2",
            "answers": ["en-s2"],
        },
        {
            "id": "s3",
            "type": "vocab",
            "level": "Lv2",
            "unit": "U1",
            "en": "en-s3",
            "jp": "jp-s3",
            "answers": ["en-s3"],
        },
    ]
    stats = {
        item["id"]: {"stage": "F", "streak": 0, "nextDueAt": None} for item in deck
    }

    result = execute_build_order(
        deck,
        stats,
        total_per_set=1,
        stage_f_history=["id:s3"],
        force_stage_priority_quota=0,
    )

    stage_f_ids = [
        item.get("id")
        for item in result["orderWithIds"]
        if item.get("bucket") == "Stage F"
    ]
    assert stage_f_ids == ["s3"]
    assert "id:s3" in result["stageFHistory"]


def test_stage_f_history_records_promoted_questions():
    deck = [
        {
            "id": "base1",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en-base1",
            "jp": "jp-base1",
            "answers": ["en-base1"],
        },
        {
            "id": "base2",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en-base2",
            "jp": "jp-base2",
            "answers": ["en-base2"],
        },
        {
            "id": "extra1",
            "type": "vocab",
            "level": "Lv2",
            "unit": "U1",
            "en": "en-extra1",
            "jp": "jp-extra1",
            "answers": ["en-extra1"],
        },
        {
            "id": "extra2",
            "type": "vocab",
            "level": "Lv2",
            "unit": "U1",
            "en": "en-extra2",
            "jp": "jp-extra2",
            "answers": ["en-extra2"],
        },
    ]
    stats = {
        item["id"]: {"stage": "F", "streak": 0, "nextDueAt": None} for item in deck
    }

    result = execute_build_order(
        deck,
        stats,
        total_per_set=3,
        stage_f_history=None,
    )

    stage_f_ids = {
        item.get("id")
        for item in result["orderWithIds"]
        if item.get("bucket") == "Stage F"
    }
    assert stage_f_ids & {"extra1", "extra2"}
    assert any(key in result["stageFHistory"] for key in {"id:extra1", "id:extra2"})


def test_waiting_fallback_extras_are_replaced_by_additional_levels():
    deck = [
        {
            "id": "1",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en1",
            "jp": "jp1",
            "answers": ["en1"],
        },
        {
            "id": "2",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en2",
            "jp": "jp2",
            "answers": ["en2"],
        },
        {
            "id": "3",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en3",
            "jp": "jp3",
            "answers": ["en3"],
        },
        {
            "id": "4",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en4",
            "jp": "jp4",
            "answers": ["en4"],
        },
        {
            "id": "5",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en5",
            "jp": "jp5",
            "answers": ["en5"],
        },
        {
            "id": "6",
            "type": "vocab",
            "level": "Lv2",
            "unit": "U1",
            "en": "en6",
            "jp": "jp6",
            "answers": ["en6"],
        },
        {
            "id": "7",
            "type": "vocab",
            "level": "Lv2",
            "unit": "U1",
            "en": "en7",
            "jp": "jp7",
            "answers": ["en7"],
        },
        {
            "id": "8",
            "type": "vocab",
            "level": "Lv3",
            "unit": "U1",
            "en": "en8",
            "jp": "jp8",
            "answers": ["en8"],
        },
        {
            "id": "9",
            "type": "vocab",
            "level": "Lv3",
            "unit": "U1",
            "en": "en9",
            "jp": "jp9",
            "answers": ["en9"],
        },
    ]
    stats = {
        "1": {"stage": "F", "streak": 1, "nextDueAt": None},
        "2": {"stage": "F", "streak": 2, "nextDueAt": None},
        "3": {"stage": "F", "streak": 0, "nextDueAt": None},
        "4": {"stage": "F", "streak": 1, "nextDueAt": None},
        "5": {"stage": "F", "streak": 3, "nextDueAt": None},
        "6": {"stage": "C", "streak": 4, "nextDueAt": "2099-01-01T00:00:00.000Z"},
        "7": {"stage": "D", "streak": 2, "nextDueAt": "2099-01-02T00:00:00.000Z"},
        "8": {"stage": "D", "streak": 1, "nextDueAt": None},
        "9": {"stage": "E", "streak": 2, "nextDueAt": None},
    }

    result = execute_build_order(deck, stats, math_random=0.22222)

    assert result["orderLength"] == 7
    assert set(result["extrasIds"]) == {"8", "9"}
    used_ids = [item.get("id") for item in result["orderWithIds"]]
    assert used_ids.count("8") == 1
    assert used_ids.count("9") == 1


def test_due_stage_items_appear_even_when_stage_f_is_sufficient():
    deck = [
        {
            "id": "1",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en1",
            "jp": "jp1",
            "answers": ["en1"],
        },
        {
            "id": "2",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en2",
            "jp": "jp2",
            "answers": ["en2"],
        },
        {
            "id": "3",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en3",
            "jp": "jp3",
            "answers": ["en3"],
        },
        {
            "id": "4",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en4",
            "jp": "jp4",
            "answers": ["en4"],
        },
        {
            "id": "5",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en5",
            "jp": "jp5",
            "answers": ["en5"],
        },
        {
            "id": "6",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en6",
            "jp": "jp6",
            "answers": ["en6"],
        },
        {
            "id": "7",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en7",
            "jp": "jp7",
            "answers": ["en7"],
        },
        {
            "id": "8",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en8",
            "jp": "jp8",
            "answers": ["en8"],
        },
    ]
    stats = {
        "1": {"stage": "F", "streak": 1, "nextDueAt": None},
        "2": {"stage": "F", "streak": 2, "nextDueAt": None},
        "3": {"stage": "F", "streak": 0, "nextDueAt": None},
        "4": {"stage": "F", "streak": 1, "nextDueAt": None},
        "5": {"stage": "F", "streak": 3, "nextDueAt": None},
        "6": {"stage": "F", "streak": 2, "nextDueAt": None},
        "7": {"stage": "F", "streak": 1, "nextDueAt": None},
        "8": {"stage": "D", "streak": 4, "nextDueAt": "2000-01-01T00:00:00.000Z"},
    }

    result = execute_build_order(deck, stats, math_random=0.44444)

    assert result["orderLength"] == 7
    ids_with_buckets = {
        item.get("id"): item.get("bucket") for item in result["orderWithIds"]
    }
    assert ids_with_buckets.get("8") == "Stage D"
    stage_f_count = sum(
        1 for bucket in ids_with_buckets.values() if bucket == "Stage F"
    )
    assert stage_f_count == 6


def test_waiting_fallback_extras_trigger_additional_retry_until_new_level_used():
    deck = [
        {
            "id": "1",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en1",
            "jp": "jp1",
            "answers": ["en1"],
        },
        {
            "id": "2",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en2",
            "jp": "jp2",
            "answers": ["en2"],
        },
        {
            "id": "3",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en3",
            "jp": "jp3",
            "answers": ["en3"],
        },
        {
            "id": "4",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en4",
            "jp": "jp4",
            "answers": ["en4"],
        },
        {
            "id": "5",
            "type": "vocab",
            "level": "Lv1",
            "unit": "U1",
            "en": "en5",
            "jp": "jp5",
            "answers": ["en5"],
        },
        {
            "id": "6",
            "type": "vocab",
            "level": "Lv2",
            "unit": "U1",
            "en": "en6",
            "jp": "jp6",
            "answers": ["en6"],
        },
        {
            "id": "7",
            "type": "vocab",
            "level": "Lv2",
            "unit": "U1",
            "en": "en7",
            "jp": "jp7",
            "answers": ["en7"],
        },
        {
            "id": "8",
            "type": "vocab",
            "level": "Lv2",
            "unit": "U1",
            "en": "en8",
            "jp": "jp8",
            "answers": ["en8"],
        },
        {
            "id": "9",
            "type": "vocab",
            "level": "Lv2",
            "unit": "U1",
            "en": "en9",
            "jp": "jp9",
            "answers": ["en9"],
        },
        {
            "id": "10",
            "type": "vocab",
            "level": "Lv2",
            "unit": "U1",
            "en": "en10",
            "jp": "jp10",
            "answers": ["en10"],
        },
        {
            "id": "11",
            "type": "vocab",
            "level": "Lv2",
            "unit": "U1",
            "en": "en11",
            "jp": "jp11",
            "answers": ["en11"],
        },
        {
            "id": "12",
            "type": "vocab",
            "level": "Lv3",
            "unit": "U1",
            "en": "en12",
            "jp": "jp12",
            "answers": ["en12"],
        },
        {
            "id": "13",
            "type": "vocab",
            "level": "Lv3",
            "unit": "U1",
            "en": "en13",
            "jp": "jp13",
            "answers": ["en13"],
        },
        {
            "id": "14",
            "type": "vocab",
            "level": "Lv3",
            "unit": "U1",
            "en": "en14",
            "jp": "jp14",
            "answers": ["en14"],
        },
    ]
    stats = {
        "1": {"stage": "F", "streak": 1, "nextDueAt": None},
        "2": {"stage": "F", "streak": 2, "nextDueAt": None},
        "3": {"stage": "F", "streak": 0, "nextDueAt": None},
        "4": {"stage": "F", "streak": 1, "nextDueAt": None},
        "5": {"stage": "F", "streak": 3, "nextDueAt": None},
        "6": {"stage": "C", "streak": 4, "nextDueAt": "2099-01-01T00:00:00.000Z"},
        "7": {"stage": "D", "streak": 2, "nextDueAt": "2099-01-01T00:00:00.000Z"},
        "8": {"stage": "D", "streak": 1, "nextDueAt": "2099-01-03T00:00:00.000Z"},
        "9": {"stage": "D", "streak": 2, "nextDueAt": "2099-01-04T00:00:00.000Z"},
        "10": {"stage": "C", "streak": 1, "nextDueAt": "2099-01-05T00:00:00.000Z"},
        "11": {"stage": "C", "streak": 2, "nextDueAt": "2099-01-06T00:00:00.000Z"},
        "12": {"stage": "D", "streak": 1, "nextDueAt": None},
        "13": {"stage": "D", "streak": 1, "nextDueAt": None},
        "14": {"stage": "E", "streak": 2, "nextDueAt": None},
    }

    result = execute_build_order(deck, stats, math_random=0.33333)

    assert result["orderLength"] == 7
    assert set(result["extrasIds"]) == {"12", "13", "14"}
    used_ids = [item.get("id") for item in result["orderWithIds"]]
    assert {"12", "13"}.issubset(set(used_ids))
    assert used_ids.count("12") == 1
    assert used_ids.count("13") == 1
