# kass_ksaa_paper.html → Word + PDF in the academy's identity: picture embedded, running header from page 2, page numbers.
#   powershell reports/paper/export_ksaa.ps1
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$html = Join-Path $dir "kass_ksaa_paper.html"
$docx = Join-Path $dir "kass_ksaa_paper.docx"
$pdf = Join-Path $dir "kass_ksaa_paper.pdf"
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $d = $word.Documents.Open($html, $false, $true)
    foreach ($s in @($d.InlineShapes)) { if ($s.LinkFormat) { $s.LinkFormat.SavePictureWithDocument = $true; $s.LinkFormat.BreakLink() } }
    $d.SaveAs2([string]$docx, 16)
    $d.Close([ref]0)
    $d = $word.Documents.Open([string]$docx)
    $d.ActiveWindow.View.Type = 3
    $green = 0x548A1B   # #1b8354 as BGR
    $sec = $d.Sections.Item(1)
    $d.PageSetup.DifferentFirstPageHeaderFooter = -1
    $h = $sec.Headers.Item(1).Range
    $h.Text = "مجمع الملك سلمان العالمي للغة العربية  ·  خصص: طبقة مصطلحية عربية"
    $h.Font.Name = "IBM Plex Sans Arabic"; $h.Font.Size = 8.5; $h.Font.Color = $green
    $h.ParagraphFormat.Alignment = 2; $h.ParagraphFormat.ReadingOrder = 0
    $h.ParagraphFormat.Borders.Item(-3).LineStyle = 1; $h.ParagraphFormat.Borders.Item(-3).Color = 0x6FB2D2   # gold rule under it
    foreach ($k in 1, 2) {
        $f = $sec.Footers.Item($k)
        $f.Range.Text = ""
        $f.Range.Fields.Add($f.Range, 33) | Out-Null   # wdFieldPage
        $f.Range.ParagraphFormat.Alignment = 1
        $f.Range.Font.Name = "IBM Plex Sans Arabic"; $f.Range.Font.Size = 9; $f.Range.Font.Color = $green
    }
    $d.Save()
    $d.ExportAsFixedFormat([string]$pdf, 17)
    Write-Output ("pages " + $d.ComputeStatistics(2))
    $d.Close([ref]0)
} finally { $word.Quit([ref]0) }
Write-Output "done"
