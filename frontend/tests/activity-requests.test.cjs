const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs.readFileSync(path.join(__dirname, "../src/lib/activity-requests.js"), "utf8");
const loaded = import("data:text/javascript;base64," + Buffer.from(source).toString("base64"));

test("double click is blocked before a rerender, including a different intent", async () => {
  const { createActivityRequests } = await loaded;
  const requests = createActivityRequests(() => "key-1");
  assert.equal(requests.begin("task-1", "done"), "key-1");
  assert.equal(requests.begin("task-1", "done"), null);
  assert.equal(requests.begin("task-1", "todo"), null);
});

test("an uncertain result reuses its key when retried", async () => {
  const { createActivityRequests } = await loaded;
  let next = 0;
  const requests = createActivityRequests(() => "key-" + ++next);
  const key = requests.begin("habit-1", "complete");
  requests.finish("habit-1", false);
  assert.equal(requests.begin("habit-1", "complete"), key);
  assert.equal(next, 1);
});

test("a successful action releases the resource and the next action has a new key", async () => {
  const { createActivityRequests } = await loaded;
  let next = 0;
  const requests = createActivityRequests(() => "key-" + ++next);
  requests.begin("task-1", "done");
  requests.finish("task-1", true);
  assert.equal(requests.begin("task-1", "todo"), "key-2");
});

test("independent resources proceed and changed intent does not reuse a receipt", async () => {
  const { createActivityRequests } = await loaded;
  let next = 0;
  const requests = createActivityRequests(() => "key-" + ++next);
  assert.equal(requests.begin("task-1", "done"), "key-1");
  assert.equal(requests.begin("task-2", "done"), "key-2");
  requests.finish("task-1", false);
  assert.equal(requests.begin("task-1", "todo"), "key-3");
});
