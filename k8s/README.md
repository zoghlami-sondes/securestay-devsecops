# Déployer SecureStay sur Docker Desktop

Exécuter les commandes PowerShell 7 depuis la racine du dépôt. Elles ciblent le contexte `docker-desktop` et le namespace `securestay`.

## Vérifier avant d’appliquer

```powershell
kubectl --context docker-desktop get nodes
kubectl --context docker-desktop get namespace securestay --show-labels
kubectl --context docker-desktop apply --dry-run=server --validate=strict -k k8s
```

Le namespace est déjà présent sur ce cluster. Sur un cluster équivalent où il manque, valider `namespace.yaml` avec `--dry-run=server`, puis appliquer ce seul fichier avant de valider les ressources du namespace.

Pour vérifier l’admission des deux Pods sans en créer un seul, exécuter ces commandes. La première requête de création doit réussir et la seconde doit renvoyer `Forbidden` avec `allowPrivilegeEscalation != false`.

```powershell
$deployment = kubectl --context docker-desktop -n securestay apply --dry-run=server -f k8s/deployment.yaml -o json | ConvertFrom-Json
@{
    apiVersion = 'v1'
    kind = 'Pod'
    metadata = @{ name = 'securestay-psa-positive'; namespace = 'securestay' }
    spec = $deployment.spec.template.spec
} | ConvertTo-Json -Depth 40 | kubectl --context docker-desktop create --dry-run=server -f -

kubectl --context docker-desktop create --dry-run=server -f k8s/tests/rejected-pod.yaml
```

## Construire et charger l’image locale

Le manifeste utilise `imagePullPolicy: Never` pour que le nœud exécute l’image locale importée. Dans Docker Desktop, activer l’affichage **Show system containers (advanced)** si `docker inspect desktop-control-plane` ne trouve pas le nœud. Cette option rend le nœud visible aux commandes Docker. [Paramètres Docker Desktop](https://docs.docker.com/desktop/settings-and-maintenance/settings/#kubernetes)

```powershell
docker inspect desktop-control-plane --format '{{.Name}}'
if ($LASTEXITCODE -ne 0) { throw 'Le conteneur du nœud kind doit être visible.' }

docker build --provenance=false -t securestay:k8s-local .
if ($LASTEXITCODE -ne 0) { throw 'Échec de la construction de l’image.' }

$imageArchive = Join-Path ([IO.Path]::GetTempPath()) ("securestay-" + [guid]::NewGuid() + ".tar")
$nodeArchive = "/tmp/" + (Split-Path -Leaf $imageArchive)
try {
    docker image save -o $imageArchive securestay:k8s-local
    if ($LASTEXITCODE -ne 0) { throw 'Échec de l’export de l’image.' }
    docker cp $imageArchive "desktop-control-plane:${nodeArchive}"
    if ($LASTEXITCODE -ne 0) { throw 'Échec du transfert vers le nœud.' }
    docker exec desktop-control-plane ctr --namespace k8s.io images import $nodeArchive
    if ($LASTEXITCODE -ne 0) { throw 'Échec de l’import dans containerd.' }
} finally {
    docker exec desktop-control-plane rm -f $nodeArchive
    if (Test-Path -LiteralPath $imageArchive) { Remove-Item -LiteralPath $imageArchive }
}
docker exec desktop-control-plane crictl inspecti docker.io/library/securestay:k8s-local
```

## Fournir le Secret et appliquer

Créer le Secret une fois. Le mot de passe saisi et la clé Flask générée en mémoire sont transmis par l’entrée standard de `kubectl`. Le mot de passe administrateur sert à initialiser une base neuve. Les données et comptes existants restent sur le PVC lors des redémarrages.

```powershell
$admin = Read-Host -MaskInput 'Mot de passe initial de l’administrateur'
if ([string]::IsNullOrWhiteSpace($admin)) { throw 'Saisir un mot de passe non vide.' }
try {
    @{
        apiVersion = 'v1'
        kind = 'Secret'
        metadata = @{ name = 'securestay-credentials'; namespace = 'securestay' }
        type = 'Opaque'
        stringData = @{
            ADMIN_PASSWORD = $admin
            SECRET_KEY = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
        }
    } | ConvertTo-Json -Depth 5 | kubectl --context docker-desktop create -f -
    if ($LASTEXITCODE -ne 0) { throw 'La création du Secret a échoué.' }
} finally {
    Remove-Variable admin
}
```

Aux déploiements suivants, réutiliser le Secret et le PVC existants.

```powershell
kubectl --context docker-desktop apply -k k8s
kubectl --context docker-desktop -n securestay rollout status deployment/securestay --timeout=180s
kubectl --context docker-desktop -n securestay get pods
kubectl --context docker-desktop -n securestay get svc
kubectl --context docker-desktop -n securestay get pvc,networkpolicy
kubectl --context docker-desktop -n securestay exec deploy/securestay -- id
kubectl --context docker-desktop -n securestay exec deploy/securestay -- python -c 'import sqlite3; print(sqlite3.connect("file:/app/data/lab.db?mode=ro", uri=True).execute("PRAGMA integrity_check").fetchone()[0])'
```

Le Pod doit être `1/1 Ready`, le PVC `Bound`, le processus sous UID/GID `10001:10001` et le contrôle SQLite doit imprimer `ok`. Le PVC Kubernetes est indépendant du volume Docker Compose. Les fichiers de journal sont sur un `emptyDir` et durent autant que le Pod.

## Vérifier l’accès et la persistance

Dans un terminal, lancer le port-forward sur un port distinct de celui de Docker Compose.

```powershell
kubectl --context docker-desktop -n securestay port-forward --address 127.0.0.1 service/securestay 18080:8080
```

Dans un autre terminal, vérifier la réponse HTTP.

```powershell
(Invoke-WebRequest -Uri 'http://127.0.0.1:18080/' -TimeoutSec 10).StatusCode
```

Les politiques réseau autorisent uniquement TCP/8080 depuis les Pods du namespace portant `securestay.io/http-client=true`. Flask n’a besoin ni d’accès sortant ni de DNS. Le port-forward passe par l’API Kubernetes et teste HTTP indépendamment du filtrage entre Pods. [Documentation NetworkPolicy](https://kubernetes.io/docs/concepts/services-networking/network-policies/)

Le test suivant écrit un fichier temporaire sur le PVC Kubernetes, recrée le Pod, vérifie le fichier puis le retire. Arrêter le port-forward avant de recréer le Pod.

```powershell
$marker = kubectl --context docker-desktop -n securestay exec deploy/securestay -- mktemp /app/data/.pvc-check.XXXXXX
if ($LASTEXITCODE -ne 0 -or $marker -notmatch '^/app/data/\.pvc-check\.[A-Za-z0-9]{6}$') { throw 'Impossible de créer le marqueur.' }
kubectl --context docker-desktop -n securestay rollout restart deployment/securestay
kubectl --context docker-desktop -n securestay rollout status deployment/securestay --timeout=180s
if ($LASTEXITCODE -ne 0) { throw 'Le Pod de remplacement ne répond pas.' }
kubectl --context docker-desktop -n securestay exec deploy/securestay -- test -f $marker
if ($LASTEXITCODE -ne 0) { throw 'Marqueur introuvable après le redémarrage.' }
kubectl --context docker-desktop -n securestay exec deploy/securestay -- rm -- $marker
```
