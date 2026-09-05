const { buildSnapshot } = require("../lib/snapshot");

module.exports = async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "GET") {
    res.statusCode = 405;
    res.json({ error: "method_not_allowed" });
    return;
  }
  try {
    const snapshot = await buildSnapshot();
    res.statusCode = 200;
    res.json(snapshot);
  } catch (err) {
    res.statusCode = 500;
    res.json({ error: "snapshot_failed", message: String(err.message || err) });
  }
};
