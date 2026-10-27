// Runs the page's engine on every gold sentence and prints the results as JSON (compared by parity.py).
const fs = require("fs");
const DATA_DIR = process.argv[2] || __dirname + "/../../../demo_local";
const html = fs.readFileSync(__dirname + "/../kass-lab.html", "utf8");
let js = html.split("<script>")[1].split("</script>")[0];
js = js.replace(/\}\)\(\);\s*$/, "globalThis.K = { analyse, setDomain: id => { current = id }, D: () => DATA }; })();");
const stub = () => ({ addEventListener() {}, textContent: "", innerHTML: "", hidden: true, disabled: true, value: "", classList: { add() {}, remove() {} }, style: {} });
const els = {}; global.document = { getElementById: id => els[id] || (els[id] = stub()), querySelectorAll: () => [], addEventListener() {} };
global.fetch = u => Promise.resolve({ ok: true, text: () => fs.readFileSync(DATA_DIR + "/senses.txt", "utf8"),
  json: () => JSON.parse(fs.readFileSync(DATA_DIR + "/" + (String(u).includes("context") ? "context.json" : "index.json"), "utf8")) });
global.performance = { now: () => 0 };
eval(js);
setTimeout(() => {
  const out = [];
  for (const f of fs.readdirSync(__dirname).filter(f => /^gold.*\.json$/.test(f)).sort())
    for (const g of JSON.parse(fs.readFileSync(__dirname + "/" + f, "utf8"))) {
      K.setDomain(g.domain); const r = K.analyse(g.text), S = K.D().senses;
      out.push({ domain: g.domain, text: g.text, items: r.items.map(x => ({ original: x.original, state: x.state, choices: x.choices.slice(0, 6).map(c => S[c[0]][0]), reasons: x.reasons, notes: x.notes })), unknown: r.unknown });
    }
  process.stdout.write(JSON.stringify(out));
}, 2500);
