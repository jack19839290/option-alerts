import fs from "node:fs";
import vm from "node:vm";

const code = fs.readFileSync(new URL("../apps-script/Code.gs", import.meta.url), "utf8");
const html = fs.readFileSync(new URL("../apps-script/Index.html", import.meta.url), "utf8");
const browserScript = html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
if (!browserScript) throw new Error("Index.html is missing its browser script");

new vm.Script(code);
new vm.Script(browserScript);
const autoHtml = fs.readFileSync(new URL('../apps-script/AutoIndex.html', import.meta.url), 'utf8');
new vm.Script(autoHtml.match(/<script>([\s\S]*?)<\/script>/)[1]);

const context = {
  console,
  Utilities: {formatDate: () => "2026-09-12"},
};
vm.createContext(context);
vm.runInContext(`${code}\nthis.buildQueueEmail = buildQueueEmail_; this.expirationDte = expirationDte_;`, context);

if (context.expirationDte("2027-09-12") !== 365 || context.expirationDte("2027-09-13") !== 366) {
  throw new Error("The one-year DTE boundary is incorrect");
}

const groups = [
  {ticker: "INTC", expiry: "2027-06-18", items: [{strike: 40, option_type: "PUT", dte: 279}]},
  {ticker: "AAPL", expiry: "2027-09-17", items: []},
  {ticker: "AAPL", expiry: "2027-03-19", items: [{strike: 250, option_type: "PUT", dte: 188}]},
  {ticker: "AAPL", expiry: "2027-01-15", items: [{strike: 240, option_type: "PUT", dte: 125}]},
];
const message = context.buildQueueEmail(
  "FIRST_CLOSE",
  {market_date: "2026-09-11", groups},
  "https://example.invalid",
);
if (message.body.includes("AAPL 2027-09-17")) throw new Error("A zero-match group was rendered");
const positions = ["AAPL 2027-01-15", "AAPL 2027-03-19", "INTC 2027-06-18"]
  .map(value => message.body.indexOf(value));
if (positions.some(value => value < 0) || !(positions[0] < positions[1] && positions[1] < positions[2])) {
  throw new Error("Close-email groups are not sorted by ticker and expiry");
}

const emptyMessage = context.buildQueueEmail(
  "FIRST_CLOSE",
  {market_date: "2026-09-11", groups: [{ticker: "MU", expiry: "2027-03-19", items: []}]},
  "https://example.invalid",
);
if (!emptyMessage.body.includes("本日收盤無符合第一門檻的合約")) {
  throw new Error("The all-zero close summary is missing");
}

console.log("Apps Script syntax and close-email behavior OK");
