param(
  [Parameter(Mandatory=$true)][string]$PptxPath,
  [Parameter(Mandatory=$true)][string]$OutDir
)

$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
Get-ChildItem -Path $OutDir -Filter *.PNG | Remove-Item -Force -ErrorAction SilentlyContinue

$ppt = New-Object -ComObject PowerPoint.Application
$pres = $ppt.Presentations.Open($PptxPath, $true, $false, $false)
$prefix = Join-Path $OutDir 'slide'
$pres.Export($prefix, 'PNG')
$pres.Close()
$ppt.Quit()

$sub = Join-Path $OutDir 'slide'
if (Test-Path $sub) {
  Get-ChildItem -Path $sub -Filter *.PNG | Move-Item -Destination $OutDir -Force
  Remove-Item -Path $sub -Recurse -Force
}

$count = (Get-ChildItem -Path $OutDir -Filter *.PNG | Measure-Object).Count
Write-Output "RENDERED:$count"
