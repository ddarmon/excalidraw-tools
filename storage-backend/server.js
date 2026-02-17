const express = require("express");
const cors = require("cors");
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const app = express();
const PORT = process.env.PORT || 8080;
const DATA_DIR = process.env.DATA_DIR || "/data";

// Ensure data directory exists
fs.mkdirSync(DATA_DIR, { recursive: true });

app.use(cors());

// Parse raw binary bodies (Excalidraw sends no Content-Type header)
app.use(express.raw({ type: () => true, limit: "50mb" }));

// Generate a 16-digit numeric ID
function generateId() {
  const bytes = crypto.randomBytes(8);
  const num = BigInt("0x" + bytes.toString("hex")) % 9000000000000000n + 1000000000000000n;
  return num.toString();
}

// POST /api/v2/post/ — save a scene snapshot, return its ID
app.post("/api/v2/post/", (req, res) => {
  if (!req.body || req.body.length === 0) {
    return res.status(400).json({ error: "Empty body" });
  }

  const id = generateId();
  const filePath = path.join(DATA_DIR, id);

  fs.writeFile(filePath, req.body, (err) => {
    if (err) {
      console.error("Failed to write:", err);
      return res.status(500).json({ error: "Storage error" });
    }
    console.log(`Saved scene ${id} (${req.body.length} bytes)`);
    res.json({ id });
  });
});

// GET /api/v2/:id — retrieve a scene snapshot by ID
app.get("/api/v2/:id", (req, res) => {
  const filePath = path.join(DATA_DIR, path.basename(req.params.id));

  fs.readFile(filePath, (err, data) => {
    if (err) {
      if (err.code === "ENOENT") {
        return res.status(404).json({ error: "Not found" });
      }
      console.error("Failed to read:", err);
      return res.status(500).json({ error: "Storage error" });
    }
    res.set("Content-Type", "application/octet-stream");
    res.send(data);
  });
});

app.listen(PORT, () => {
  console.log(`Excalidraw storage backend listening on port ${PORT}`);
});
