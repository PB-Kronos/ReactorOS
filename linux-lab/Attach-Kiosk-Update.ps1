param([string]$BuildDirectory, [ValidateSet(0, 1)][int]$DvdPort = 1)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$root = Split-Path -Parent $PSScriptRoot
$vbox = Join-Path $env:ProgramFiles 'Oracle\VirtualBox\VBoxManage.exe'
$name = 'ReactorOS Kiosk Lab'
$id = [guid]::NewGuid()
$media = Join-Path $PSScriptRoot "kiosk-update-$id.viso"
$files = @('local_server.py', 'database_service.py', 'workstation_programs.py', 'workstation_access.py')
if (!$BuildDirectory) { $BuildDirectory = Join-Path $root 'rbwr/dist' }
$build = (Resolve-Path -LiteralPath $BuildDirectory).Path
if (!(Test-Path -LiteralPath (Join-Path $build 'index.html'))) { throw 'RBWR build missing.' }
$recipe = @("--iprt-iso-maker-file-marker-ms=$id", '--rock-ridge', '--joliet', '--volume-id=REACTOROS_UPDATE')
foreach ($file in $files) { $recipe += ('"/{0}={1}"' -f $file, (Join-Path $root $file)) }
$recipe += ('"/rbwr/dist={0}"' -f $build)
foreach ($file in 'kiosk.html', 'plant-tools.html', 'manage-users.py', 'update-kiosk.sh') {
    $recipe += ('"/{0}={1}"' -f $file, (Join-Path $PSScriptRoot $file))
}
[IO.File]::WriteAllLines($media, $recipe, [Text.UTF8Encoding]::new($false))
& $vbox storageattach $name --storagectl SATA --port $DvdPort --device 0 --type dvddrive --medium $media
