# AI Handoff Document - JSON Translator v1.0.0

## 1) Purpose
This application is a desktop JSON translation tool for game/localization workflows.
It is designed to:
- Load a JSON file.
- Extract translatable keys (string-value keys).
- Let user choose include/exclude keys.
- Translate selected text values via OpenAI or Gemini APIs.
- Save translated JSON and detailed logs.

Primary implementation file:
- `main.py`

---

## 2) Runtime and Dependencies
Language/runtime:
- Python 3.10+

UI stack:
- `tkinter`
- `ttkbootstrap`

API providers:
- OpenAI SDK: `openai`
- Gemini SDK: `google-genai`

Standard libraries used:
- `json`, `threading`, `importlib`, `random`, `time`, `datetime`, `pathlib`

Install dependencies (from project root):
- `pip install -r requirements.txt`

Run:
- `python main.py`

---

## 3) High-Level UX Structure
The UI has 5 sections:
1. File
2. Key Selection
3. Translation Settings
4. System Prompt
5. Run / Log

Important enable/disable rule:
- Sections 2-5 remain disabled until JSON is validated and keys are analyzed.
- During active translation, sections 1-4 are locked.
- After translation stops/completes/errors, lock is released and normal section state is restored.

---

## 4) Core Features Implemented
### 4.1 File and JSON handling
- Browse and validate JSON.
- Preview root JSON type.
- Auto-generate save path (`<input_stem>.translated.json`) when file selected.
- Manual save path selection is supported.

### 4.2 Key extraction and selection
- Traverses JSON recursively.
- Only keys whose values are strings are considered translatable candidates.
- Key Manager allows moving keys between Translate and Exclude lists.
- Filter boxes for both lists.
- Supports Exclude All / Include All.

### 4.3 Key state retention across files
When analyzing a newly loaded file:
- Existing Exclude keys are retained only if they also exist in new file (intersection retention).
- Any new keys not in Exclude are added to Translate.
- If no overlap exists, behavior appears as reset (Exclude empty, Translate filled with new keys).

### 4.4 Translation providers
Supported providers:
- OpenAI
- Gemini

Provider-specific model lists are populated in UI.

### 4.5 Source language behavior
Source language options:
- `auto`, `en`, `ja`, `ko`

Current default source language:
- `auto`

Prompt behavior:
- If source is `auto`: explicitly instruct model to detect source language from text.
- If source is fixed (`en/ja/ko`): detect actual text language first; if mismatched, ignore configured source and use detected language.

Local pre-check:
- If source and target are the same (and source is explicit), translation is blocked before any API call.

### 4.6 API key management
- Separate key pools by provider (`OpenAI`, `Gemini`).
- Add/remove/reorder keys (priority by order).
- Masked key display in manager list.
- Retry on API errors with exponential backoff + jitter.
- After 3 consecutive errors on one key, rotate to next key.
- Fail when all keys exhausted.

### 4.7 Translation execution
- Runs on background thread.
- Recursively traverses JSON and translates only eligible strings.
- Maintains counters: done / translated / skipped / failed.
- Progress bar updates by `done / total_targets`.
- Supports user stop request (graceful stop between calls).

### 4.8 Logging and save
- Timestamped logs in UI.
- Real-time per-key success log: `Translated[key] 'src' -> 'dst'`.
- Save log to `.txt`.
- Auto-save translated JSON on completion if save path exists.

Overwrite safety:
- If save path is auto-assigned and file already exists, confirm overwrite before starting translation.
- Manual save dialog already has OS-level overwrite confirmation.

### 4.9 Settings persistence
Saved in `settings.json`:
- provider, model, source/target language
- API keys by provider
- Gemini options
- system prompt

Backward compatibility:
- If old settings use legacy `api_key` or `api_keys`, they are migrated into OpenAI key pool.

---

## 5) Main Internal Data Model (TranslatorUI state)
Key fields:
- `selected_file`, `save_path_var`
- `provider_var`, `model_var`
- `source_lang_var`, `target_lang_var`
- `api_keys_by_provider: {"OpenAI": [...], "Gemini": [...]}`
- `all_keys`, `translate_keys`, `exclude_keys`
- `translation_running`, `translated_result`
- `sections_enabled` (controls section availability)
- `save_path_auto_assigned` (controls overwrite-confirm behavior)

---

## 6) Important Method Map (main.py)
UI build:
- `_build_file_section`
- `_build_key_selection_section`
- `_build_translation_section`
- `_build_system_prompt_section`
- `_build_log_section`

State/UI control:
- `_set_sections_enabled`
- `_set_sections_2_to_4_enabled`
- `_set_translation_ui_locked`
- `_update_provider_dependent_ui`

File/key handling:
- `_choose_file`
- `_choose_save_path`
- `_validate_and_activate_selected_json`
- `_extract_all_keys`
- `_analyze_keys`
- `_open_key_manager`
- `_refresh_key_listboxes`

Run pipeline:
- `_start_translation`
- `_run_translation_job`
- `_translate_node`
- `_translate_text_with_provider`
- `_stop_translation`

Provider calls:
- `_create_openai_client`
- `_create_gemini_client`
- `_create_provider_client`
- `_translate_text_openai_once`
- `_translate_text_gemini_once`

API key manager:
- `_open_api_key_manager`
- `_add_api_key`
- `_remove_selected_api_keys`
- `_move_api_key_up`
- `_move_api_key_down`

Settings/log/save:
- `_save_settings`
- `_load_settings`
- `_save_log`
- `_write_json_file`
- `_append_log`

---

## 7) Translation Flow (Execution Order)
1. User selects file.
2. JSON validation succeeds.
3. User clicks Analyze Keys.
4. Sections 2-5 become enabled.
5. User configures provider/model/languages/key selection/API keys.
6. User starts translation.
7. Prechecks run (including source/target same-language check and auto-save overwrite confirm for auto path).
8. Background worker starts.
9. Recursive translation executes with retry/backoff/key rotation.
10. Result auto-saved, logs emitted, UI restored.

---

## 8) Known Design Decisions
- Translation candidates are determined by key/value shape: only string values are translated.
- Key-based include/exclude applies globally by key name across nested structures.
- Exclude list is session behavior in runtime and can be influenced by key manager transitions across files.
- UI does not perform strict schema validation of game JSON; it performs generic JSON parsing.

---

## 9) Maintenance Guidance for Future AI Sessions
When adding or changing features, verify these invariants:
1. Section enable/disable lifecycle remains consistent.
2. Background thread never updates Tk widgets directly (use `_post_ui`).
3. API failures preserve retry/backoff/key-rotation behavior.
4. New settings fields are backward-compatible in `_load_settings`.
5. Key retention logic across files still follows intersection-retain + new-to-translate rule.
6. Save-path overwrite behavior remains safe for auto-assigned paths.

Recommended validation after edits:
- Run static error check on `main.py`.
- Manually test these scenarios:
  - Analyze keys on two different files with partial/no key overlap.
  - Source `auto` and fixed source modes.
  - Source=Target block behavior.
  - Translation start/stop and UI lock/unlock.
  - Existing auto save-path overwrite confirm.
  - API key rotation after forced failures.

---

## 10) Version Note
This document reflects the codebase state for:
- JSON Translator `Version 1.0.0`
