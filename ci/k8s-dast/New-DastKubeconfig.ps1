[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$server = [uri](kubectl --context docker-desktop config view --minify -o 'jsonpath={.clusters[0].cluster.server}')
if ($LASTEXITCODE -ne 0 -or $server.Scheme -ne 'https' -or $server.Host -ne '127.0.0.1') {
    throw 'Le point d''accès Docker Desktop attendu a changé.'
}
$ca = kubectl --context docker-desktop config view --raw --flatten --minify -o 'jsonpath={.clusters[0].cluster.certificate-authority-data}'
if ($LASTEXITCODE -ne 0 -or -not $ca) { throw 'CA publique indisponible.' }
$token = kubectl --context docker-desktop -n securestay-dast create token securestay-deploy --duration=45m
if ($LASTEXITCODE -ne 0 -or -not $token) { throw 'La demande de jeton temporaire a échoué.' }

try {
    $config = @{
        apiVersion = 'v1'
        kind = 'Config'
        clusters = @(@{
            name = 'docker-desktop-dast'
            cluster = @{
                server = "https://host.docker.internal:$($server.Port)"
                'tls-server-name' = $server.Host
                'certificate-authority-data' = $ca
            }
        })
        users = @(@{ name = 'securestay-deploy'; user = @{ token = $token } })
        contexts = @(@{
            name = 'securestay-dast'
            context = @{ cluster = 'docker-desktop-dast'; user = 'securestay-deploy'; namespace = 'securestay-dast' }
        })
        'current-context' = 'securestay-dast'
    }
    $file = Join-Path ([IO.Path]::GetTempPath()) ("securestay-dast-" + [guid]::NewGuid() + ".json")
    $config | ConvertTo-Json -Depth 10 | Set-Content -Encoding utf8 -LiteralPath $file
    $file
} finally {
    Remove-Variable token
    Remove-Variable config -ErrorAction SilentlyContinue
}
