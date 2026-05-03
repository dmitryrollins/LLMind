# llmind-cli

Embed signed semantic-metadata layers into images, PDFs, and audio files.

`llmind` analyzes a JPEG, PNG, PDF, MP3, WAV, or M4A file with an LLM, then
writes the extracted text, description, and document structure into the file
itself as XMP metadata. The file stays normal — it opens in any viewer — but
machine-readable agents can now consume it without re-running OCR or vision
inference.

Each layer is HMAC-SHA256 signed and bound to the file's SHA-256 hash, so
tampering invalidates the layer.

## Install

```bash
pipx install 'llmind-cli[anthropic]'
```

Pick your provider — extras are opt-in:

| Extra            | What you get                                  |
| ---------------- | --------------------------------------------- |
| `anthropic`      | Claude vision (recommended default)           |
| `openai`         | GPT-4o vision + Whisper transcription         |
| `gemini`         | Gemini 2.0 vision + audio                     |
| `whisper-local`  | Offline Whisper via `faster-whisper`          |
| `embeddings`     | VoyageAI embeddings for semantic search       |
| `all`            | Everything above                              |

Combine with commas: `pipx install 'llmind-cli[anthropic,whisper-local]'`.

`uv tool install 'llmind-cli[anthropic]'` works the same way.

**Requires** Python 3.11+. PDF rendering also needs `poppler-utils`
(`brew install poppler` on macOS, `apt install poppler-utils` on
Debian/Ubuntu). Image and audio support work out of the box.

## Quick start

```bash
export ANTHROPIC_API_KEY=sk-ant-...

llmind enrich photo.jpg          # writes signed metadata into photo.jpg
llmind read photo.jpg            # show the embedded layer
llmind verify photo.jpg          # check signature + checksum
llmind history photo.jpg         # list every enrichment version
llmind strip photo.jpg           # remove the metadata layer
```

`llmind --help` lists every command. Each command has its own `--help`.

## Commands

- `enrich` — analyze and embed a new metadata layer
- `reenrich` — re-run enrichment in place (no rename)
- `read` — display the embedded layer
- `verify` — check signature and file checksum
- `history` — list every layer version
- `strip` — remove LLMind metadata
- `embed` — store a semantic vector inside a `.llmind` file
- `search` — hybrid semantic + keyword search across enriched files
- `watch` — auto-enrich files dropped into a directory

## License

MIT. See [LICENSE](https://github.com/dmitryrollins/LLMind/blob/main/LICENSE).

## Source and issue tracker

https://github.com/dmitryrollins/LLMind
