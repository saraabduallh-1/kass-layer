const fs = require("fs");
const html = fs.readFileSync(__dirname + "/../kass-lab.html", "utf8");
let js = html.split("<script>")[1].split("</script>")[0];
js = js.replace(/\}\)\(\);\s*$/, "globalThis.K = { analyse, setDomain: id => { current = id }, D: () => DATA, C: () => CTX }; })();");
const stub = () => ({ addEventListener() {}, textContent: "", innerHTML: "", hidden: true, disabled: true, value: "", classList: { add() {}, remove() {} }, style: {} });
const els = {}; global.document = { getElementById: id => els[id] || (els[id] = stub()), querySelectorAll: () => [], addEventListener() {} };
global.fetch = u => { const p = __dirname + "/../../../demo_local" + "/" + String(u); return Promise.resolve(fs.existsSync(p) ? { ok: true, text: () => fs.readFileSync(p, "utf8"), json: () => JSON.parse(fs.readFileSync(p, "utf8")) } : { ok: false }); };
global.performance = { now: () => 0 };
eval(js);
setTimeout(() => {
  const [domain, text] = [process.argv[2], process.argv[3]];
  K.setDomain(domain); const D = K.D();
  for (const x of K.analyse(text).items) {
    console.log(`${x.original} [${x.state}] how=${x.m.how} head=${x.m.head}`);
    for (const r of x.choices.slice(0, 6)) console.log(`    ${D.senses[r[0]][0]} | ${D.senses[r[0]][2]} | ${D.dictionaries[D.senses[r[0]][1]].slice(0, 25)} | flags ${r[1]} ${r[2]}`);
  }
}, 6000);
