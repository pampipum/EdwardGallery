#!/usr/bin/env node

import fs from "node:fs/promises";

const outputPath = new URL("../data/lead-seeds.csv", import.meta.url);

const sectorQueries = [
  { sector: "tourismus", region: "Davos", query: "hotel davos" },
  { sector: "tourismus", region: "Graubuenden", query: "tourismus graubuenden" },
  { sector: "wealth_management", region: "Zuerich", query: "vermoegensverwaltung zuerich" },
  { sector: "private_clinic", region: "Bern", query: "privatklinik bern" },
  { sector: "manufacturing_kmu", region: "Graubuenden", query: "metallbau chur" }
];

const sources = [
  {
    source: "search.ch",
    buildUrl(query) {
      return `https://search.ch/tel/?was=${encodeURIComponent(query)}`;
    }
  },
  {
    source: "local.ch",
    buildUrl(query) {
      return `https://www.local.ch/en/q?what=${encodeURIComponent(query)}`;
    }
  }
];

function extractMatches(html, source) {
  if (source === "search.ch") {
    return extractSearchCh(html, source);
  }

  if (source === "local.ch") {
    return extractLocalCh(html, source);
  }

  return [];
}

function extractSearchCh(html, source) {
  const matches = [];
  const blocks = html.match(/<article class="tel-resultentry[\s\S]*?<\/article>/g) ?? [];

  for (const block of blocks) {
    const name = firstCapture(block, /<h1><a [^>]*>(.*?)<\/a><\/h1>/i);
    const phone = firstCapture(block, /href="tel:[^"]+"[^>]*>(.*?)<\/a>/i);
    const website = firstCapture(block, /class="tel-result-action sl-icon-website" href="(https?:\/\/[^"]+)"/i);

    if (!name || !phone) {
      continue;
    }

    matches.push({
      source,
      name: decode(name),
      phone: decode(phone).replace(/\s+\*/g, "").trim(),
      website: website ? decode(website) : ""
    });
  }

  return dedupe(matches);
}

function extractLocalCh(html, source) {
  const matches = [];
  const entries = html.match(/"title":"[^"]+","entryType":"BUSINESS"[\s\S]*?"__typename":"Entry"/g) ?? [];

  for (const entry of entries) {
    const name = firstCapture(entry, /"title":"([^"]+)"/);
    const phone = firstCapture(entry, /"displayValue":"([^"]+)","label":"[^"]*","refuseAdvertising":(?:true|false|null),"priceInformation":"[^"]*","__typename":"(?:CustomerProvidedPhoneContact|AiGeneratedPhoneContact)"/);
    const website = firstCapture(entry, /"displayValue":"(https?:\/\/[^"]+)","label":null,"refuseAdvertising":(?:true|false|null),"priceInformation":null,"__typename":"AiGeneratedURLContact"/);

    if (!name || !phone) {
      continue;
    }

    matches.push({
      source,
      name: decode(name),
      phone: decode(phone),
      website: website ? decode(website) : ""
    });
  }

  return dedupe(matches);
}

function dedupe(entries) {
  const seen = new Set();
  return entries.filter((entry) => {
    const key = `${entry.name}|${entry.phone}|${entry.website}`;
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function firstCapture(input, regex) {
  const match = input.match(regex);
  return match ? match[1] : "";
}

function decode(value) {
  return value
    .replace(/<[^>]+>/g, "")
    .replace(/\\"/g, "\"")
    .replace(/\\u0026/g, "&")
    .replace(/\\u002F/g, "/")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, "\"")
    .replace(/&#39;/g, "'")
    .replace(/&uuml;/g, "ü")
    .replace(/&ouml;/g, "ö")
    .replace(/&auml;/g, "ä")
    .replace(/&nbsp;/g, " ")
    .trim();
}

async function fetchPage(url) {
  const response = await fetch(url, {
    headers: {
      "user-agent": "SwissAIAuditLeadResearch/1.0 (+internal research)"
    }
  });

  if (!response.ok) {
    throw new Error(`Fetch failed: ${response.status} ${url}`);
  }

  return response.text();
}

async function main() {
  const rows = [
    "sector,region,source,name,phone,website,query,url,notes"
  ];

  for (const queryDef of sectorQueries) {
    for (const source of sources) {
      const url = source.buildUrl(queryDef.query);

      try {
        const html = await fetchPage(url);
        const leads = extractMatches(html, source.source).slice(0, 10);

        for (const lead of leads) {
          rows.push([
            queryDef.sector,
            queryDef.region,
            lead.source,
            csvEscape(lead.name),
            csvEscape(lead.phone),
            csvEscape(lead.website),
            csvEscape(queryDef.query),
            csvEscape(url),
            csvEscape("Verify manually. Respect source terms and outreach laws.")
          ].join(","));
        }
      } catch (error) {
        rows.push([
          queryDef.sector,
          queryDef.region,
          source.source,
          "",
          "",
          "",
          csvEscape(queryDef.query),
          csvEscape(url),
          csvEscape(`Fetch failed: ${error.message}`)
        ].join(","));
      }
    }
  }

  await fs.mkdir(new URL("../data/", import.meta.url), { recursive: true });
  await fs.writeFile(outputPath, rows.join("\n") + "\n", "utf8");
  console.log(`Wrote ${rows.length - 1} rows to ${outputPath.pathname}`);
}

function csvEscape(value) {
  const stringValue = String(value ?? "");
  return `"${stringValue.replaceAll("\"", "\"\"")}"`;
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
