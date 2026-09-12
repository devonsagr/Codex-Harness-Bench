Fix `search_notes` in `/app/notes.py`. Preserve the public function signature.

Required behavior:
- Use the existing `normalize_text` helper for normalization: Unicode case folding and trimming surrounding whitespace.
- Match a normalized substring in either the title or any tag. Missing title/tags are treated as empty.
- Exclude archived notes unless `include_archived=True`.
- An empty or whitespace-only query returns every eligible note.
- Preserve input order and the original note objects. Do not mutate inputs. Accept any iterable, including generators.
- Add no dependencies. Keep `text_utils.py` and `AGENTS.md` unchanged. Additional standard-library tests are welcome.

Run the existing tests and appropriate checks for the new behavior. Only files under `/app` are deliverables.
