/**
 * Trigger the GitHub Actions hunt workflow (workflow_dispatch).
 * Auth: header x-dashboard-secret must match DASHBOARD_SECRET.
 */
async function triggerWorkflow({ fullSweep = false, skipScoring = false } = {}) {
  const repo = process.env.GITHUB_REPO;
  const token = process.env.GITHUB_TOKEN;
  const workflow = process.env.GITHUB_WORKFLOW || "vinted-bot.yml";
  const ref = process.env.GITHUB_REF || "main";
  if (!repo || !token) {
    const err = new Error("GITHUB_REPO and GITHUB_TOKEN are required");
    err.status = 500;
    throw err;
  }

  const url = `https://api.github.com/repos/${repo}/actions/workflows/${workflow}/dispatches`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "User-Agent": "vinted-hunt-dashboard",
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      ref,
      inputs: {
        skip_scoring: String(Boolean(skipScoring)),
        full_sweep: String(Boolean(fullSweep)),
      },
    }),
  });

  if (res.status !== 204 && res.status !== 200) {
    const text = await res.text();
    const err = new Error(`GitHub dispatch failed (${res.status}): ${text.slice(0, 300)}`);
    err.status = res.status;
    throw err;
  }
  return { ok: true, repo, workflow, ref, full_sweep: Boolean(fullSweep) };
}

function authorized(req) {
  const expected = process.env.DASHBOARD_SECRET || "";
  if (!expected) return false;
  const header = req.headers["x-dashboard-secret"] || "";
  const bearer = (req.headers.authorization || "").replace(/^Bearer\s+/i, "");
  return header === expected || bearer === expected;
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    if (req.body && typeof req.body === "object") {
      resolve(req.body);
      return;
    }
    let raw = "";
    req.on("data", (chunk) => {
      raw += chunk;
      if (raw.length > 1e6) reject(new Error("body_too_large"));
    });
    req.on("end", () => {
      if (!raw) {
        resolve({});
        return;
      }
      try {
        resolve(JSON.parse(raw));
      } catch (err) {
        reject(err);
      }
    });
    req.on("error", reject);
  });
}

module.exports = async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "POST") {
    res.statusCode = 405;
    res.json({ error: "method_not_allowed" });
    return;
  }
  if (!authorized(req)) {
    res.statusCode = 401;
    res.json({ error: "unauthorized" });
    return;
  }
  try {
    const body = await readBody(req);
    const result = await triggerWorkflow({
      fullSweep: Boolean(body.full_sweep || body.fullSweep),
      skipScoring: Boolean(body.skip_scoring || body.skipScoring),
    });
    res.statusCode = 200;
    res.json(result);
  } catch (err) {
    res.statusCode = err.status || 500;
    res.json({ error: "trigger_failed", message: String(err.message || err) });
  }
};

module.exports.triggerWorkflow = triggerWorkflow;
module.exports.authorized = authorized;
