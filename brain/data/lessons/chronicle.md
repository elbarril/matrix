# lessons/chronicle.md — scoped lessons for Chronicle

These load only when a session binds to the Chronicle project. Append-only.

---

## Lessons

1. **IndexedDB (Dexie) schema changes require a version bump.** Changing field names or adding indexes without incrementing the Dexie db version silently fails on returning users. Always bump `db.version(N+1).stores(...)` when the schema changes.

2. **PWA service worker caching can mask broken builds.** After a deploy, the old SW may serve stale assets. Always increment the SW cache version string and verify with a hard refresh or `Update on reload` in DevTools.
