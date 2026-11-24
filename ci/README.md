# Jenkins SecureStay

BuildKit fonctionne dans un conteneur rootless dédié sur Docker Desktop. Il ne publie aucun port et ne monte aucun socket Docker. L’agent Jenkins existant utilise un socket Unix BuildKit et un client `buildctl`, partagés dans un sous-répertoire privé de son volume. Le constructeur garde son espace de processus propre. Réserver cet accès aux jobs SecureStay qui construisent du code approuvé.

## Démarrage depuis PowerShell, à la racine du dépôt

```powershell
docker exec securestay-agent install -d -m 0700 /home/jenkins/agent/.securestay-buildkit
docker compose -p securestay-buildkit -f ci/compose.buildkit.yml config --quiet
docker compose -p securestay-buildkit -f ci/compose.buildkit.yml up -d
docker compose -p securestay-buildkit -f ci/compose.buildkit.yml exec -T buildkit sh -ec 'cp /usr/bin/buildctl /shared/buildctl.new; chmod 0700 /shared/buildctl.new; mv /shared/buildctl.new /shared/buildctl'
docker exec securestay-agent /home/jenkins/agent/.securestay-buildkit/buildctl --addr unix:///home/jenkins/agent/.securestay-buildkit/buildkitd.sock debug workers
```

La dernière commande doit afficher un worker avant de lancer Jenkins avec `BUILD_IMAGE=true`. Publier le Jenkinsfile et `ci/trivy_image_policy.py` sur la branche GitHub suivie par Jenkins, puis lancer le job depuis **Build with Parameters**. `BUILD_IMAGE` reste désactivé par défaut. Faire un premier lancement avec `ENFORCE_SECURITY_GATE=false`, puis l’activer pour appliquer le blocage. Le job construit le commit Git déjà extrait par Jenkins et laisse l’image sous forme d’archive temporaire pour Trivy.

Dans **Artifacts**, vérifier `reports/trivy-image.json` (toutes les HIGH et CRITICAL) et `reports/trivy-image-fixable.json` (sous-ensemble dont `FixedVersion` est renseigné). Le rapport complet est archivé même si le gate bloque. Le gate image bloque les HIGH corrigibles et applique `IMAGE_CRITICAL_POLICY` aux CRITICAL : `all` pour toutes, `fixable` pour celles avec correctif, `off` pour aucune. Les règles SAST, Gitleaks, SCA et IaC existantes restent actives lorsque le gate est activé.

## Politique de sécurité IaC — fixtures de rejet PSA

Le Security Gate bloque toute alerte IaC HIGH ou CRITICAL sur les fichiers Kubernetes et Docker du dépôt. La seule exception de périmètre concerne les deux fichiers suivants.

- `ci/k8s-dast/rejected-pod.yaml`
- `k8s/tests/rejected-pod.yaml`

Ces Pods activent volontairement l'élévation de privilèges pour vérifier que Pod Security Admission les refuse. Le scan Trivy IaC exclut ces deux chemins exacts. La règle KSV-0014 et toutes les autres règles restent actives sur le reste du dépôt.

Le contrôle `ci/check_psa_fixtures.py` s'exécute avant le scan. Il bloque si un point d'entrée applicable de SecureStay référence l'une des fixtures ou reprend l'identité de son Pod. Exécuter les fixtures uniquement avec `kubectl create --dry-run=server`. Cette exception vaut tant que les deux fichiers servent à ce test de rejet. La retirer si les fixtures disparaissent ou changent de rôle.
