import { initialState, transition } from './model.mjs';

const KEY = 'space-catalog-review-design-v1';
export function createSession(storage) {
  let scenario = 'standard';
  let events = [];
  let state = initialState();
  let persistent = true;
  let restored = false;
  try {
    const raw = storage?.getItem(KEY);
    if (raw) {
      if (raw.length > 120_000) throw new Error('Oversized preview session');
      const value = JSON.parse(raw);
      if (value.version !== 1 || !Array.isArray(value.events) || value.events.length > 800) throw new Error('Invalid preview session');
      scenario = value.scenario;
      state = initialState(scenario);
      // Replay the same guarded state machine, never trust a stored state snapshot.
      for (const event of value.events) state = transition(state, event);
      events = value.events;
      restored = true;
    }
  } catch {
    scenario = 'standard'; state = initialState(); events = [];
    try { storage?.removeItem(KEY); } catch { persistent = false; }
  }
  function persist() {
    try {
      if (!storage || events.length > 800) throw new Error('Preview storage unavailable');
      storage.setItem(KEY, JSON.stringify({ version: 1, scenario, events }));
      persistent = true;
    } catch { persistent = false; }
  }
  persist();
  return {
    get state() { return state; },
    get persistent() { return persistent; },
    restored,
    dispatch(event) {
      const next = transition(state, event);
      if (next === state) return state;
      state = next; events.push(event); persist(); return state;
    },
    reset(nextScenario = 'standard') {
      state = initialState(nextScenario); scenario = nextScenario; events = []; persist();
      return state;
    },
  };
}
