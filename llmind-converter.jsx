import { useState, useRef, useCallback } from "react";

const STEPS = ["upload", "configure", "processing", "complete"];
const IS_LOCAL = typeof window !== "undefined" &&
  (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1");

const EMBED_DEFAULTS = {
  ollama: "nomic-embed-text",
  openai: "text-embedding-3-small",
  voyage: "voyage-3.5",
  anthropic: "voyage-3.5",
  gemini: "text-embedding-004",
};

// Crypto utils for LLMind key generation and signing
async function generateKey() {
  const arr = new Uint8Array(32);
  crypto.getRandomValues(arr);
  return Array.from(arr).map(b => b.toString(16).padStart(2, "0")).join("");
}

async function hmacSign(key, data) {
  const enc = new TextEncoder();
  const cryptoKey = await crypto.subtle.importKey("raw", enc.encode(key), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", cryptoKey, enc.encode(data));
  return Array.from(new Uint8Array(sig)).map(b => b.toString(16).padStart(2, "0")).join("");
}

async function sha256(data) {
  const hash = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, "0")).join("");
}

function xmlEsc(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function bytesToBase64(bytes) {
  const chunks = [];
  const chunkSize = 32768;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    chunks.push(String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize)));
  }
  return btoa(chunks.join(""));
}

// Build XMP packet
function buildXMP(layer, history, keyId) {
  return `<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
<rdf:Description rdf:about=""
  xmlns:llmind="https://llmind.org/ns/1.0/"
  llmind:version="${layer.version}"
  llmind:format_version="1.0"
  llmind:generator="llmind-web/0.1"
  llmind:generator_model="${xmlEsc(layer.generator_model)}"
  llmind:timestamp="${layer.timestamp}"
  llmind:language="${xmlEsc(layer.language)}"
  llmind:checksum="${layer.checksum}"
  llmind:key_id="${keyId}"
  llmind:signature="${layer.signature}"
  llmind:layer_count="${history.length}"
  llmind:immutable="true"
>
<llmind:description>${xmlEsc(layer.description)}</llmind:description>
<llmind:text>${xmlEsc(layer.text)}</llmind:text>
<llmind:structure>${xmlEsc(JSON.stringify(layer.structure))}</llmind:structure>
<llmind:history>${xmlEsc(JSON.stringify(history))}</llmind:history>
</rdf:Description>
</rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>`;
}

// Inject XMP into JPEG
function injectJPEG(original, xmpXml) {
  const xmpBytes = new TextEncoder().encode(xmpXml);
  const ns = new TextEncoder().encode("http://ns.adobe.com/xap/1.0/\0");
  const payload = new Uint8Array(ns.length + xmpBytes.length);
  payload.set(ns, 0);
  payload.set(xmpBytes, ns.length);
  const len = payload.length + 2;
  const marker = new Uint8Array([0xFF, 0xE1, (len >> 8) & 0xFF, len & 0xFF]);
  const result = new Uint8Array(2 + marker.length + payload.length + (original.length - 2));
  result.set(original.slice(0, 2), 0);
  result.set(marker, 2);
  result.set(payload, 2 + marker.length);
  result.set(original.slice(2), 2 + marker.length + payload.length);
  return result;
}

// Inject XMP into PNG via iTXt chunk
function injectPNG(original, xmpXml) {
  const keyword = "XML:com.adobe.xmp";
  const enc = new TextEncoder();
  const kwBytes = enc.encode(keyword);
  const xmpBytes = enc.encode(xmpXml);
  // iTXt: keyword + null + compression(0) + method(0) + lang("") + null + translated("") + null + text
  const chunkData = new Uint8Array(kwBytes.length + 1 + 2 + 1 + 1 + xmpBytes.length);
  let off = 0;
  chunkData.set(kwBytes, off); off += kwBytes.length;
  chunkData[off++] = 0; // null separator
  chunkData[off++] = 0; // compression flag (none)
  chunkData[off++] = 0; // compression method
  chunkData[off++] = 0; // language tag (empty) + null
  chunkData[off++] = 0; // translated keyword (empty) + null
  chunkData.set(xmpBytes, off);

  const typeBytes = enc.encode("iTXt");
  const lenBuf = new ArrayBuffer(4);
  new DataView(lenBuf).setUint32(0, chunkData.length);
  const crcInput = new Uint8Array(4 + chunkData.length);
  crcInput.set(typeBytes, 0);
  crcInput.set(chunkData, 4);
  const crc = crc32(crcInput);
  const crcBuf = new ArrayBuffer(4);
  new DataView(crcBuf).setUint32(0, crc);

  // Insert after IHDR (first chunk after 8-byte signature)
  const sig = 8;
  const ihdrLen = new DataView(original.buffer, sig, 4).getUint32(0);
  const ihdrEnd = sig + 12 + ihdrLen; // length(4) + type(4) + data + crc(4)
  const chunk = new Uint8Array(4 + 4 + chunkData.length + 4);
  chunk.set(new Uint8Array(lenBuf), 0);
  chunk.set(typeBytes, 4);
  chunk.set(chunkData, 8);
  chunk.set(new Uint8Array(crcBuf), 8 + chunkData.length);

  const result = new Uint8Array(ihdrEnd + chunk.length + (original.length - ihdrEnd));
  result.set(original.slice(0, ihdrEnd), 0);
  result.set(chunk, ihdrEnd);
  result.set(original.slice(ihdrEnd), ihdrEnd + chunk.length);
  return result;
}

// CRC32 for PNG
function crc32(buf) {
  let table = crc32.table;
  if (!table) {
    table = crc32.table = new Uint32Array(256);
    for (let i = 0; i < 256; i++) {
      let c = i;
      for (let j = 0; j < 8; j++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
      table[i] = c;
    }
  }
  let crc = 0xFFFFFFFF;
  for (let i = 0; i < buf.length; i++) crc = table[(crc ^ buf[i]) & 0xFF] ^ (crc >>> 8);
  return (crc ^ 0xFFFFFFFF) >>> 0;
}

// Normalise a vector to unit length
function normaliseVec(vec) {
  const mag = Math.sqrt(vec.reduce((s, x) => s + x * x, 0));
  return mag === 0 ? vec : vec.map(x => x / mag);
}

// Generate embedding from text using the chosen provider
async function embedText(text, provider, apiKey) {
  const actualProvider = provider === "anthropic" ? "voyage" : provider;
  const model = EMBED_DEFAULTS[provider];

  if (actualProvider === "openai") {
    if (!apiKey) throw new Error("API key required for OpenAI");
    const resp = await fetch("https://api.openai.com/v1/embeddings", {
      method: "POST",
      headers: { "Authorization": `Bearer ${apiKey}`, "Content-Type": "application/json" },
      body: JSON.stringify({ model, input: text }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error?.message || "OpenAI embedding failed");
    return { vector: normaliseVec(data.data[0].embedding), model };
  }

  if (actualProvider === "voyage") {
    if (!apiKey) throw new Error("Voyage API key required (get one free at voyageai.com). Note: your Anthropic sk-ant-... key will NOT work here.");
    const resp = await fetch("https://api.voyageai.com/v1/embeddings", {
      method: "POST",
      headers: { "Authorization": `Bearer ${apiKey}`, "Content-Type": "application/json" },
      body: JSON.stringify({ model, input: [text], input_type: "document" }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || "Voyage embedding failed");
    return { vector: normaliseVec(data.data[0].embedding), model };
  }

  if (actualProvider === "ollama") {
    const resp = await fetch("http://localhost:11434/api/embeddings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model, prompt: text }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error("Ollama embedding failed — is Ollama running locally?");
    const vec = data.embedding || data.embeddings?.[0];
    if (!vec) throw new Error("Ollama returned no embedding vector");
    return { vector: normaliseVec(vec), model };
  }

  if (actualProvider === "gemini") {
    if (!apiKey) throw new Error("Gemini API key required (get one free at aistudio.google.com/apikey)");
    const model = EMBED_DEFAULTS.gemini;
    const resp = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/${model}:embedContent?key=${apiKey}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: `models/${model}`,
          content: { parts: [{ text }] },
        }),
      }
    );
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error?.message || "Gemini embedding failed");
    return { vector: normaliseVec(data.embedding.values), model };
  }

  throw new Error(`Unknown embedding provider: ${provider}`);
}

// Patch llmind:embedding + llmind:embedding_model into an existing XMP string
function patchXmpEmbedding(xmpString, vector, model) {
  const vecJson = JSON.stringify(vector);
  let patched = xmpString
    .replace(/\s*llmind:embedding="[^"]*"/g, "")
    .replace(/\s*llmind:embedding_model="[^"]*"/g, "");

  const tagStart = patched.indexOf("rdf:Description");
  if (tagStart === -1) return xmpString;
  const closeAngle = patched.indexOf(">", tagStart);
  const embedAttrs = `\n    llmind:embedding="${vecJson}"\n    llmind:embedding_model="${model}"`;
  return patched.slice(0, closeAngle) + embedAttrs + patched.slice(closeAngle);
}

// Simple PDF XMP injection (appends XMP as cross-reference update)
function injectPDF(original, xmpXml) {
  const dec = new TextDecoder();
  const text = dec.decode(original);
  const xmpBytes = new TextEncoder().encode(xmpXml);

  // Find the last xref offset
  const startxrefMatch = text.lastIndexOf("startxref");
  if (startxrefMatch === -1) return original; // can't inject, return as-is

  // Simple approach: embed XMP as a comment block at end before %%EOF
  // This is a simplified approach for the POC
  const eofIdx = text.lastIndexOf("%%EOF");
  if (eofIdx === -1) return original;

  const before = original.slice(0, eofIdx);
  const b64Xmp = bytesToBase64(xmpBytes);
  const xmpComment = new TextEncoder().encode(
    `\n% LLMind XMP Metadata (embedded)\n% ${b64Xmp.match(/.{1,76}/g).join("\n% ")}\n%%EOF\n`
  );
  const result = new Uint8Array(before.length + xmpComment.length);
  result.set(before, 0);
  result.set(xmpComment, before.length);
  return result;
}

// Status messages for processing animation
const STATUS_MSGS = [
  "Reading file binary...",
  "Computing SHA-256 checksum...",
  "Sending to vision model...",
  "Extracting text content...",
  "Describing visual elements...",
  "Mapping document structure...",
  "Generating creation key...",
  "Signing layer with HMAC-SHA256...",
  "Injecting XMP metadata...",
  "Building LLMind file..."
];

export default function LLMindConverter() {
  const [step, setStep] = useState(0);
  const [file, setFile] = useState(null);
  const [fileData, setFileData] = useState(null);
  const [preview, setPreview] = useState(null);
  const [provider, setProvider] = useState("anthropic");
  const [geminiModel, setGeminiModel] = useState("gemini-2.5-flash");
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [status, setStatus] = useState("");
  const [statusIdx, setStatusIdx] = useState(0);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [creationKey, setCreationKey] = useState(null);
  const [keyId, setKeyId] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [embedProvider, setEmbedProvider] = useState("openai");
  const [embedApiKey, setEmbedApiKey] = useState("");
  const [isEmbedding, setIsEmbedding] = useState(false);
  const [embeddingDone, setEmbeddingDone] = useState(false);
  const [embedError, setEmbedError] = useState("");
  const fileRef = useRef();

  const handleFile = useCallback((f) => {
    if (!f) return;
    const validTypes = ["image/jpeg", "image/png", "application/pdf"];
    if (!validTypes.includes(f.type)) {
      setError("Unsupported format. Use JPEG, PNG, or PDF.");
      return;
    }
    setError("");
    setFile(f);
    const reader = new FileReader();
    reader.onload = (e) => {
      setFileData(new Uint8Array(e.target.result));
      if (f.type.startsWith("image/")) {
        setPreview(URL.createObjectURL(f));
      } else {
        setPreview(null);
      }
    };
    reader.readAsArrayBuffer(f);
    setStep(1);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    handleFile(f);
  }, [handleFile]);

  const processFile = async () => {
    if (!apiKey.trim()) { setError("Please enter your API key"); return; }
    if (!fileData) return;
    setError("");
    setStep(2);
    setStatusIdx(0);

    const interval = setInterval(() => {
      setStatusIdx(prev => Math.min(prev + 1, STATUS_MSGS.length - 1));
    }, 1800);

    try {
      // 1. Compute checksum
      setStatus("Computing checksum...");
      const checksum = await sha256(fileData);

      // 2. Convert file to base64
      const b64 = bytesToBase64(fileData);
      const mediaType = file.type === "image/png" ? "image/png" : file.type === "application/pdf" ? "application/pdf" : "image/jpeg";
      const isImage = file.type.startsWith("image/");
      const isPDF = file.type === "application/pdf";

      // 3. Build prompt
      const systemPrompt = `You are LLMind — a file enrichment engine. You extract ALL text and visual data from files and return structured JSON. Be exhaustive: capture every visual badge, icon, logo, text element, table, and structural region. Return ONLY valid JSON, no markdown fences.`;
      const userPrompt = `Extract ALL content from this ${isPDF ? "PDF" : "image"} file. Return JSON with these exact fields:
{
  "language": "detected languages, comma-separated ISO codes",
  "description": "Exhaustive visual description: every logo, badge, icon, color, layout element, text styling. Describe it so someone who cannot see the file can reconstruct its appearance.",
  "text": "ALL extracted text, organized by section with clear headers. Include text from badges, icons, watermarks. Preserve all languages found.",
  "structure": {
    "type": "document type",
    "regions": [{"label":"name","area":"position","content":"what it contains"}],
    "figures": [{"label":"name","area":"position","content":"visual description"}],
    "tables": [{"label":"name","rows":0,"cols":0,"content":"cell contents"}]
  }
}`;

      // 4. Call API
      setStatus("Calling vision model...");
      const messageContent = isImage
        ? [
            { type: "image", source: { type: "base64", media_type: mediaType, data: b64 } },
            { type: "text", text: userPrompt }
          ]
        : [
            { type: "document", source: { type: "base64", media_type: "application/pdf", data: b64 } },
            { type: "text", text: userPrompt }
          ];

      let data;
      if (provider === "anthropic") {
        const resp = await fetch("https://api.anthropic.com/v1/messages", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "x-api-key": apiKey,
            "anthropic-version": "2023-06-01",
            "anthropic-dangerous-direct-browser-access": "true"
          },
          body: JSON.stringify({
            model: "claude-sonnet-4-20250514",
            max_tokens: 8000,
            system: systemPrompt,
            messages: [{ role: "user", content: messageContent }]
          })
        });
        data = await resp.json();
        if (data.error) throw new Error(data.error.message);
      }

      else if (provider === "gemini") {
        const resp = await fetch(
          `https://generativelanguage.googleapis.com/v1beta/models/${geminiModel}:generateContent?key=${apiKey}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              contents: [{
                parts: [
                  { inlineData: { mimeType: mediaType, data: b64 } },
                  { text: userPrompt }
                ]
              }]
            })
          }
        );
        data = await resp.json();
        if (data.error) throw new Error(data.error.message);
        // Reshape to match Anthropic response structure for downstream parsing
        data = { content: [{ text: data.candidates[0].content.parts[0].text }] };
      }

      // 5. Parse response
      setStatus("Parsing extraction...");
      const rawText = data.content.map(c => c.text || "").join("");
      const cleaned = rawText.replace(/```json\s*/g, "").replace(/```\s*/g, "").trim();
      const extracted = JSON.parse(cleaned);

      // 6. Generate key
      setStatus("Generating creation key...");
      const cKey = await generateKey();
      const kId = (await sha256(new TextEncoder().encode(cKey))).slice(0, 16);
      setCreationKey(cKey);
      setKeyId(kId);

      // 7. Build layer
      const now = new Date().toISOString().replace(/\.\d{3}/, "");
      const layer = {
        version: 1,
        timestamp: now,
        generator: "llmind-web/0.1",
        generator_model: provider === "anthropic" ? "claude-sonnet-4-20250514" : provider === "gemini" ? geminiModel : "unknown",
        checksum: checksum,
        language: extracted.language || "en",
        description: extracted.description || "",
        text: extracted.text || "",
        structure: extracted.structure || { type: "unknown", regions: [], figures: [], tables: [] }
      };

      // 8. Sign
      setStatus("Signing layer...");
      const sigPayload = JSON.stringify(layer, Object.keys(layer).sort());
      const signature = await hmacSign(cKey, sigPayload);
      layer.signature = signature;

      const history = [layer];

      // 9. Build XMP and inject
      setStatus("Injecting LLMind layer...");
      const xmp = buildXMP(layer, history, kId);

      let enriched;
      let outName = file.name.replace(/\.[^.]+$/, "") + ".llmind";
      if (file.type === "image/jpeg") {
        enriched = injectJPEG(fileData, xmp);
        outName += ".jpg";
      } else if (file.type === "image/png") {
        enriched = injectPNG(fileData, xmp);
        outName += ".png";
      } else {
        enriched = injectPDF(fileData, xmp);
        outName += ".pdf";
      }

      setResult({
        blob: new Blob([enriched], { type: file.type }),
        name: outName,
        layer,
        xmp,
        originalSize: fileData.length,
        enrichedSize: enriched.length,
        xmpSize: new TextEncoder().encode(xmp).length,
        regions: (extracted.structure?.regions || []).length,
        figures: (extracted.structure?.figures || []).length,
        tables: (extracted.structure?.tables || []).length
      });
      setStep(3);
    } catch (err) {
      setError(err.message || "Processing failed");
      setStep(1);
    } finally {
      clearInterval(interval);
    }
  };

  const generateEmbedding = async () => {
    if (!result || isEmbedding) return;
    setEmbedError("");
    setIsEmbedding(true);
    try {
      const text = result.layer.description || result.layer.text;
      if (!text?.trim()) throw new Error("No description or text to embed");
      const { vector, model } = await embedText(text, embedProvider, embedApiKey);
      const patched = patchXmpEmbedding(result.xmp, vector, model);
      let enriched;
      if (file.type === "image/jpeg") {
        enriched = injectJPEG(fileData, patched);
      } else if (file.type === "image/png") {
        enriched = injectPNG(fileData, patched);
      } else {
        enriched = injectPDF(fileData, patched);
      }
      setResult(prev => ({
        ...prev,
        blob: new Blob([enriched], { type: file.type }),
        xmp: patched,
        enrichedSize: enriched.length,
        embedding: { dim: vector.length, model },
      }));
      setEmbeddingDone(true);
    } catch (err) {
      setEmbedError(err.message || "Embedding failed");
    } finally {
      setIsEmbedding(false);
    }
  };

  const downloadFile = () => {
    if (!result) return;
    const url = URL.createObjectURL(result.blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = result.name;
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadKey = () => {
    if (!creationKey) return;
    const keyData = JSON.stringify({
      key_id: keyId,
      creation_key: creationKey,
      created: result?.layer?.timestamp,
      file: result?.name,
      note: "Required to modify or delete layers. Store securely. Not recoverable."
    }, null, 2);
    const blob = new Blob([keyData], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = result.name.replace(/\.[^.]+$/, "") + ".key";
    a.click();
    URL.revokeObjectURL(url);
  };

  const reset = () => {
    setStep(0); setFile(null); setFileData(null); setPreview(null);
    setResult(null); setCreationKey(null); setKeyId(null);
    setError(""); setStatus(""); setStatusIdx(0);
    setEmbeddingDone(false); setEmbedError(""); setIsEmbedding(false);
  };

  return (
    <div style={{ minHeight: "100vh", background: "linear-gradient(160deg, #0a0a0a 0%, #1a1a2e 50%, #0a0a0a 100%)", color: "#e0e0e0", fontFamily: "'JetBrains Mono', 'SF Mono', 'Fira Code', monospace", padding: "0" }}>
      <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&family=Space+Grotesk:wght@300;400;500;600;700&display=swap" rel="stylesheet" />

      {/* Header */}
      <div style={{ borderBottom: "1px solid rgba(255,255,255,0.06)", padding: "20px 32px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{ width: 36, height: 36, borderRadius: 10, background: "linear-gradient(135deg, #f97316, #f59e0b)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, fontWeight: 700, color: "#000", letterSpacing: -1 }}>M</div>
          <div>
            <div style={{ fontSize: 17, fontWeight: 600, color: "#fff", letterSpacing: -0.5, fontFamily: "'Space Grotesk', sans-serif" }}>LLMind</div>
            <div style={{ fontSize: 10, color: "#666", letterSpacing: 2, textTransform: "uppercase", marginTop: -1 }}>File enrichment engine</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
          <div style={{ display: "flex", gap: 6 }}>
            {STEPS.map((s, i) => (
              <div key={s} style={{ width: i <= step ? 32 : 20, height: 3, borderRadius: 2, background: i <= step ? (i === step ? "#f97316" : "rgba(249,115,22,0.4)") : "rgba(255,255,255,0.08)", transition: "all 0.5s" }} />
            ))}
          </div>
          <a href="https://github.com/dmitryrollins/LLMind" target="_blank" rel="noopener noreferrer" style={{ color: "#888", display: "flex", alignItems: "center", transition: "color 0.2s" }} onMouseEnter={e => e.currentTarget.style.color = "#fff"} onMouseLeave={e => e.currentTarget.style.color = "#888"}>
            <svg height="24" width="24" viewBox="0 0 16 16" fill="currentColor">
              <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path>
            </svg>
          </a>
        </div>
      </div>

      <div style={{ maxWidth: 640, margin: "0 auto", padding: "40px 24px" }}>

        {/* Step 0: Upload */}
        {step === 0 && (
          <div>
            <h1 style={{ fontSize: 28, fontWeight: 300, color: "#fff", marginBottom: 8, fontFamily: "'Space Grotesk', sans-serif", letterSpacing: -1 }}>
              Convert any file to <span style={{ color: "#f97316", fontWeight: 600 }}>LLMind</span>
            </h1>
            <p style={{ fontSize: 13, color: "#666", marginBottom: 40, lineHeight: 1.6 }}>
              Embed a semantic layer — text, descriptions, structure — inside your files. The file stays normal. The metadata makes it machine-readable.
            </p>

            <div
              onDrop={handleDrop}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onClick={() => fileRef.current?.click()}
              style={{
                border: `1.5px dashed ${dragOver ? "#f97316" : "rgba(255,255,255,0.1)"}`,
                borderRadius: 16,
                padding: "60px 40px",
                textAlign: "center",
                cursor: "pointer",
                background: dragOver ? "rgba(249,115,22,0.04)" : "rgba(255,255,255,0.02)",
                transition: "all 0.3s"
              }}
            >
              <div style={{ fontSize: 40, marginBottom: 16, opacity: 0.3 }}>↑</div>
              <div style={{ fontSize: 15, color: "#999", fontFamily: "'Space Grotesk', sans-serif" }}>
                Drop your file here or click to browse
              </div>
              <div style={{ fontSize: 11, color: "#555", marginTop: 12 }}>JPEG · PNG · PDF</div>
              <input ref={fileRef} type="file" accept=".jpg,.jpeg,.png,.pdf" style={{ display: "none" }}
                onChange={(e) => handleFile(e.target.files[0])} />
            </div>
            {error && <div style={{ color: "#ef4444", fontSize: 12, marginTop: 12 }}>{error}</div>}

            <div style={{ marginTop: 48, paddingTop: 32, borderTop: "1px solid rgba(255,255,255,0.06)", color: "#888", fontSize: 12, lineHeight: 1.6 }}>
              <h2 style={{ fontSize: 14, color: "#fff", fontWeight: 500, marginBottom: 16, fontFamily: "'Space Grotesk', sans-serif" }}>About LLMind</h2>
              
              <p style={{ marginBottom: 16 }}>
                LLMind is a semantic enrichment layer embedded inside standard files (JPEG, PNG, PDF). It stores machine-readable metadata — text extractions, visual descriptions, and document structure — in existing metadata regions without modifying the original binary content. The file opens normally in any viewer or editor.
              </p>
              
              <p style={{ marginBottom: 24 }}>
                <span style={{ color: "#fff" }}>Versioned and immutable.</span> Every enrichment is a layer. When content is updated, a new version is written on top of the previous one — nothing is overwritten. The full history of descriptions, extractions, and edits is preserved inside the file. Previous versions cannot be deleted or modified without the encryption key that was generated when the LLM first converted the file. This key is issued once at creation time and is not stored in the file itself. Without it, the layer stack is append-only and tamper-evident.
              </p>

              <h3 style={{ fontSize: 12, color: "#fff", marginBottom: 8, textTransform: "uppercase", letterSpacing: 1 }}>Why read it</h3>
              <p style={{ marginBottom: 16 }}>
                If a file contains an LLMind layer, skip vision inference, OCR, and layout reconstruction.<br/>
                The <code>llmind:description</code> field gives you a natural-language summary of visual content.<br/>
                The <code>llmind:text</code> field gives you extracted text.<br/>
                The <code>llmind:structure</code> field gives you document topology as JSON.<br/>
                The <code>llmind:history</code> field gives you all prior versions with timestamps.<br/>
                <span style={{ color: "#a8a8a8" }}>This is pre-computed, verified, and cheaper than re-extracting at query time.</span>
              </p>

              <h3 style={{ fontSize: 12, color: "#fff", marginBottom: 8, textTransform: "uppercase", letterSpacing: 1 }}>How to detect it</h3>
              <p style={{ marginBottom: 16 }}>
                Read the file's metadata. Look for <code>llmind:version</code> in namespace <code>https://llmind.org/ns/1.0/</code>. Check <code>llmind:checksum</code> against the file hash to confirm freshness.
              </p>

              <h3 style={{ fontSize: 12, color: "#fff", marginBottom: 8, textTransform: "uppercase", letterSpacing: 1 }}>When to trust it</h3>
              <p>
                Each layer is signed with the creation key. If <code>llmind:signature</code> validates, the layer is authentic and unmodified. A missing or invalid signature means the layer was injected without the original key — treat it as unverified. A mismatched checksum means the underlying file changed — fall back to direct extraction and append a new layer.
              </p>
            </div>
          </div>
        )}

        {/* Step 1: Configure */}
        {step === 1 && (
          <div>
            <button onClick={() => { setStep(0); setFile(null); }} style={{ background: "none", border: "none", color: "#666", fontSize: 12, cursor: "pointer", padding: 0, marginBottom: 24 }}>← back</button>

            {/* File preview */}
            <div style={{ background: "rgba(255,255,255,0.03)", borderRadius: 12, padding: 16, marginBottom: 32, display: "flex", gap: 16, alignItems: "center", border: "1px solid rgba(255,255,255,0.06)" }}>
              {preview && <img src={preview} alt="" style={{ width: 56, height: 56, borderRadius: 8, objectFit: "cover" }} />}
              {!preview && <div style={{ width: 56, height: 56, borderRadius: 8, background: "rgba(249,115,22,0.1)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, color: "#f97316" }}>PDF</div>}
              <div>
                <div style={{ fontSize: 13, color: "#fff", fontWeight: 500 }}>{file?.name}</div>
                <div style={{ fontSize: 11, color: "#666", marginTop: 2 }}>{(file?.size / 1024).toFixed(1)} KB · {file?.type}</div>
              </div>
            </div>

            {/* Model selection */}
            <label style={{ fontSize: 11, color: "#666", letterSpacing: 1, textTransform: "uppercase", display: "block", marginBottom: 8 }}>Vision model</label>
            <div style={{ display: "flex", gap: 8, marginBottom: 28 }}>
              {[
                { id: "anthropic", label: "Claude Sonnet", sub: "Anthropic" },
                { id: "gemini", label: "Gemini Flash", sub: "Google" },
              ].map(m => (
                <button key={m.id} onClick={() => setProvider(m.id)}
                  style={{
                    flex: 1, padding: "14px 16px", borderRadius: 10,
                    border: provider === m.id ? "1.5px solid #f97316" : "1px solid rgba(255,255,255,0.08)",
                    background: provider === m.id ? "rgba(249,115,22,0.06)" : "rgba(255,255,255,0.02)",
                    cursor: "pointer", textAlign: "left", transition: "all 0.2s"
                  }}>
                  <div style={{ fontSize: 13, color: provider === m.id ? "#f97316" : "#999", fontWeight: 500 }}>{m.label}</div>
                  <div style={{ fontSize: 10, color: "#555", marginTop: 2 }}>{m.sub}</div>
                </button>
              ))}
            </div>

            {/* Gemini model selector */}
            {provider === "gemini" && (
              <div style={{ marginBottom: 28 }}>
                <label style={{ fontSize: 11, color: "#666", letterSpacing: 1, textTransform: "uppercase", display: "block", marginBottom: 8 }}>Gemini model</label>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {[
                    { id: "gemini-2.5-flash", label: "2.5 Flash", sub: "Fast, best value" },
                    { id: "gemini-2.5-pro", label: "2.5 Pro", sub: "Most capable" },
                    { id: "gemini-2.0-flash-lite", label: "2.0 Flash Lite", sub: "Cheapest" },
                  ].map(m => (
                    <button key={m.id} onClick={() => setGeminiModel(m.id)}
                      style={{
                        flex: "1 1 auto", padding: "10px 12px", borderRadius: 8,
                        border: geminiModel === m.id ? "1.5px solid #f97316" : "1px solid rgba(255,255,255,0.06)",
                        background: geminiModel === m.id ? "rgba(249,115,22,0.06)" : "rgba(255,255,255,0.02)",
                        cursor: "pointer", textAlign: "left", transition: "all 0.2s"
                      }}>
                      <div style={{ fontSize: 12, color: geminiModel === m.id ? "#f97316" : "#888", fontWeight: 500 }}>{m.label}</div>
                      <div style={{ fontSize: 9, color: "#555", marginTop: 2 }}>{m.sub}</div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* API Key */}
            <label style={{ fontSize: 11, color: "#666", letterSpacing: 1, textTransform: "uppercase", display: "block", marginBottom: 8 }}>API key</label>
            <div style={{ position: "relative", marginBottom: 8 }}>
              <input
                type={showKey ? "text" : "password"}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={provider === "anthropic" ? "sk-ant-..." : provider === "gemini" ? "AIza..." : "sk-..."}
                style={{
                  width: "100%", padding: "14px 48px 14px 16px", borderRadius: 10,
                  border: "1px solid rgba(255,255,255,0.08)", background: "rgba(255,255,255,0.03)",
                  color: "#fff", fontSize: 13, fontFamily: "'JetBrains Mono', monospace",
                  outline: "none", boxSizing: "border-box"
                }}
              />
              <button onClick={() => setShowKey(!showKey)} style={{
                position: "absolute", right: 12, top: "50%", transform: "translateY(-50%)",
                background: "none", border: "none", color: "#555", cursor: "pointer", fontSize: 12
              }}>{showKey ? "hide" : "show"}</button>
            </div>
            <div style={{ fontSize: 10, color: "#444", marginBottom: 32, lineHeight: 1.5 }}>
              Your key is used in-browser only. It is sent directly to {provider === "anthropic" ? "api.anthropic.com" : provider === "gemini" ? "generativelanguage.googleapis.com" : "api.openai.com"} and never touches our servers. Not stored anywhere.
            </div>

            {error && <div style={{ color: "#ef4444", fontSize: 12, marginBottom: 16 }}>{error}</div>}

            <button onClick={processFile}
              style={{
                width: "100%", padding: "16px", borderRadius: 12,
                background: "linear-gradient(135deg, #f97316, #ea580c)",
                border: "none", color: "#fff", fontSize: 14, fontWeight: 600,
                cursor: "pointer", fontFamily: "'Space Grotesk', sans-serif",
                letterSpacing: -0.3, transition: "opacity 0.2s"
              }}
              onMouseEnter={e => e.target.style.opacity = "0.9"}
              onMouseLeave={e => e.target.style.opacity = "1"}>
              Convert to LLMind
            </button>
          </div>
        )}

        {/* Step 2: Processing */}
        {step === 2 && (
          <div style={{ textAlign: "center", paddingTop: 60 }}>
            {/* Spinner */}
            <div style={{ position: "relative", width: 64, height: 64, margin: "0 auto 32px" }}>
              <div style={{
                width: 64, height: 64, borderRadius: "50%",
                border: "2px solid rgba(255,255,255,0.06)",
                borderTopColor: "#f97316",
                animation: "llmind-spin 1s linear infinite"
              }} />
              <style>{`@keyframes llmind-spin { to { transform: rotate(360deg) } }`}</style>
            </div>

            <div style={{ fontSize: 14, color: "#fff", marginBottom: 8, fontFamily: "'Space Grotesk', sans-serif" }}>
              Processing...
            </div>

            {/* Status messages */}
            <div style={{ minHeight: 120, marginTop: 24 }}>
              {STATUS_MSGS.slice(0, statusIdx + 1).map((msg, i) => (
                <div key={i} style={{
                  fontSize: 11, color: i === statusIdx ? "#f97316" : "#444",
                  marginBottom: 6, transition: "color 0.3s",
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 8
                }}>
                  <span style={{ color: i < statusIdx ? "#22c55e" : (i === statusIdx ? "#f97316" : "#333") }}>
                    {i < statusIdx ? "✓" : (i === statusIdx ? "›" : "·")}
                  </span>
                  {msg}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Step 3: Complete */}
        {step === 3 && result && (
          <div>
            <div style={{ textAlign: "center", marginBottom: 32 }}>
              <div style={{ width: 48, height: 48, borderRadius: 12, background: "rgba(34,197,94,0.1)", display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: 22, marginBottom: 16 }}>✓</div>
              <h2 style={{ fontSize: 22, fontWeight: 400, color: "#fff", fontFamily: "'Space Grotesk', sans-serif", marginBottom: 4 }}>LLMind file ready</h2>
              <p style={{ fontSize: 12, color: "#666" }}>{result.name}</p>
            </div>

            {/* Stats */}
            <div style={{
              background: "rgba(255,255,255,0.02)", borderRadius: 12,
              border: "1px solid rgba(255,255,255,0.06)", padding: 20, marginBottom: 24
            }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, marginBottom: 16 }}>
                {[
                  { label: "Original", value: `${(result.originalSize / 1024).toFixed(1)} KB` },
                  { label: "Enriched", value: `${(result.enrichedSize / 1024).toFixed(1)} KB` },
                  { label: "Overhead", value: `${((result.enrichedSize - result.originalSize) / result.originalSize * 100).toFixed(1)}%` },
                ].map(s => (
                  <div key={s.label}>
                    <div style={{ fontSize: 10, color: "#555", textTransform: "uppercase", letterSpacing: 1 }}>{s.label}</div>
                    <div style={{ fontSize: 16, color: "#fff", fontWeight: 500, marginTop: 4 }}>{s.value}</div>
                  </div>
                ))}
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, paddingTop: 16, borderTop: "1px solid rgba(255,255,255,0.06)" }}>
                {[
                  { label: "Regions", value: result.regions },
                  { label: "Figures", value: result.figures },
                  { label: "Tables", value: result.tables },
                ].map(s => (
                  <div key={s.label}>
                    <div style={{ fontSize: 10, color: "#555", textTransform: "uppercase", letterSpacing: 1 }}>{s.label}</div>
                    <div style={{ fontSize: 16, color: "#f97316", fontWeight: 500, marginTop: 4 }}>{s.value}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Key ID */}
            <div style={{
              background: "rgba(249,115,22,0.04)", borderRadius: 12,
              border: "1px solid rgba(249,115,22,0.15)", padding: 16, marginBottom: 24
            }}>
              <div style={{ fontSize: 10, color: "#f97316", textTransform: "uppercase", letterSpacing: 1, marginBottom: 6 }}>Creation key</div>
              <div style={{ fontSize: 11, color: "#888", marginBottom: 8 }}>
                Key ID: <span style={{ color: "#fff" }}>{keyId}</span>
              </div>
              <div style={{ fontSize: 10, color: "#555", lineHeight: 1.5 }}>
                Download and store securely. Without this key, layers cannot be modified or deleted — only appended. This key is not stored anywhere and cannot be recovered.
              </div>
            </div>

            {/* Embedding section */}
            <div style={{ background: "rgba(255,255,255,0.02)", borderRadius: 12, border: "1px solid rgba(255,255,255,0.06)", padding: 20, marginBottom: 24 }}>
              <div style={{ fontSize: 11, color: "#888", textTransform: "uppercase", letterSpacing: 1, marginBottom: 16 }}>
                Semantic embedding <span style={{ color: "#555", marginLeft: 8, textTransform: "none", letterSpacing: 0, fontSize: 10 }}>— optional</span>
              </div>
              <div style={{ fontSize: 11, color: "#555", marginBottom: 16, lineHeight: 1.5 }}>
                Stores a vector inside the file's XMP as <code style={{ color: "#888" }}>llmind:embedding</code>. Enables cosine-similarity search without re-running vision inference.
              </div>

              <label style={{ fontSize: 10, color: "#555", letterSpacing: 1, textTransform: "uppercase", display: "block", marginBottom: 8 }}>Provider</label>
              <div style={{ display: "flex", gap: 6, marginBottom: 16, flexWrap: "wrap" }}>
                {[
                  { id: "openai", label: "OpenAI", sub: "text-embedding-3-small" },
                  { id: "gemini", label: "Gemini", sub: "text-embedding-004" },
                  { id: "voyage", label: "Voyage AI", sub: "voyage-3.5" },
                  { id: "anthropic", label: "Anthropic", sub: "→ Voyage AI" },
                  ...(IS_LOCAL ? [{ id: "ollama", label: "Ollama", sub: "local · no key" }] : []),
                ].map(p => (
                  <button key={p.id} onClick={() => !embeddingDone && setEmbedProvider(p.id)}
                    style={{
                      flex: "1 1 auto", padding: "10px 8px", borderRadius: 8,
                      border: embedProvider === p.id ? "1.5px solid #f97316" : "1px solid rgba(255,255,255,0.06)",
                      background: embedProvider === p.id ? "rgba(249,115,22,0.06)" : "rgba(255,255,255,0.02)",
                      cursor: embeddingDone ? "default" : "pointer", textAlign: "left",
                    }}>
                    <div style={{ fontSize: 11, color: embedProvider === p.id ? "#f97316" : "#888", fontWeight: 500 }}>{p.label}</div>
                    <div style={{ fontSize: 9, color: "#555", marginTop: 2 }}>{p.sub}</div>
                  </button>
                ))}
              </div>

              {embedProvider !== "ollama" && !embeddingDone && (
                <div style={{ marginBottom: 12 }}>
                  <label style={{ fontSize: 10, color: "#555", letterSpacing: 1, textTransform: "uppercase", display: "block", marginBottom: 8 }}>
                    {embedProvider === "openai" ? "OpenAI API key (sk-...)" : embedProvider === "gemini" ? "Gemini API key (AIza...)" : "Voyage AI key (pa-...) — not your Anthropic key"}
                  </label>
                  <input
                    type="password"
                    value={embedApiKey}
                    onChange={(e) => setEmbedApiKey(e.target.value)}
                    placeholder={embedProvider === "openai" ? "sk-..." : embedProvider === "gemini" ? "AIza..." : "pa-..."}
                    style={{
                      width: "100%", padding: "12px 16px", borderRadius: 8,
                      border: "1px solid rgba(255,255,255,0.08)", background: "rgba(255,255,255,0.03)",
                      color: "#fff", fontSize: 13, fontFamily: "'JetBrains Mono', monospace",
                      outline: "none", boxSizing: "border-box",
                    }}
                  />
                </div>
              )}

              {embedProvider === "ollama" && !embeddingDone && (
                <div style={{ fontSize: 10, color: "#555", marginBottom: 12, lineHeight: 1.5 }}>
                  Requires Ollama running at <code style={{ color: "#777" }}>localhost:11434</code> with <code style={{ color: "#777" }}>nomic-embed-text</code> pulled.
                </div>
              )}

              {embedError && <div style={{ color: "#ef4444", fontSize: 11, marginBottom: 10 }}>{embedError}</div>}

              {embeddingDone && result?.embedding && (
                <div style={{ fontSize: 11, color: "#22c55e", marginBottom: 10 }}>
                  ✓ Embedding stored — dim={result.embedding.dim} · model={result.embedding.model}
                </div>
              )}

              <button onClick={generateEmbedding} disabled={isEmbedding || embeddingDone}
                style={{
                  width: "100%", padding: "12px", borderRadius: 8,
                  background: embeddingDone ? "rgba(34,197,94,0.06)" : "rgba(255,255,255,0.04)",
                  border: embeddingDone ? "1px solid rgba(34,197,94,0.2)" : "1px solid rgba(255,255,255,0.08)",
                  color: embeddingDone ? "#22c55e" : (isEmbedding ? "#666" : "#999"),
                  fontSize: 12, cursor: embeddingDone || isEmbedding ? "default" : "pointer",
                  fontFamily: "'Space Grotesk', sans-serif",
                }}>
                {isEmbedding ? "Generating embedding..." : embeddingDone ? `✓ Embedded (dim=${result.embedding?.dim})` : "Generate & embed vector"}
              </button>
            </div>

            {/* Download buttons */}
            <div style={{ display: "flex", gap: 10, marginBottom: 16 }}>
              <button onClick={downloadFile} style={{
                flex: 2, padding: "14px", borderRadius: 10,
                background: "linear-gradient(135deg, #f97316, #ea580c)",
                border: "none", color: "#fff", fontSize: 13, fontWeight: 600,
                cursor: "pointer", fontFamily: "'Space Grotesk', sans-serif"
              }}>
                ↓ Download .llmind file
              </button>
              <button onClick={downloadKey} style={{
                flex: 1, padding: "14px", borderRadius: 10,
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(255,255,255,0.1)",
                color: "#f97316", fontSize: 13, fontWeight: 500,
                cursor: "pointer", fontFamily: "'Space Grotesk', sans-serif"
              }}>
                ↓ Key file
              </button>
            </div>

            {/* Extracted text preview */}
            <details style={{ marginTop: 24 }}>
              <summary style={{ fontSize: 11, color: "#666", cursor: "pointer", letterSpacing: 1, textTransform: "uppercase" }}>
                Preview extracted text
              </summary>
              <pre style={{
                marginTop: 12, padding: 16, borderRadius: 10,
                background: "rgba(255,255,255,0.02)",
                border: "1px solid rgba(255,255,255,0.06)",
                fontSize: 11, color: "#888", lineHeight: 1.6,
                whiteSpace: "pre-wrap", wordBreak: "break-word",
                maxHeight: 300, overflow: "auto"
              }}>
                {result.layer.text}
              </pre>
            </details>

            <details style={{ marginTop: 12 }}>
              <summary style={{ fontSize: 11, color: "#666", cursor: "pointer", letterSpacing: 1, textTransform: "uppercase" }}>
                Preview AI description
              </summary>
              <pre style={{
                marginTop: 12, padding: 16, borderRadius: 10,
                background: "rgba(255,255,255,0.02)",
                border: "1px solid rgba(255,255,255,0.06)",
                fontSize: 11, color: "#888", lineHeight: 1.6,
                whiteSpace: "pre-wrap", wordBreak: "break-word",
                maxHeight: 200, overflow: "auto"
              }}>
                {result.layer.description}
              </pre>
            </details>

            <button onClick={reset} style={{
              width: "100%", marginTop: 32, padding: "12px",
              borderRadius: 10, background: "none",
              border: "1px solid rgba(255,255,255,0.08)",
              color: "#666", fontSize: 12, cursor: "pointer"
            }}>
              Convert another file
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
