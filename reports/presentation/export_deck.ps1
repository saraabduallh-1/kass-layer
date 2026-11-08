# Opens the raw deck in PowerPoint, saves the final PPTX with embedded fonts, the PDF, and a PNG per slide for review.
#   export_deck.ps1 -Name kass_layer_deck            (short deck, from build_deck_short.py)
#   export_deck.ps1 -Name kass_layer_deck_detailed   (detailed deck, from build_deck.py)
param([string]$Name = "kass_layer_deck")
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$raw = Join-Path $dir "kass_layer_deck_raw.pptx"
$pptx = Join-Path $dir "$Name.pptx"
$pdf = Join-Path $dir "$Name.pdf"
$png = Join-Path $dir "preview"
Remove-Item "$png\*.png" -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $png | Out-Null
$app = New-Object -ComObject PowerPoint.Application
try {
    $p = $app.Presentations.Open($raw, $true, $false, $false)
    $p.SaveAs($pptx, 24, -1)   # ppSaveAsOpenXMLPresentation, fonts embedded
    $p.SaveAs($pdf, 32)        # ppSaveAsPDF
    $i = 1
    foreach ($s in $p.Slides) { $s.Export((Join-Path $png ("slide{0:D2}.png" -f $i)), "PNG", 1600, 900); $i++ }
    $p.Close()
} finally { $app.Quit() }
Remove-Item $raw
Write-Output "done"
