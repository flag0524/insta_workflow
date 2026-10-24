# flag_21 Excel plan: 2026-10-25 to 2026-11-23

## Active configuration after workflow replacement
- Source: 인스타그램_flag_21_30일_제작계획_20261025.xlsx (SHA256 recorded in JSON).
- New active plan: `content_plan_20261025.json`; entry point: `plan_publish.py`.
- Legacy `content_plan.json` and `daily.py` remain for rollback/API helpers, but the replaced workflow no longer runs the legacy calendar.
- One scheduled format per day: 15 real-demo Reels and 15 six-image carousels. Each axis has 10 posts.
- Target 20:00 Asia/Seoul; retries 20:20/20:40; yesterday-only recovery at 07:15 (late morning triggers accepted before 20:00). GitHub cron is not punctuality-guaranteed.
- Final planned post: 2026-11-23. Only its recovery can run 2026-11-24 morning; no newly generated post after the plan ends.
- Publication history is preserved. Date+format IDs do not collide with old numeric day keys. Retired-plan backlog is not injected into the new calendar.

## Actual-demo requirement
A Reel is **held** until `verified_media/<post-id>/manifest.json` and its actual source captures are present and reviewed. No fabricated model response, simulated app UI, unverified winner, invented performance number or silent audio fallback is allowed. The TTS narration and caption come from the reviewed manifest, not an unverified draft.

Initial packaged evidence: DAY 1 has two real ChatGPT UI captures, checked against the fictional HWPX and reconstructed image PDF. Both preserve 12, 8, 20, unit and provisional footnote; no format superiority is claimed. The PDF was not exported by Hancom. The other 14 Reel experiments are not yet recorded and will be held until their own evidence is added. `unpack_verified.py` safely restores the archive into verified_media/; readiness is listed in every run summary.

The manifest must have approved=true, evidence_type=actual_tool_capture, reviewer, verification date, tool/model, actual results, reviewed narration/caption and SHA256 for every image/video. Paths cannot escape that post folder. Capture/verification dates appear in the video. Example schema: `verified_manifest.example.json` (deliberately unapproved).

Real captures must exclude account sidebars, chat histories, personal data, secrets and internal institutional material. Only self-authored fictional public samples may be used. A single test does not establish general superiority. Model/plan/feature limits need date-stamped official verification. Unsupported HWP/HWPX or export functions must be reported honestly; do not substitute an invented success.

Missing evidence produces an explicit GitHub warning and a blocked entry in state.json, not a publication-complete record. A Telegram alert is sent only if Telegram secrets are configured. Korean free TTS failure blocks the Reel and allows safe scheduled retry. Posting is not guaranteed for a day whose evidence remains missing.

## Carousels
`plan_publish.py` renders the 6 Excel cards as 1080×1350 images. It does not create a second Reel on a carousel day. Current captions and exactly five topic-specific hashtags come from the Excel. These educational checklists do not claim that unperformed experiments were executed.

## Verification and uncertainty
Before publication, the Instagram username must equal flag_21. Media is hosted using the existing Cloudinary integration. An intent record is written immediately before media_publish; an ambiguous publish response is held for manual reconciliation, never automatically duplicated. Upload/encoding failures before this boundary are safe to retry. Preserve all historical state entries.

## Preview and tests
Manual dispatch defaults to dry_run=true. DAY 2 previews the first carousel without uploading media to Cloudinary or Instagram. A Reel preview still requires real reviewed evidence. A --day request cannot force a future or already-published item to publish.

Local validation: 38 offline unit tests passed (schedule, date/state collision, one-format selection, morning recovery, evidence hashes, traversal rejection, missing/unapproved manifests and TTS segmentation). Full CI rendering, free TTS networking and live API publication require separate runtime verification; unit tests alone do not prove posting.

## Operational checks
Use GitHub run logs and state.json media_id/date/topic, then check the actual live Instagram post. A green run can be a no-op or an explicitly held Reel. Ubuntu is pinned to 24.04; dependency preparation has bounded timeouts to avoid the observed ffmpeg setup timeout on the moving ubuntu-latest image.
