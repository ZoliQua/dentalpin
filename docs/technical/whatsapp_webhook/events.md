---
module: whatsapp_webhook
last_verified_commit: 0000000
---

# whatsapp_webhook — events

This module **does not register event handlers and emits no events of its
own**. It is driven by the notifications gateway's outbox, which publishes
the notification lifecycle events (`notification.queued` / `.sent` /
`.failed`).
