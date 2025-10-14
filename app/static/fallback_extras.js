(function(global){
  function toNonNegativeInt(value){
    const num = Number(value);
    if(!Number.isFinite(num) || num <= 0){
      return 0;
    }
    return Math.floor(num);
  }

  function appendFallbackExtras(extras, prioritized, others, desiredTotal, baseCount){
    if(!Array.isArray(extras)){
      return extras;
    }
    const needed = toNonNegativeInt(desiredTotal);
    if(needed === 0){
      return extras;
    }
    const base = Math.min(toNonNegativeInt(baseCount), needed);
    const limit = Math.max(0, needed - base);
    if(limit === 0){
      return extras;
    }

    const pushLimited = (source)=>{
      if(!Array.isArray(source) || source.length === 0){
        return;
      }
      const remaining = limit - extras.length;
      if(remaining <= 0){
        return;
      }
      extras.push(...source.slice(0, remaining));
    };

    pushLimited(prioritized);
    pushLimited(others);
    return extras;
  }

  const api = {
    appendFallbackExtras,
  };

  if(typeof global === 'object' && global){
    const existing = global.__quizFallbackExtras || {};
    global.__quizFallbackExtras = Object.assign({}, existing, api);
  }

  if(typeof module !== 'undefined' && module && module.exports){
    module.exports = api;
  }
})(typeof window !== 'undefined' ? window : globalThis);
