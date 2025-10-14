import json
import subprocess
from pathlib import Path


def run_node(code: str) -> str:
    result = subprocess.run(
        ["node", "-e", code],
        check=True,
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent.parent,
    )
    return result.stdout.strip()


def test_stage_f_shortage_promotes_higher_level_items():
    node_code = """
    const fs = require('fs');
    const path = require('path');
    const vm = require('vm');

    class Element {
      constructor(id){
        this.id = id;
        this.children = [];
        this.style = {};
        this.attributes = {};
        this._textContent = '';
        this.value = '';
        this.disabled = false;
        this.innerHTML = '';
      }
      appendChild(child){ this.children.push(child); return child; }
      removeChild(child){ this.children = this.children.filter(c => c !== child); }
      set textContent(val){ this._textContent = val; }
      get textContent(){ return this._textContent; }
      set onclick(fn){ this._onclick = fn; }
      get onclick(){ return this._onclick; }
      addEventListener(){ }
      removeEventListener(){ }
      setAttribute(name, value){ this.attributes[name] = value; }
      getAttribute(name){ return this.attributes[name]; }
      focus(){ }
      blur(){ }
      remove(){ }
      get classList(){
        return {
          add(){},
          remove(){},
          contains(){ return false; },
        };
      }
    }

    const elements = new Map();
    const getElement = (id)=>{
      if(!elements.has(id)){
        elements.set(id, new Element(id));
      }
      return elements.get(id);
    };

    const documentStub = {
      getElementById(id){ return getElement(id); },
      querySelector(selector){ return selector.startsWith('#') ? getElement(selector.slice(1)) : new Element(selector); },
      querySelectorAll(){ return []; },
      createElement(tag){ return new Element(tag); },
    };

    const localStore = new Map();
    const localStorageStub = {
      getItem(key){ return localStore.has(key) ? localStore.get(key) : null; },
      setItem(key, value){ localStore.set(key, String(value)); },
      removeItem(key){ localStore.delete(key); },
    };

    const statsMap = new Map([
      ['1', { stage: 'F', streak: 1, nextDueAt: null }],
      ['2', { stage: 'F', streak: 2, nextDueAt: null }],
      ['3', { stage: 'F', streak: 0, nextDueAt: null }],
      ['4', { stage: 'F', streak: 1, nextDueAt: null }],
      ['5', { stage: 'F', streak: 3, nextDueAt: null }],
      ['6', { stage: 'C', streak: 4, nextDueAt: null }],
      ['7', { stage: 'D', streak: 1, nextDueAt: null }],
    ]);

    const fetchStub = async (url, options={})=>{
      if(typeof url === 'string' && url.includes('/data/english/questions.json')){
        return { ok: true, json: async ()=>({ vocabInput: [], vocabChoice: [], reorder: [], rewrite: [] }) };
      }
      if(url === '/api/stats/bulk'){
        const body = JSON.parse(options.body || '{}');
        const ids = Array.isArray(body.ids) ? body.ids : [];
        const results = ids.map(id => {
          const key = String(id);
          const stat = statsMap.get(key) || { stage: 'F', streak: 0, nextDueAt: null };
          return { id: key, stage: stat.stage, streak: stat.streak, nextDueAt: stat.nextDueAt };
        });
        return { ok: true, json: async ()=>({ results }) };
      }
      return { ok: true, json: async ()=>({}) };
    };

    const context = {
      console: { log(){}, warn(){}, error(){} },
      setTimeout,
      clearTimeout,
      setInterval,
      clearInterval,
      Math: Object.assign(Object.create(Math), { random: () => 0.11111 }),
      document: documentStub,
      localStorage: localStorageStub,
      fetch: fetchStub,
      alert: ()=>{},
      performance: { now: () => 0 },
    };
    context.window = {
      document: documentStub,
      addEventListener(){},
      location: { href: '' },
      __stagePriority: require('./app/static/stage_priority.js'),
    };
    context.window.window = context.window;
    context.window.__quizFallbackExtras = require('./app/static/fallback_extras.js');
    context.__quizFallbackExtras = context.window.__quizFallbackExtras;
    context.globalThis = context;
    context.SpeechSynthesisUtterance = function(){};
    context.AbortController = AbortController;
    context.URL = URL;

    vm.createContext(context);
    const htmlPath = path.join(__dirname, 'app/static/index.html');
    const html = fs.readFileSync(htmlPath, 'utf8');
    const match = html.match(/<script>\\s*([\\s\\S]*)\\s*<\\/script>\\s*<\\/body>/);
    if(!match){ throw new Error('script block not found'); }
    vm.runInContext(match[1], context, { filename: 'index.html' });

    const deckData = [
      { id: '1', type: 'vocab', level: 'Lv1', unit: 'U1', en: 'en1', jp: 'jp1', answers: ['en1'] },
      { id: '2', type: 'vocab', level: 'Lv1', unit: 'U1', en: 'en2', jp: 'jp2', answers: ['en2'] },
      { id: '3', type: 'vocab', level: 'Lv1', unit: 'U1', en: 'en3', jp: 'jp3', answers: ['en3'] },
      { id: '4', type: 'vocab', level: 'Lv1', unit: 'U1', en: 'en4', jp: 'jp4', answers: ['en4'] },
      { id: '5', type: 'vocab', level: 'Lv1', unit: 'U1', en: 'en5', jp: 'jp5', answers: ['en5'] },
      { id: '6', type: 'vocab', level: 'Lv2', unit: 'U1', en: 'en6', jp: 'jp6', answers: ['en6'] },
      { id: '7', type: 'vocab', level: 'Lv2', unit: 'U1', en: 'en7', jp: 'jp7', answers: ['en7'] },
    ];
    context.deckData = deckData;
    vm.runInContext('BANK_VOCAB_INPUT = deckData;', context);
    delete context.deckData;

    vm.runInContext('state.qType = "vocab";', context);
    vm.runInContext('state.mode = "normal";', context);
    vm.runInContext('state.levelMax = "Lv1";', context);
    vm.runInContext('state.totalPerSet = 7;', context);
    vm.runInContext('state.unitFilter = "";', context);
    vm.runInContext('state.fallbackExtras = [];', context);
    vm.runInContext('state.fallbackStageOverrides = new Map();', context);
    vm.runInContext('state.user = "tester";', context);

    (async ()=>{
      const buildOrderFromBank = vm.runInContext('buildOrderFromBank', context);
      const order = await buildOrderFromBank();
      const extrasIds = vm.runInContext('state.fallbackExtras.map(q => q.id)', context);
      const overrides = vm.runInContext('Array.from(state.fallbackStageOverrides.entries())', context);
      const deckSnapshot = vm.runInContext('deck({ includeExtras: true })', context);
      const orderWithIds = order.map(entry => {
        const question = deckSnapshot[entry.idx];
        return { id: question ? question.id : undefined, bucket: entry.bucket };
      });
      process.stdout.write(JSON.stringify({ extrasIds, overrides, orderWithIds }));
    })();
    """
    output = run_node(node_code)
    data = json.loads(output)

    assert set(data["extrasIds"]) == {"6", "7"}
    overrides = dict(data["overrides"])
    assert overrides.get("id:6") == "F"
    assert overrides.get("id:7") == "F"
    stage_f_ids = [item for item in data["orderWithIds"] if item.get("id") in {"6", "7"}]
    assert len(stage_f_ids) == 2
    assert all(item["bucket"] == "Stage F" for item in stage_f_ids)
