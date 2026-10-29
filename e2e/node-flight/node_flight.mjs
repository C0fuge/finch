// Node.js Flight SQL client (@firetiger-oss/flight-sql-client): run the TPC-H queries, write TSV answers for e2e/compare.py.
//   node node_flight.mjs <queries-dir> <out-dir> <host:port>   env: FLIGHT_TOKEN, TABLE_PREFIX (default "tpch.")
import fs from "node:fs";
import path from "node:path";
import { FlightSQLClient } from "@firetiger-oss/flight-sql-client";

const [qdir, outDir, addr] = process.argv.slice(2);
const prefix = process.env.TABLE_PREFIX || "tpch.";
const token = process.env.FLIGHT_TOKEN || "";
const [host, port] = addr.split(":");
fs.mkdirSync(outDir, { recursive: true });
const tables = "lineitem|orders|customer|part|partsupp|supplier|nation|region";
const re1 = new RegExp(`\\b(from|join)\\s+(${tables})\\b`, "gi");
const re2 = new RegExp(`,\\s*(${tables})\\b`, "gi");

function decimalStr(words, scale) {
  let v = 0n;
  for (let i = words.length - 1; i >= 0; i--) v = (v << 32n) | BigInt(words[i]);
  const bits = BigInt(words.length * 32);
  if (v >> (bits - 1n)) v -= 1n << bits;
  const neg = v < 0n; if (neg) v = -v;
  let s = v.toString();
  if (scale > 0) { s = s.padStart(scale + 1, "0"); s = s.slice(0, -scale) + "." + s.slice(-scale); }
  return (neg ? "-" : "") + s;
}
const iso = (d) => d.toISOString();

function cell(v, field) {
  if (v === null || v === undefined) return "\\N";
  const name = field.type.constructor.name;
  if (name === "Decimal") return decimalStr(v, field.type.scale);
  if (name.startsWith("Date")) return iso(typeof v === "number" ? new Date(v) : v).slice(0, 10);
  if (name.startsWith("Timestamp")) return iso(typeof v === "number" ? new Date(v) : v).slice(0, 19).replace("T", " ");
  if (typeof v === "boolean") return v ? "true" : "false";
  return String(v);
}

const client = new FlightSQLClient({ host, port: Number(port), plaintext: true, ...(token ? { token } : {}) });
for (const f of fs.readdirSync(qdir).filter((x) => x.endsWith(".sql")).sort()) {
  const name = f.slice(0, -4);
  let sql = fs.readFileSync(path.join(qdir, f), "utf8");
  sql = sql.replace(re1, (_, a, t) => `${a} ${prefix}${t}`).replace(re2, (_, t) => `, ${prefix}${t}`);
  try {
    const table = await client.executeQuery(sql);
    const fields = table.schema.fields;
    const lines = [];
    for (let r = 0; r < table.numRows; r++)
      lines.push(fields.map((fl, c) => cell(table.getChildAt(c).get(r), fl)).join("\t"));
    fs.writeFileSync(path.join(outDir, name + ".tsv"), lines.map((l) => l + "\n").join(""));
  } catch (e) {
    fs.writeFileSync(path.join(outDir, name + ".err"), String(e && e.message || e).split(/\s+/).join(" ") + "\n");
  }
}
await client.close();
