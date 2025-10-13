(function(global){
  function toNonNegativeInt(value){
    const num = Number(value);
    if(!Number.isFinite(num) || num <= 0){
      return 0;
    }
    return Math.floor(num);
  }

  function determineStagePriorityQuota(totalNeeded, stageFCount){
    const needed = toNonNegativeInt(totalNeeded);
    if(needed === 0){
      return 0;
    }
    const stageFUsable = Math.min(toNonNegativeInt(stageFCount), needed);
    return Math.max(0, needed - stageFUsable);
  }

  const api = {
    determineStagePriorityQuota,
  };

  if(typeof global === 'object' && global){
    global.determineStagePriorityQuota = determineStagePriorityQuota;
    const existing = global.__stagePriority || {};
    global.__stagePriority = Object.assign({}, existing, api);
  }

  if(typeof module !== 'undefined' && module && module.exports){
    module.exports = api;
  }
})(typeof window !== 'undefined' ? window : globalThis);
