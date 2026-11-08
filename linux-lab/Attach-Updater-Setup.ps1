param([Parameter(Mandatory)][string]$PublicKey)
$ErrorActionPreference = 'Stop'
$vbox = Join-Path $env:ProgramFiles 'Oracle\VirtualBox\VBoxManage.exe'
$name = 'ReactorOS Kiosk Lab'
$key = (Resolve-Path -LiteralPath $PublicKey).Path
if ((Get-Content -LiteralPath $key -TotalCount 1) -cne '-----BEGIN PUBLIC KEY-----') {
    throw 'Supply the release public key PEM.'
}
$id = [guid]::NewGuid()
$media = Join-Path $PSScriptRoot "updater-setup-$id.viso"
$recipe = @("--iprt-iso-maker-file-marker-ms=$id", '--rock-ridge', '--joliet', '--volume-id=REACTOROS_UPDATER')
$recipe += ('"/update-public.pem={0}"' -f $key)
foreach ($file in 'install-updater.sh', 'reactoros-update.sh') {
    $recipe += ('"/{0}={1}"' -f $file, (Join-Path $PSScriptRoot $file))
}
[IO.File]::WriteAllLines($media, $recipe, [Text.UTF8Encoding]::new($false))
& $vbox storageattach $name --storagectl SATA --port 1 --device 0 --type dvddrive --medium $media
if ($LASTEXITCODE -ne 0) { throw 'VirtualBox could not attach the setup disc.' }
Write-Output $media
