(function(global){
  function toNonNegativeInt(value){
    const num = Number(value);
    if(!Number.isFinite(num) || num <= 0){
      return 0;
    }
    return Math.floor(num);
  }

  function toValidDate(value){
    if(value instanceof Date){
      return Number.isNaN(value.getTime()) ? null : value;
    }
    if(typeof value === 'number'){
      if(!Number.isFinite(value)){
        return null;
      }
      const dateFromNumber = new Date(value);
      return Number.isNaN(dateFromNumber.getTime()) ? null : dateFromNumber;
    }
    if(typeof value === 'string'){
      const trimmed = value.trim();
      if(!trimmed){
        return null;
      }
      const dateFromString = new Date(trimmed);
      return Number.isNaN(dateFromString.getTime()) ? null : dateFromString;
    }
    return null;
  }

  function normalizeStageKey(value){
    if(typeof value !== 'string'){
      return '';
    }
    const upper = value.trim().toUpperCase();
    return /^[A-Z]$/.test(upper) ? upper : '';
  }

  function determineStagePriorityQuota(totalNeeded, stageFCount){
    const needed = toNonNegativeInt(totalNeeded);
    if(needed === 0){
      return 0;
    }
    const stageFUsable = Math.min(toNonNegativeInt(stageFCount), needed);
    return Math.max(0, needed - stageFUsable);
  }

  function shouldPrioritizeStagePromotion(stage, nextDue, nowValue){
    const stageKey = normalizeStageKey(stage);
    if(!stageKey || stageKey === 'A' || stageKey === 'F'){
      return false;
    }
    const nowMs = Number.isFinite(nowValue) ? Number(nowValue) : Date.now();
    const dueDate = toValidDate(nextDue);
    if(!dueDate){
      return false;
    }
    return dueDate.getTime() <= nowMs;
  }

  const api = {
    determineStagePriorityQuota,
    shouldPrioritizeStagePromotion,
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
