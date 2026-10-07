// Server baseline plus pending toggle intents. A response can never erase later clicks.
export function createDailyWorkoutQueue({ write, publish, failed, uuid = () => crypto.randomUUID() }) {
  const plans = new Map();
  const project = entry => {
    const checks = { ...entry.base.exercises_status };
    for (const op of entry.ops) {
      if (checks[op.index]) delete checks[op.index]; else checks[op.index] = true;
    }
    return { ...entry.base, exercises_status: checks };
  };
  const emit = (id, entry) => publish(id, project(entry));
  async function drain(id, entry) {
    if (entry.running || entry.paused) return;
    entry.running = true;
    try {
      while (entry.ops.length) {
        const op = entry.ops[0];
        try {
          entry.base = await write(id, op.index, op.key);
          entry.ops.shift();
          emit(id, entry);
        } catch (error) {
          const status = error?.response?.status;
          // Timeout/5xx may have committed. Keep the intent and its receipt key for explicit retry.
          if (!status || status >= 500 || status === 408) {
            entry.paused = true;
            failed(error, () => { entry.paused = false; void drain(id, entry); });
            break;
          }
          entry.ops.shift(); // Definitive rejection: rollback only this operation.
          emit(id, entry);
          failed(error);
        }
      }
    } finally { entry.running = false; }
  }
  return {
    enqueue(id, index, initial) {
      let entry = plans.get(id);
      if (!entry || (!entry.running && !entry.ops.length)) {
        entry = { base: initial || { exercises_status: {}, completed: false }, ops: [], running: false, paused: false };
        plans.set(id, entry);
      }
      entry.ops.push({ index, key: uuid() });
      emit(id, entry);
      void drain(id, entry);
    },
    busy: id => !!plans.get(id)?.ops.length,
    reconcile(id, state) {
      const entry = plans.get(id);
      // Ignore reads begun before an outstanding write. Only write responses advance that baseline.
      if (entry?.ops.length) return project(entry);
      return state;
    },
  };
}
