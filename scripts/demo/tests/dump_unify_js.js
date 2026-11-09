// Runs the page's term unification on texts given as JSON [{domain, text}] (argv[2]) and prints the groups (compared by parity_unify.py).
const fs = require("fs");
const DATA_DIR = __dirname + "/../../../demo_local";
const html = fs.readFileSync(__dirname + "/../kass-lab.html", "utf8");
let js = html.split("<script>")[1].split("</script>")[0];
js = js.replace(/\}\)\(\);\s*$/, "globalThis.K = { analyse, unifyTerms, setDomain: id => { current = id }, ready: () => !!(DATA && WORDS && WORD_GEN) }; })();");
const stub = () => ({ addEventListener() {}, textContent: "", innerHTML: "", hidden: true, disabled: true, value: "", classList: { add() {}, remove() {} }, style: {}, setAttribute() {}, focus() {} });
const els = {}; global.document = { getElementById: id => els[id] || (els[id] = stub()), querySelectorAll: () => [], addEventListener() {}, documentElement: { dataset: {} } };
global.fetch = u => { const p = DATA_DIR + "/" + String(u); return Promise.resolve(fs.existsSync(p) ? { ok: true, text: () => fs.readFileSync(p, "utf8"), json: () => JSON.parse(fs.readFileSync(p, "utf8")) } : { ok: false }); };
global.performance = { now: () => 0 }; global.matchMedia = () => ({ matches: false });
eval(js);
const cases = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const iv = setInterval(() => {
  if (!K.ready()) return;
  clearInterval(iv);
  const out = cases.map(c => { K.setDomain(c.domain); return K.unifyTerms(c.text, K.analyse(c.text)); });
  process.stdout.write(JSON.stringify(out));
}, 100);
