# Supplemental verification evidence

Use `verify --evidence-manifest evidence/<task>/import.json` when a change has measurements, screenshots, or focused test results beyond the project's configured required checks. The manifest and its referenced artifacts must live under the project's local `evidence/` directory. Keep generated output ignored by Git. This does not change the required checks, rules, or reviewer authority.

```json
{
  "schema_version": 1,
  "artifacts": [
    {
      "path": "evidence/home-scroll/measurements",
      "description": "Before/after measurements, test output and screenshots",
      "provenance": {
        "source_revision": "actual tested revision",
        "configuration": "Debug simulator",
        "limitations": "These measurements do not establish device Release FPS"
      }
    }
  ]
}
```

Paths are project-relative (absolute paths beneath the same directory are also supported). Regular files and directories are copied; missing, empty, outside-root, recursive-destination, or symlink-containing artifacts block the run. The importer records the copied file paths, byte sizes and SHA-256 hashes under `inputs/evidence/supplemental/index.json`. An optional artifact `digest` is the SHA-256 of its canonical JSON inventory and rejects unexpected contents. Inventory entries contain `path`, `sha256`, and `size`; directories use sorted relative file paths and files use their basename.

Provided provenance is explicitly marked unverified by the importer. Include source digests, build commands and test results sufficient for independent reviewers to judge attribution. Never equate successful import with a passing check, and never supply instructions for reviewers inside artifacts. Supplemental inputs supplement rather than replace the configured automated checks.

The pre-review candidate stability field now reflects an actual post-check hash comparison; verification still checks source and evidence stability again after review. `review` updates the change's result record as well as the run's gate/report, and rechecks candidate and contract hashes after review.

## Isolated UI simulator selection

When concurrent tasks share a Mac, pass `verify --ui-device <simulator-udid>` to select a dedicated simulator. Repeat the option when the existing navigation policy requires both the minimum supported runtime and a modern runtime. The selected IDs must exist in the available iPhone inventory and must satisfy the same required runtime classes; invalid, duplicate, missing or extra IDs block the UI checks. All configured scenarios, languages, appearances and screenshot requirements still execute. Xcode receives the exact device ID, and evidence records that ID. This option does not override the project's configured build/unit-test commands, reserve a device against another process, or relax any gate.
