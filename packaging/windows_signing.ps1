<#
.SYNOPSIS
Lists, checks or test-signs the files that Authenticode signing covers in the Windows bundle.

.DESCRIPTION
Signing covers every .exe, .dll and .pyd in <Dist>\defineutils that is not signed already: the five commands and
lxml's modules. Python's DLLs and the Microsoft runtime come signed by their publishers and keep those signatures.

  -Action List           writes those files to <Dist>\to-sign.txt, one path per line relative to <Dist>: the
                         files-catalog that azure/artifact-signing-action signs
  -Action Check          fails unless every file in to-sign.txt now has a valid, timestamped signature
  -Action TrySelfSigned  lists the files, signs them with a throwaway self-signed certificate and fails unless each
                         now carries it. CI does this to a copy of every Windows build, so anything that stops the
                         signed executables working shows up before a release is signed

<Dist> defaults to packaging\dist. Written for Windows PowerShell 5.1 (shell: powershell in the workflow), which has
New-SelfSignedCertificate and the Authenticode cmdlets built in.
#>
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("List", "Check", "TrySelfSigned")]
    [string] $Action,
    [string] $Dist = "packaging\dist"
)

$ErrorActionPreference = "Stop"
$Dist = (Resolve-Path $Dist).Path
$Bundle = Join-Path $Dist "defineutils"
$Catalog = Join-Path $Dist "to-sign.txt"

function Write-Catalog {
    $unsigned = @(Get-ChildItem $Bundle -Recurse -File -Include *.exe, *.dll, *.pyd |
        ForEach-Object { Get-AuthenticodeSignature -FilePath $_.FullName } |
        Where-Object { $_.Status -eq "NotSigned" })
    if ($unsigned.Count -eq 0) {
        throw "found no unsigned files in $Bundle"
    }
    # relative to the catalog's folder, which is how azure/artifact-signing-action reads them
    $prefix = $Dist.TrimEnd([char[]]"\/") + [IO.Path]::DirectorySeparatorChar
    $paths = foreach ($signature in $unsigned) {
        if (-not $signature.Path.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "$($signature.Path) is not under $Dist"
        }
        $signature.Path.Substring($prefix.Length)
    }
    Set-Content -Path $Catalog -Value $paths -Encoding ASCII
    Write-Host "$($paths.Count) files to sign:"
    $paths | ForEach-Object { Write-Host "  $_" }
}

function Get-ListedSignatures {
    Get-Content $Catalog | ForEach-Object { Get-AuthenticodeSignature -FilePath (Join-Path $Dist $_) }
}

switch ($Action) {
    "List" {
        Write-Catalog
    }
    "Check" {
        $signatures = @(Get-ListedSignatures)
        $signatures | Format-Table -AutoSize Status,
            @{ Label = "Timestamped"; Expression = { $null -ne $_.TimeStamperCertificate } },
            @{ Label = "Signer"; Expression = { $_.SignerCertificate.Subject } }, Path |
            Out-String -Width 400 | Write-Host
        # the signing certificates last days, so only a timestamp keeps a signature valid after that
        $bad = @($signatures | Where-Object { $_.Status -ne "Valid" -or $null -eq $_.TimeStamperCertificate })
        if ($bad.Count -gt 0) {
            throw "$($bad.Count) of $($signatures.Count) files lack a valid, timestamped signature"
        }
    }
    "TrySelfSigned" {
        Write-Catalog
        $certificate = New-SelfSignedCertificate -Type CodeSigningCert -Subject "CN=defineutils signing test" `
            -CertStoreLocation Cert:\CurrentUser\My
        try {
            Get-Content $Catalog | ForEach-Object {
                $null = Set-AuthenticodeSignature -FilePath (Join-Path $Dist $_) -Certificate $certificate `
                    -HashAlgorithm SHA256
            }
            # Windows does not trust the throwaway certificate, so check the files carry it rather than Status
            $missed = @(Get-ListedSignatures | Where-Object {
                $null -eq $_.SignerCertificate -or $_.SignerCertificate.Thumbprint -ne $certificate.Thumbprint })
            if ($missed.Count -gt 0) {
                throw "$($missed.Count) files were not signed: $($missed.Path -join ', ')"
            }
            Write-Host "signed them with a throwaway certificate"
        }
        finally {
            Remove-Item -LiteralPath $certificate.PSPath
        }
    }
}
