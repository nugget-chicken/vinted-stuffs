/**
 * Latest GitHub Actions runs for the hunt workflow (for dashboard status).
 */
module.exports = async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "GET") {
    res.statusCode = 405;
    res.json({ error: "method_not_allowed" });
    return;
  }
  const repo = process.env.GITHUB_REPO;
  const token = process.env.GITHUB_TOKEN;
  const workflow = process.env.GITHUB_WORKFLOW || "vinted-bot.yml";
  if (!repo || !token) {
    res.statusCode = 200;
    res.json({ runs: [], note: "GITHUB_REPO/TOKEN not configured" });
    return;
  }
  try {
    const url = `https://api.github.com/repos/${repo}/actions/workflows/${workflow}/runs?per_page=5`;
    const gh = await fetch(url, {
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${token}`,
        "User-Agent": "vinted-hunt-dashboard",
        "X-GitHub-Api-Version": "2022-11-28",
      },
    });
    if (!gh.ok) {
      const text = await gh.text();
      res.statusCode = gh.status;
      res.json({ error: "github_failed", message: text.slice(0, 300) });
      return;
    }
    const data = await gh.json();
    res.statusCode = 200;
    res.json({
      runs: (data.workflow_runs || []).map((r) => ({
        id: r.id,
        status: r.status,
        conclusion: r.conclusion,
        event: r.event,
        created_at: r.created_at,
        updated_at: r.updated_at,
        html_url: r.html_url,
        display_title: r.display_title,
      })),
    });
  } catch (err) {
    res.statusCode = 500;
    res.json({ error: "status_failed", message: String(err.message || err) });
  }
};
