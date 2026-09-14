// One in-flight request per resource; retry an uncertain result with the same key.
export function createActivityRequests(makeKey = () => crypto.randomUUID()) {
  const requests = new Map();
  return {
    begin(resource, intent) {
      const previous = requests.get(resource);
      if (previous?.pending) return null;
      const entry = previous?.intent === intent
        ? previous
        : { key: makeKey(), intent };
      entry.pending = true;
      requests.set(resource, entry);
      return entry.key;
    },
    finish(resource, succeeded) {
      const entry = requests.get(resource);
      if (!entry) return;
      if (succeeded) requests.delete(resource);
      else entry.pending = false;
    },
  };
}
