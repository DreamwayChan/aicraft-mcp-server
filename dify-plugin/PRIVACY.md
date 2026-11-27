# Privacy Policy — AICraft Injection Molding Plugin

Last updated: 2026-11-27

## 1. Overview

The **AICraft Injection Molding** plugin connects your Dify workspace to the external service **AICraft Injection Process API** (`https://aicraft4injection.com`) to compute physics-based first-shot process setups and defect-driven parameter adjustments for injection molding.

## 2. Data Transmitted

When a tool in this plugin is invoked, only the technical engineering parameters explicitly supplied to the tool are transmitted over HTTPS (TLS) to `https://aicraft4injection.com`:

- **Authentication Header**: Your API key (`sk_...`), sent in the `Authorization` header solely to authenticate requests and check monthly call limits.
- **Technical Process Inputs**: Material grade/properties (e.g., polymer abbreviation, melt density), part/mold geometry (e.g., wall thickness, shot weight, flow length, gate thickness), injection machine specifications (e.g., screw diameter, clamp force, stroke), observed defect codes, and optional on-machine measurements.
- **Optional Process Archive ID (`business_id` / `process_no`)**: When you supply a `business_id`, the resulting process setup is stored in an isolated per-account scope (`k<id>-<business_id>`) so subsequent `optimize_defect` calls can load your baseline setup automatically.

## 3. Data We Do NOT Collect

- This plugin does **not** collect personal data, end-user identities, chat histories outside tool arguments, or device identifiers.

## 4. Storage, Retention & Third-Party Sharing

- We do **not** sell, rent, or share your credentials or molding process payloads with any third party or advertiser, nor do we use customer process parameters to train third-party foundation models.
- Short-lived request logging is retained strictly for debugging, rate-limiting, and abuse prevention.

## 5. Data Deletion & Contact

You may request deletion of your API key record and any stored process archive entries at any time by contacting:

- **Email**: `mosschan550@gmail.com`
- **Hosted Privacy Policy**: https://aicraft4injection.com/legal/privacy
- **Terms of Service**: https://aicraft4injection.com/legal/terms
