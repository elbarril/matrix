# lessons/artista-ia.md — template

Scoped lessons for `artista-ia`. These load only when a session binds to this project. Append new lessons at the bottom; never delete or reorder — append-only.

Routing: if a lesson applies to ALL projects, it goes in the core pool (`brain/data/lessons.md`), not here.

---

## Lessons

<!-- Append new lessons below this line -->

- **Siempre trabajar en un branch nuevo, nunca commitear directo a `master`.** El repo está diseñado para dev → staging/branch → PR → prod (evidencia: `git log` muestra merges de `staging` y de `feature/xanaeli-upgrades-...` hacia `master`). Regla explícita del usuario (2026-08-27): "es importante que trabajes en nuevos branches con este proyecto como esta diseñado, asi se arregla y se prueba en dev y luego vamos a prod cuando estamos seguros... por mas que no te lo diga". Aplica siempre, sin necesidad de que el usuario lo repita cada vez — antes de la primera edición de una tarea nueva en este repo, crear `git checkout -b <tipo>/<slug-descriptivo>` desde `master` actualizado, commitear ahí, y dejar el merge/PR a `master` (y el push a prod) como paso explícito a confirmar con el usuario, no automático. Excepción ya aceptada una vez por el usuario mismo (no repetible sin pedirla de nuevo): el fix de cron-life/cron-summary del 2026-08-27 se commiteó directo a `master` porque ya estaba hecho para cuando se dio la regla.
