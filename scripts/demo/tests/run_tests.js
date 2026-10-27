// Test harness: loads the page script with DOM stubs and exposes analyse() for a gold set.
const fs = require("fs");
const html = fs.readFileSync(__dirname + "/../kass-lab.html", "utf8");
let js = html.split("<script>")[1].split("</script>")[0];
js = js.replace("let EMB_W = 2", "let EMB_W = " + (process.env.EMB_W || 2)); js = js.replace(/\}\)\(\);\s*$/, "globalThis.__sense = r => DATA.senses[r[0]][0]; globalThis.K = { analyse, setDomain: id => { current = id }, termKey, normalize }; })();");
const stub = () => ({ addEventListener() {}, textContent: "", innerHTML: "", hidden: true, disabled: true, value: "", classList: { add() {}, remove() {} }, style: {} });
const els = {}; global.document = { getElementById: id => els[id] || (els[id] = stub()), querySelectorAll: () => [], addEventListener() {} };
global.fetch = u => { const p = __dirname + "/../../../demo_local" + "/" + String(u); return Promise.resolve(fs.existsSync(p) ? { ok: true, text: () => fs.readFileSync(p, "utf8"), json: () => JSON.parse(fs.readFileSync(p, "utf8")) } : { ok: false }); };
global.performance = { now: () => 0 }; global.matchMedia = () => ({ matches: false });
eval(js);
setTimeout(() => {
  const gold = JSON.parse(fs.readFileSync(__dirname + "/" + (process.argv[2] || "gold.json"), "utf8"));
  let tp = 0, fn = 0, fp = 0, wrong = 0; const misses = [], extras = [], wrongs = [];
  for (const g of gold) {
    K.setDomain(g.domain);
    const res = K.analyse(g.text);
    const found = res.items.filter(x => x.state !== "std");
    const used = new Set();
    for (const [surface, term] of Object.entries(g.expect || {})) {
      const it = found.find(x => x.original === surface);
      if (!it) { fn++; misses.push(`[${g.domain}] ${surface} → ${term}`); continue; }
      used.add(it);
      const terms = it.choices.map(r => K.termKey(K.DATA ? "" : "") || "");
      const allKey = t => K.normalize(t).split(" ").map(w => w.startsWith("ال") && w.length > 3 ? w.slice(2) : w).join(" ");
      const ok = term.split("|").some(t => allKey(globalThis.__sense(it.choices[0])) === allKey(t));
      if (ok) tp++; else { wrong++; wrongs.push(`[${g.domain}] ${surface} → got ${it.sense[0]} (want ${term})`); }
    }
    for (const it of found) if (!used.has(it)) { fp++; extras.push(`[${g.domain}] ${it.original} → ${it.sense[0]} (${it.state})`); }
  }
  const P = tp / Math.max(1, tp + wrong + fp), R = tp / Math.max(1, tp + fn + wrong);
  console.log(`cases ${gold.length} | correct ${tp} | missed ${fn} | wrong term ${wrong} | extra ${fp} | recall ${(100 * R).toFixed(1)}% | precision ${(100 * P).toFixed(1)}%`);
  if (process.argv.includes("-v")) {
    console.log("\nMISSED:\n  " + misses.join("\n  "));
    console.log("\nWRONG:\n  " + wrongs.join("\n  "));
    console.log("\nEXTRA:\n  " + extras.join("\n  "));
  }
}, 6000);
