# SecureStay · Observabilité et réponse à incident (§4.7)

Les événements JSON sont écrits dans `access.log`, `auth.log` et `app.log`. L'en-tête de réponse `X-Correlation-ID` est généré côté serveur et relie l'événement de sécurité à la trace d'accès. La route journalisée est un modèle Flask, par exemple `/profile/<int:user_id>`. Les identifiants de compte et les entrées HTTP brutes ne sont pas journalisés.

| Signal | Journal | Réponse |
| --- | --- | --- |
| `PRICE_NAN_REJECTED` | `app.log` | HTTP 400 |
| `PRICE_NONFINITE_REJECTED` | `app.log` | HTTP 400 |
| `PROFILE_ACCESS_DENIED` | `auth.log` | HTTP 403 |
| `ADMIN_ACCESS_DENIED` | `app.log` | HTTP 403 |
| `LOGIN_FAILURE` | `auth.log` | Résultat de connexion refusée |

Pour ces événements, `event_count` est un compteur croissant par type d'événement et par processus Flask. Il repart à zéro au redémarrage. Une valeur isolée indique un refus, sans attribuer d'intention à son auteur. Pour comparer plusieurs processus ou redémarrages, compter les événements sur une fenêtre UTC dans les journaux disponibles.

## Démonstration locale sans Kubernetes

Depuis la racine du dépôt, dans PowerShell, utiliser une instance jetable isolée du réseau. Le conteneur n'utilise aucun montage SQLite. Les journaux vont dans un dossier temporaire dédié.

```powershell
$evidenceDir = Join-Path ([IO.Path]::GetTempPath()) ("securestay-47-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $evidenceDir | Out-Null
docker build -t securestay:observability-test .
docker run --rm -d --name securestay-observability-test --network none --mount "type=bind,source=$evidenceDir,target=/app/logs" securestay:observability-test
```

Lorsque `docker inspect securestay-observability-test --format '{{.State.Health.Status}}'` indique `healthy`, exécuter deux contrôles de rejet et conserver la sortie.

```powershell
Get-Content -Raw ci/verify_security_telemetry.py | docker exec -i securestay-observability-test python - --port 8080 --log-dir /app/logs | Tee-Object -FilePath (Join-Path $evidenceDir 'evidence.ndjson')
Get-Content -Raw ci/verify_security_telemetry.py | docker exec -i securestay-observability-test python - --port 8080 --log-dir /app/logs | Tee-Object -FilePath (Join-Path $evidenceDir 'evidence.ndjson') -Append
docker stop securestay-observability-test
```

Le script exige HTTP 400, un identifiant de corrélation et les deux événements correspondants dans les journaux. À la soutenance, montrer les deux identifiants distincts, le compteur qui augmente et le résultat `HTTP_REQUEST` associé. Pour un contrôle IDOR, les tests Flask vérifient le même lien après un accès à un profil refusé.

## Plan de réponse à incident

| Étape | Action et preuve à conserver |
| --- | --- |
| Détection | Ouvrir une fiche avec l'heure UTC, l'événement, le statut et le `correlation_id`. Retrouver la trace d'accès de même identifiant. Vérifier s'il s'agit d'un refus isolé, d'une répétition ou d'un signal accompagné d'un accès non autorisé. |
| Confinement | Pour la démonstration, arrêter l'instance jetable après collecte. Pour un incident hors démonstration, demander au responsable d'isoler la seule exposition affectée ou de limiter le trafic sur la route concernée. Préserver les journaux et SQLite. |
| Éradication | Examiner le contrôle de validation ou d'autorisation et le commit déployé. Corriger la cause identifiée et lancer les tests de régression et le Security Gate. Révoquer les identifiants concernés si une exposition est confirmée. |
| Rétablissement | Repartir de l'image approuvée, vérifier une requête nominale et le rejet attendu, puis confirmer la présence des traces corrélées. Rétablir l'accès normal après validation du responsable. |
| Retour d'expérience | Archiver la chronologie, les verdicts expurgés, le commit ou le build et les décisions prises. Consigner la cause, les améliorations retenues et leur suivi. |
