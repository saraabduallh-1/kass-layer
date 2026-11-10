# Converts kass_khasas_paper.html to an editable Word file and a PDF with Word (picture embedded, RTL kept).
#   powershell reports/paper/export_paper.ps1
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$html = Join-Path $dir "kass_khasas_paper.html"
$docx = Join-Path $dir "kass_khasas_paper.docx"
$pdf = Join-Path $dir "kass_khasas_paper.pdf"
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $d = $word.Documents.Open($html, $false, $true)
    foreach ($s in @($d.InlineShapes)) { if ($s.LinkFormat) { $s.LinkFormat.SavePictureWithDocument = $true; $s.LinkFormat.BreakLink() } }
    $d.SaveAs2([string]$docx, 16)     # wdFormatDocumentDefault
    $d.ExportAsFixedFormat([string]$pdf, 17)  # wdExportFormatPDF
    Write-Output ("pages " + $d.ComputeStatistics(2))
    $d.Close([ref]0)
} finally { $word.Quit([ref]0) }
Write-Output "done"
