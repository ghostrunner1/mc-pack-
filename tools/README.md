# tools

Generator for this packwiz repo.

- `spec.json`: the full pack contents.
  - `url` entries point at Modrinth/CurseForge with a sha1.
  - `local` entries use the form `repo:<path>`, which is a file already in this repo. Server-only files live in `_files/`.
- `python3 tools/packgen.py`: rebuilds the whole repo (pack.toml, index.toml, *.pw.toml) from spec.json. It keeps `.git`, `.github` and `tools`.

## Adding a mod
1. Append an entry to spec.json (path, url, sha1 hash, side: both/client/server).
2. Run `python3 tools/packgen.py`.
3. Commit and push to main.

## Adding a local file
1. Put the file in the repo. Use `_files/<path>` if it is server/client-only, otherwise use `<path>` itself.
2. Point the entry at it with `"local": "repo:..."`.
