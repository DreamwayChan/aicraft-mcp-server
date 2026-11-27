# AICraft Injection Molding — Official Dify Tool Plugin

Give your Dify Agents, Chatflows, and Workflows industrial-grade **scientific injection molding** calculation capabilities powered by a self-developed physics & fuzzy-expert engine (`https://aicraft4injection.com`).

## Included Tools

| Tool | Endpoint | Quota Cost | Description |
|---|---|---|---|
| **First-Shot Molding Setup** (`first_shot_setup`) | `POST /v1/first-shot` | 1 call | Computes barrel & mold temperatures, multi-stage filling (`IV`/`IP`/`IL`), V/P switchover (`VPTL`), packing (`PP`/`PV`/`PT`), plasticizing (`MEL`/`ML0`/`MSR0`/`MBP0`/`DDAM`), cooling time (`CT`), and stability margins from resin, part/runner/gate, shot weight, and press specs. |
| **Molding Defect Tuning** (`optimize_defect`) | `POST /v1/optimize` | 1 call | Adjusts process parameters for 25 injection molding defects (`SHORTSHOT`, `FLASH`, `SHRINKAGE`, `WARPING`, `BURN`, `WELDLINE`, etc.) using fuzzy expert rules + physical safety guards and 6 on-machine trial measurements. |
| **Field & Defect Catalog** (`get_schema_catalog`) | `GET /v1/schema` | **Free (0 calls)** | Returns the complete dictionary of parameter codes, default units, 25 defect codes, severity levels, and request examples. |

## Setup (30 Seconds)

1. Obtain an API key (`sk_...`) at **https://aicraft4injection.com** ($19/month for 1,000 API calls; validation errors and `get_schema_catalog` cost 0 calls).
2. Install this plugin in Dify and click **Authorize / Configure**.
3. Paste your `sk_...` key into **AICraft API Key** and save (credential verification checks your key at zero quota cost).

## Recommended Two-Step Workflow

1. **Before Trial (`first_shot_setup`)**:
   - Provide `polymer_abbreviation` (e.g. `PC`), `product_ave_thickness` (e.g. `2.0` mm), `injector_screw_diameter_mm` (e.g. `36` mm), **`target_shot_weight_g`** (total shot weight including runner, e.g. `62` g — required for physical screw stroke calculation), and **`business_id`** (e.g. `MOLD-2026-001`).
   - Receive a formatted Markdown **First-Shot Setup Sheet** plus structured JSON containing `process_no`.
2. **After Trial (`optimize_defect`)**:
   - Pass the same **`business_id`** (or `process_no`) + `defect_code` (e.g. `SHORTSHOT`) + `defect_severity` (`moderate`), along with any measured press values (`actual_injection_peak_pressure`, `min_buffer_position`, `actual_product_weight`, `actual_mould_temp`).
   - The server automatically loads your stored baseline process and returns a **Parameter Adjustment Delta Table (`Previous -> Adjusted -> Delta`)** plus the updated full setup.

## Links & Contact

- Website & Subscription: https://aicraft4injection.com
- Technical Guide & FAQ: https://aicraft4injection.com/content
- Source Repository: https://github.com/DreamwayChan/aicraft-mcp-server
- Privacy Policy: https://aicraft4injection.com/legal/privacy
- Support & Contact: mosschan550@gmail.com
