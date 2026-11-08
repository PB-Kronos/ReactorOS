param([switch]$Kiosk)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$root = Split-Path -Parent $PSScriptRoot
$vbox = Join-Path $env:ProgramFiles 'Oracle\VirtualBox\VBoxManage.exe'
$name = if ($Kiosk) { 'ReactorOS Kiosk Lab' } else { 'ReactorOS Linux Lab' }
$iso = Join-Path $PSScriptRoot 'debian-live-13.7.0-amd64-standard.iso'
if (!(Test-Path -LiteralPath $iso -PathType Leaf)) { throw "Missing verified Debian ISO: $iso" }
if (!(Test-Path -LiteralPath (Join-Path $root 'rbwr/dist/index.html'))) { throw 'Build rbwr first.' }
if ((& $vbox list vms) -match ('^"' + [regex]::Escape($name) + '" ')) { throw "VM already exists: $name" }

$media = Join-Path $PSScriptRoot $(if ($Kiosk) { 'reactoros-kiosk-tools.viso' } else { 'reactoros-tools.viso' })
$files = @('local_server.py', 'database_service.py', 'workstation_programs.py', 'workstation_access.py', 'rbwr/dist')
$recipe = @("--iprt-iso-maker-file-marker-ms=$([guid]::NewGuid())", '--rock-ridge', '--joliet', '--volume-id=REACTOROS')
foreach ($file in $files) { $recipe += ('"/{0}={1}"' -f $file, (Join-Path $root $file)) }
$recipe += ('"/start-linux.sh={0}"' -f (Join-Path $PSScriptRoot 'start-linux.sh'))
if ($Kiosk) {
    $currentBytes = (Get-ChildItem -LiteralPath $root -Recurse -Force -File | Measure-Object Length -Sum).Sum
    if ($currentBytes + 5GB + 500MB -gt 10000000000) { throw 'Kiosk disk would exceed the 10 GB workspace cap.' }
    foreach ($file in @('provision-kiosk-vm.sh', 'kiosk-session.sh', 'kiosk.html', 'plant-tools.html', 'manage-users.py', 'reactoros.desktop', 'lightdm-reactoros.conf')) {
        $recipe += ('"/{0}={1}"' -f $file, (Join-Path $PSScriptRoot $file))
    }
}
[IO.File]::WriteAllLines($media, $recipe, [Text.UTF8Encoding]::new($false))

& $vbox createvm --name $name --ostype Debian_64 --basefolder $PSScriptRoot --register
& $vbox modifyvm $name --memory 3072 --cpus 2 --graphicscontroller vmsvga --vram 32 --nic1 nat --boot1 dvd --boot2 none --boot3 none --boot4 none
& $vbox storagectl $name --name SATA --add sata --controller IntelAhci
& $vbox storageattach $name --storagectl SATA --port 0 --device 0 --type dvddrive --medium $iso
& $vbox storageattach $name --storagectl SATA --port 1 --device 0 --type dvddrive --medium $media
if ($Kiosk) {
    $disk = Join-Path (Join-Path $PSScriptRoot $name) 'reactoros-kiosk.vdi'
    & $vbox createmedium disk --filename $disk --size 5120 --format VDI
    & $vbox storageattach $name --storagectl SATA --port 2 --device 0 --type hdd --medium $disk
}
& $vbox startvm $name --type gui
