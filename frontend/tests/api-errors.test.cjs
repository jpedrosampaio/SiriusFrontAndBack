const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const helperSource = fs.readFileSync(path.join(__dirname, "../src/lib/api-errors.js"), "utf8");
const helper = import("data:text/javascript;base64," + Buffer.from(helperSource).toString("base64"));
const apiSource = fs.readFileSync(path.join(__dirname, "../src/lib/api.js"), "utf8");

async function loadClient({ offline = false, pathname = "/studies" } = {}) {
  const { getApiErrorMessage } = await helper;
  const handlers = {};
  const events = [];
  const storage = new Map([["sirius_session_token", "test-session"]]);
  const location = { pathname, href: pathname };
  const context = vm.createContext({
    axios: { interceptors: {
      request: { use(resolve, reject) { handlers.request = resolve; } },
      response: { use(resolve, reject) { handlers.reject = reject; } },
    }},
    OFFLINE_MODE: offline, OFFLINE_USER: {}, OFFLINE_DEMO_DATA: {},
    getApiErrorMessage, process: { env: {} }, Event,
    localStorage: {
      getItem: key => storage.get(key),
      setItem: (key, value) => storage.set(key, value),
      removeItem: key => storage.delete(key),
    },
    window: { addEventListener() {}, location, dispatchEvent: event => events.push(event) },
    CustomEvent: class { constructor(type, options) { this.type = type; this.detail = options?.detail; } },
  });
  // Run the actual interceptor module with browser/axios dependencies supplied above.
  const executable = apiSource
    .replace(/^import .*;$/gm, "")
    .replace(/^export \{.*\};$/gm, "")
    .replace(/^export default .*;$/gm, "")
    .replace(/^export /gm, "");
  vm.runInContext(executable, context, { filename: "api.js" });
  return { ...handlers, events, storage, location };
}

test("plain server messages remain readable", async () => {
  const { getApiErrorMessage } = await helper;
  assert.equal(getApiErrorMessage({ response: { data: { detail: "  Email already registered  " } } }),
               "Email already registered");
});

test("validation arrays produce text with fields and without submitted input", async () => {
  const { getApiErrorMessage } = await helper;
  const error = { response: { status: 422, data: { detail: [
    { loc: ["body", "password"], msg: "String should have at least 8 characters",
      input: "private-password", ctx: { secret: "private-context" } },
    { loc: ["body", "items", 0, "amount"], msg: "Input should be a valid number", input: "private-value" },
  ] } } };
  const before = structuredClone(error);
  assert.equal(getApiErrorMessage(error),
    "password: String should have at least 8 characters; items.0.amount: Input should be a valid number");
  assert.deepEqual(error, before);
});

test("structured message details are supported without stringifying their other fields", async () => {
  const { getApiErrorMessage } = await helper;
  assert.equal(getApiErrorMessage({ response: { data: { detail: {
    message: "Request unavailable", input: "secret",
  } } } }), "Request unavailable");
});

test("missing and malformed response details use the screen's fallback", async () => {
  const { getApiErrorMessage } = await helper;
  for (const detail of [null, undefined, false, 12, {}, [], "", "   ", [{ msg: {} }], [{ input: "secret" }]]) {
    assert.equal(getApiErrorMessage({ response: { data: { detail } } }, "Erro ao salvar"), "Erro ao salvar");
  }
  for (const error of [null, undefined, new Error("network URL with secret"), { response: { data: "<html>error</html>" } }]) {
    assert.equal(getApiErrorMessage(error, "Erro de conexão"), "Erro de conexão");
  }
});

test("validation duplicates are collapsed and malformed locations are ignored", async () => {
  const { getApiErrorMessage } = await helper;
  assert.equal(getApiErrorMessage({ response: { data: { detail: [
    { msg: "Required", loc: "bad-location" }, { msg: "Required" }, null,
  ] } } }), "Required");
});

test("422 rejection preserves the original Axios error instead of throwing includes TypeError", async () => {
  const client = await loadClient();
  const error = { response: { status: 422, data: { detail: [
    { loc: ["body", "email"], msg: "Invalid email", input: "private@example.test" },
  ] } }, config: { method: "post" } };
  await assert.rejects(client.reject(error), actual => actual === error);
  assert.deepEqual(client.events, []);
  assert.equal(client.storage.get("sirius_session_token"), "test-session");
});

test("object, numeric and missing details also preserve the original rejection", async () => {
  const client = await loadClient();
  for (const detail of [{ errors: [] }, 42, null, undefined]) {
    const error = { response: { status: 500, data: { detail } } };
    await assert.rejects(client.reject(error), actual => actual === error);
  }
});

test("network failures retain their identity and do not log the user out", async () => {
  const client = await loadClient();
  const error = new Error("Network Error");
  await assert.rejects(client.reject(error), actual => actual === error);
  assert.equal(client.location.href, "/studies");
  assert.equal(client.storage.get("sirius_session_token"), "test-session");
});

test("an expired session still clears credentials and redirects", async () => {
  const client = await loadClient();
  const error = { response: { status: 401, data: { detail: "Not authenticated" } } };
  await assert.rejects(client.reject(error), actual => actual === error);
  assert.equal(client.storage.has("sirius_session_token"), false);
  assert.equal(client.location.href, "/login");
});

test("login, registration and landing pages do not redirect on 401", async () => {
  for (const pathname of ["/login", "/register", "/"]) {
    const client = await loadClient({ pathname });
    const error = { response: { status: 401 } };
    await assert.rejects(client.reject(error), actual => actual === error);
    assert.equal(client.location.href, pathname);
  }
});

test("Gemini configuration guidance still opens its modal", async () => {
  const client = await loadClient();
  const error = { response: { status: 400, data: { detail: "Configure sua chave Gemini no perfil" } } };
  await assert.rejects(client.reject(error), actual => actual === error);
  assert.deepEqual(client.events.map(event => event.type), ["open-gemini-key-modal"]);
});

test("Gemini quota and invalid-key notifications remain available", async () => {
  for (const detail of ["Sua cota da API Gemini esgotou", "A chave de API Gemini é inválida"]) {
    const client = await loadClient();
    const error = { response: { status: 400, data: { detail } } };
    await assert.rejects(client.reject(error), actual => actual === error);
    assert.equal(client.events[0].type, "gemini-api-error");
    assert.equal(client.events[0].detail, detail);
  }
});

test("offline-mode failures keep their existing dedicated marker", async () => {
  const client = await loadClient({ offline: true });
  await assert.rejects(client.reject(new Error("network")), error => error.isOfflineError === true);
  assert.equal(client.location.href, "/studies");
});

test("credential injection is unaffected by the error formatter", async () => {
  const client = await loadClient();
  const config = client.request({ headers: {} });
  assert.equal(config.headers.Authorization, "Bearer test-session");
  assert.equal(config.withCredentials, true);
});
