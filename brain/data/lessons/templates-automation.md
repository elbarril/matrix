# Lecciones — templates-automation

Lecciones específicas del proyecto de test automation de portales PAS. Se cargan cuando la sesión
se resuelve a `templates-automation`. El detalle de investigación completo vive en
`brain/output/templates-automation/research/README.md` (mapa maestro) y subcarpetas.

1. **El conocimiento del framework no está en wiki.xcade.net (deprecado) — está en el wiki de GitLab del repo `frontier-templates`** (https://gitlab.xcade.net/Portal-Templates-Automation/frontier-templates/-/wikis/home). Las páginas canónicas (sin prefijo `(update)`) tienen el contenido real; las `(update)X` son stubs. Mirror local extraído en `brain/output/templates-automation/research/frontier-wiki/`. La página wiki.xcade "Frontier" y "Automation with frontier" están deprecadas.

2. **PAS = Portal App Services** (división de Professional Services). Los skills `-pas` del repo (`.agents/skills/`) son deltas específicos de portales sobre los skills generales Frontier — leer SIEMPRE el índice `.agents/skills/SKILL.md` y `.devin/rules/frontier-skills.md` antes de trabajar. Los skills generales están en el venv/aiad-common y se heredan.

3. **Regla de oro de navegación en features:** `user reaches X page by clicking Y element` para flujos; `navigates` solo en carga inicial (Given). Elementos interactivos van en `locators`, no en `validation` (website.yaml). Es la causa #1 de tests rotos.

4. **Datos mocked: solo los tipos exactos** `mocked:name|email|phone number|street|city|post code|company|job|password|text|date`. `mocked:first_name`, `mocked:last_name`, `mocked:phone`, `mocked:address` NO existen — rompen el test con DataNotFoundError.

5. **Data isolation entre portales de una misma instancia:** en ejecución a nivel instancia los portales corren secuencialmente sin cleanup — aplicar sufijo de portal a usuarios/emails/recruiters (`testhm` → `testhm_careers`). Severidad CRITICAL para username/Primary Recruiter/job title con dedup-by-fullname. Pre-commit: `.pre-commit/check_data_isolation.py`.

6. **Backend IATS de las herramientas de instancia:** el módulo `portaltemplates` fue deprecado (2026-01-14); los helpers (`EditPortalsSettings.php`, `PullPortal.php`, `EditCustomPortal.php`, `ValidatePortalZip.php`) viven en `module/portal/tool/PortalTemplates/`. Comandos vía `sudo -u www-data iats portalTemplates` (createAutomationUser, pullPortal, importCsv, ...) — wiki: `brain/output/.../wiki-xcade/templates-automation-tools-guide.md`.

7. **El case-template 829832 del workflow "Failed automation test execution" (wiki) da 404 en TEG** (2026-08-27) — verificar el template real antes de clonar para reportar un test fallido. El workflow es el 52124 con pasos "Failed test ...".

8. **Help (help.avature.net) no cubre el framework interno de testing** — es documentación de producto para clientes. Sirve para entender features de portales que se testean, no el framework.

9. **Secretos del repo:** `local_config.yaml` guarda credenciales QA como base64 (`***OBFUSCATED***`) — base64 no es cifrado. Nunca pegar valores obfuscados en chat/logs/commits/MR; referirse por field path (`ava_password`); nunca commitear `local_config.yaml`.

10. **Ejecución remota vía ETT:** `frontier_templates --remote --create --run_id ...`; logs en Kibana; API `https://ett.xcade.net/api/runs` (detalle en `frontier-wiki/tests-execution.md`). Útil para regresiones sin correr local.

11. **Cookies-steps del framework es mínima** (1 step: `user accepts cookies if prompted`); el consentimiento a nivel portal se gestiona con Portal-Steps (enable/disable + verificación). Para tests de portales con cookie consent usar el patrón del delta `write-test-pas`.
