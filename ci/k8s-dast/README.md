# Livraison SecureStay avec import OCI local

Utiliser exclusivement le namespace `securestay-dast`. La cible utilise un `emptyDir` indépendant pour SQLite, une identité non-root et les politiques réseau en refus par défaut. Le pipeline ne modifie ni le Deployment ni le PVC de `securestay`.

## Phase 1, vérifications sans déploiement

```powershell
kubectl --context docker-desktop create --dry-run=client --validate=strict -f ci/k8s-dast/bootstrap.yaml -f ci/k8s-dast/target.yaml -f ci/k8s-dast/rejected-pod.yaml -o name
git diff --check -- Jenkinsfile
```

Le Pod volontairement non conforme sert exclusivement au dry-run serveur de la phase suivante. Il est exclu de toute commande d'application. Un dry-run client vérifie la structure, pas la décision du contrôleur d'admission.

## Phase 2, après accord de mise en service

Depuis PowerShell 7 et la racine du dépôt, un opérateur autorisé prépare uniquement les ressources de test.

```powershell
kubectl --context docker-desktop apply -f ci/k8s-dast/bootstrap.yaml
kubectl --context docker-desktop apply --dry-run=server --validate=strict -f ci/k8s-dast/target.yaml
kubectl --context docker-desktop create --dry-run=server -f ci/k8s-dast/rejected-pod.yaml
kubectl --context docker-desktop apply -f ci/k8s-dast/target.yaml
```

Attendre `Forbidden` avec `allowPrivilegeEscalation != false` pour la troisième commande et conserver uniquement le verdict expurgé. Le Deployment reste à zéro réplica jusqu'au pipeline. Un opérateur fournit le Secret `securestay-dast-fixture` avec les clés `password`, `admin-password` et `flask-key` depuis le gestionnaire de secrets du projet. Le pipeline n'a aucun accès aux objets Secret.

```powershell
$identity = 'system:serviceaccount:securestay-dast:securestay-deploy'
kubectl --context docker-desktop auth can-i patch deployment/securestay -n securestay-dast --as=$identity
kubectl --context docker-desktop auth can-i create jobs -n securestay-dast --as=$identity
kubectl --context docker-desktop auth can-i get pods --subresource=log -n securestay-dast --as=$identity
kubectl --context docker-desktop auth can-i get secrets -n securestay-dast --as=$identity
kubectl --context docker-desktop auth can-i patch deployment/securestay -n securestay --as=$identity
kubectl --context docker-desktop auth can-i create clusterrolebindings --as=$identity
```

Attendre trois réponses `yes`, puis trois `no`. Réserver cette identité au job de livraison sur branche protégée. Dans le namespace de test, la création de Jobs et la modification du Deployment permettent d'exécuter des workloads, garder ce namespace dédié aux seules données de test.

### Jenkins et import

- Mettre à disposition un `kubectl` Linux AMD64 vérifié avec son checksum officiel dans `/home/jenkins/agent/.securestay-tools`. L'agent existant utilise ce répertoire de son volume, sans socket Docker et sans modification de son conteneur. Configurer `SECURESTAY_IMPORT_APPROVERS` dans Jenkins avec la liste des identifiants ou groupes habilités séparés par des virgules.
- Sur le job approuvé, activer `BUILD_IMAGE=true`, `ENFORCE_SECURITY_GATE=true`, `IMAGE_CRITICAL_POLICY=all` et `DEPLOY_DAST=true`. Indiquer le digest approuvé de l'image publique `docker.io/zaproxy/zap-stable@sha256:…`. Le réseau de l'agent vers l'API Docker Desktop doit continuer à valider la CA locale.
- Approuver la mise à disposition de l'archive dans le build. Depuis la page Jenkins authentifiée de **ce build**, télécharger **Artifacts → release → securestay.oci.tar** et **release.json**. Utiliser une URL numérotée, jamais un alias comme `lastSuccessfulBuild`. L'archive, son SHA-256, le digest du manifeste AMD64, le digest de configuration et le SHA-256 du rapport Trivy sont liés dans `release.json`.
- Importer l'archive approuvée depuis Windows. Les fichiers sont téléchargés dans le même dossier et la référence ci-dessous est l'URL exacte affichée dans Jenkins.

```powershell
$buildUrl = '<URL numérotée du build Jenkins>'
.\ci\k8s-dast\Import-ApprovedImage.ps1 -BuildUrl $buildUrl -Archive .\securestay.oci.tar -Release .\release.json
```

Au dernier point d'approbation, émettre un kubeconfig temporaire, le charger dans l'identifiant Jenkins **Secret file** `securestay-dast-kubeconfig` limité au dossier du projet, retirer la copie Windows, puis confirmer le digest **uniquement si le script d'import a réussi**. Utiliser directement le digest de manifeste qu'il affiche.

```powershell
$credentialFile = .\ci\k8s-dast\New-DastKubeconfig.ps1
# Charger le fichier dans Jenkins depuis son interface de gestion des identifiants.
Remove-Item -LiteralPath $credentialFile
```

Le script affiche uniquement le chemin local temporaire. Le jeton n'est jamais copié dans une commande Jenkins, un journal, un rapport ou Git. Retirer l'identifiant Jenkins temporaire à la fin. Chaque point d'approbation expire après 45 minutes.

### Recette de bout en bout et preuves

```powershell
kubectl --context docker-desktop -n securestay-dast get deploy,pods,svc,networkpolicy
kubectl --context docker-desktop -n securestay get deployment securestay
kubectl --context docker-desktop -n securestay get pvc securestay-sqlite
```

- **§4.3** Garder les rapports Semgrep, Gitleaks caviardés, Trivy SCA, IaC et Image, ainsi que le numéro de build et l'artefact `release/release.json`. La livraison bloque sur une CRITICAL image ou une HIGH image corrigible, selon la politique existante, et sur les résultats bloquants des autres contrôles. Vérifier également, sur un jeu synthétique sans secret réel, que le gate en échec ne produit aucun artefact de livraison.
- **§4.5** Conserver le refus PSA en dry-run, la preuve d'identité d'image du Pod (Flask et init container), puis les verdicts réseau positif, négatif et de confirmation. Le test négatif dispose aussi de la permission egress vers la cible, mais pas de la permission d'entrée.
- **§4.6** Garder dans le build les artefacts `reports/zap-passive.json` et `reports/zap-passive.html`. Le job vérifie la session de test Alice, le refus d'accès au profil d'un autre utilisateur et le rejet HTTP 400 d'un prix non fini. Les alertes High, les vérifications échouées et les scans incomplets bloquent. Les preuves avant/après sont décrites dans [evidence.md](evidence.md).

La cible revient à zéro réplica après la recette. En cas de perte de l'agent ou d'expiration de l'identifiant pendant le nettoyage, le retour à zéro doit être vérifié par l'opérateur dans `securestay-dast`.
