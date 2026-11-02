# November 2 workflow reliability repair

Run 41517278142 completed its data refresh (zero failed provider updates), preserved model-data, and built the dashboard. GitHub Pages returned HTTP 500 while creating the deployment, before a deployment could be polled. This was a hosting API failure, not a failed data calculation.

The publish workflow now retries deployment once after 30 seconds, reusing the same uploaded artifact. Each deployment attempt allows three minutes of polling. A second failure still fails the workflow; the environment URL uses whichever attempt succeeded. Earlier build or data failures do not trigger a deployment retry.

The Discord publisher previously marked the feed stale even after the primary daily delivery key was present, then emitted a daily delay notice. The preflight correctly skipped rebuilding on a completed day, so those two paths disagreed. Routine stale-data notices are now logged only. No new delay message is queued, no delivery key is consumed, and stale data remains blocked from new deliveries. Existing delivery history is preserved.

Verification: offline unittest regression cases cover stale snapshots both before and after daily delivery, assert that no webhook is called, and verify that delivery keys are unchanged. No live Discord webhook is used by these checks.
