[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string] $Archive,
    [Parameter(Mandatory)] [string] $Release,
    [Parameter(Mandatory)] [uri] $BuildUrl
)

$ErrorActionPreference = 'Stop'
$metadata = Get-Content -Raw -LiteralPath $Release | ConvertFrom-Json
if ($metadata.build_url.TrimEnd('/') -cne $BuildUrl.AbsoluteUri.TrimEnd('/') -or
    $BuildUrl.AbsolutePath -notmatch '/[0-9]+/?$' -or $BuildUrl.Query -or $BuildUrl.UserInfo) {
    throw 'Le manifeste de livraison ne correspond pas au numéro de build approuvé.'
}
if ($metadata.archive -cne 'securestay.oci.tar' -or
    $metadata.archive_sha256 -cnotmatch '^[0-9a-f]{64}$' -or
    $metadata.manifest_digest -cnotmatch '^sha256:[0-9a-f]{64}$' -or
    $metadata.config_digest -cnotmatch '^sha256:[0-9a-f]{64}$' -or
    $metadata.image -cne "docker.io/library/securestay@$($metadata.manifest_digest)" -or
    $metadata.platform -cne 'linux/amd64') {
    throw 'Manifeste de livraison invalide.'
}

$localArchive = (Resolve-Path -LiteralPath $Archive).Path
if ((Get-FileHash -LiteralPath $localArchive -Algorithm SHA256).Hash -ine $metadata.archive_sha256) {
    throw 'Le SHA-256 local ne correspond pas à celui du build approuvé.'
}
$node = 'desktop-control-plane'
$platform = kubectl --context docker-desktop get node $node -o 'jsonpath={.status.nodeInfo.operatingSystem}/{.status.nodeInfo.architecture}'
if ($LASTEXITCODE -ne 0 -or $platform -cne $metadata.platform) {
    throw 'La plateforme du nœud kind ne correspond pas à la livraison.'
}

$remote = "/tmp/securestay-$([guid]::NewGuid()).oci.tar"
try {
    docker cp $localArchive "${node}:$remote"
    if ($LASTEXITCODE -ne 0) { throw 'Échec du transfert vers le nœud.' }
    $checksumLine = docker exec $node sha256sum $remote
    if ($LASTEXITCODE -ne 0 -or (($checksumLine -split '\s+')[0] -cne $metadata.archive_sha256)) {
        throw 'Le SHA-256 après le transfert est incorrect.'
    }
    docker exec $node ctr --namespace k8s.io images import --digests --platform $platform $remote
    if ($LASTEXITCODE -ne 0) { throw 'Échec de l''import OCI dans containerd.' }
    $image = docker exec $node crictl inspecti $metadata.image
    if ($LASTEXITCODE -ne 0) { throw 'Le digest du manifeste est introuvable dans le CRI.' }
    $status = ($image | ConvertFrom-Json).status
    if ($status.id -cne $metadata.config_digest) {
        throw 'Le digest de configuration présent dans le CRI diffère du build.'
    }
    [pscustomobject]@{
        build_url = $metadata.build_url
        archive_sha256 = $metadata.archive_sha256
        manifest_digest = $metadata.manifest_digest
        config_digest = $metadata.config_digest
        node = $node
    } | ConvertTo-Json
} finally {
    docker exec $node rm -f -- $remote
    if ($LASTEXITCODE -ne 0) { Write-Warning 'Le fichier temporaire sur le nœud reste à retirer.' }
}
