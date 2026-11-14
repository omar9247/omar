# Render public simulated demo

## No-card free demo

`FreeDemo.Dockerfile` runs the same core, verified model and MQTT broker inside one free web-service container. Only the core binds publicly; model and broker listen on loopback. Use the `free` plan, Frankfurt region, `integration/full-stack` branch and this Dockerfile. No admin token is configured, so protected writes fail closed; public safe showcases still work. This is a showcase, not durable mission hosting.

Render sleeps free services after 15 idle minutes and may take about a minute to wake. SQLite and demo changes are lost on restart, redeploy or sleep; the same four simulated crews are re-seeded. Free quotas can suspend the service/builds. Render documents no-card free hosting, but on 14 November 2026 this workspace's service-creation API rejected even the `free` plan with HTTP 402 requiring payment information. Neither the paid Blueprint nor the free service was deployed. Do not add automatic keep-alive traffic or upgrade services. See [Render free-service limits](https://render.com/docs/free).

## Persistent paid deployment

`render.yaml` keeps the existing three-service topology: public HTTPS core, private MQTT broker and private CPU model. Each service uses the 512 MB plan. The core and broker each have a 1 GB persistent disk. The base compute/storage cost is $21.50/month at the pricing checked on 14 November 2026; workspace fees and usage overages are separate. Frankfurt is the shared region. Auto-deploy and Blueprint auto-sync are disabled for deliberate releases; a Git push alone does not update the deployed app.

The core initializes an empty database from the four existing seed-12 safe showcases. All readings are simulated; no original sandbox crew data or saved games are uploaded. Seeding preserves existing crews/readings on subsequent starts and rolls back generated readings if initialization fails. The checked-in small model artifacts preserve verified model version `8d30c5cab8db`; Render does not silently retrain a different model.

`AURA_PUBLIC_DEMO=1` leaves reads and game assets public. Safe catalog showcases remain replayable with a per-scenario cooldown. Other mutations require the server-generated `AURA_ADMIN_TOKEN` as a bearer token. Retrieve that secret from the core service's Environment page, never include it in a public URL or client bundle. The existing UI does not provide an operator sign-in: ordinary visitors cannot delete crews, run arbitrary scenarios, switch the shared mission, acknowledge alerts or save check-ins/game results. Games themselves remain playable. API errors explain protected writes. The local app behaves as before when public-demo mode is not enabled.

The broker uses the existing anonymous MQTT configuration **only on Render's private network**, not a public listener. Hardware from outside Render cannot connect directly to this private demo broker. A public hardware endpoint requires a separate TLS/authenticated bridge; do not expose port 1883 publicly. The model is similarly private and called by the core through service discovery.

Single-instance disks retain SQLite state across restarts/redeploys, but disk-backed redeploys have brief downtime. This is a research-concept showcase, not a medically validated or multi-user production deployment. Traffic and CPU-intensive public replays can consume resources; monitor billing and service memory before increasing plans. Do not auto-upgrade paid plans.

Deployment planning uses the public Git repository and `integration/full-stack` branch. Keep PR #3 open unless its merge is separately authorized. Approve the actual Render Blueprint plan before creating resources. After deployment, verify HTTPS root/static assets, model-backed crew statuses, MQTT connectivity, safe replay/WebSocket updates and persistence across one redeploy.

Official references: [Blueprint specification](https://render.com/docs/blueprint-spec), [persistent disks](https://render.com/docs/disks), [pricing](https://render.com/pricing).
