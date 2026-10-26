<#
.SYNOPSIS
kaoyan-english-one 仓库一键同步 / 推送
.DESCRIPTION
读操作（fetch）经 ghproxy 临时重写加速，不修改全局 git 配置；
写操作（push）直连 github.com，因为 ghproxy 是只读镜像，不能写。
.PARAMETER Sync
拉取远端 main，并在本地没有独有提交时快进到最新
.PARAMETER Push
推送本地提交到 github（配合 -Message 可先自动提交）
.PARAMETER Message
自动 git add -A 并以此信息提交，随后推送
.PARAMETER MaxRetry
推送失败重试次数，默认 3
.EXAMPLE
.\sync.ps1 -Sync
.EXAMPLE
.\sync.ps1 -Push
.EXAMPLE
.\sync.ps1 -Push -Message "更新倍速说明"
#>
[CmdletBinding()]
param(
  [switch]$Sync,
  [switch]$Push,
  [string]$Message = '',
  [int]$MaxRetry = 3
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}

function Write-Step([string]$t) { Write-Host ''; Write-Host "=== $t ===" -ForegroundColor Cyan }
function Write-Ok([string]$t)   { Write-Host "  OK   $t" -ForegroundColor Green }
function Write-Note([string]$t) { Write-Host "  --   $t" -ForegroundColor Gray }
function Write-Bad([string]$t)  { Write-Host "  FAIL $t" -ForegroundColor Red }

function Invoke-Git([string[]]$GitArgs) {
  $out  = & git @GitArgs 2>&1 | Out-String
  $code = $LASTEXITCODE
  [pscustomobject]@{ Code = $code; Out = $out.Trim() }
}

$RepoRoot  = $PSScriptRoot
$ProxyExpr = 'url.https://ghproxy.net/https://github.com/.insteadOf=https://github.com/'
$Branch    = 'main'

if ($MaxRetry -lt 1) { $MaxRetry = 1 }

if (-not (Test-Path (Join-Path $RepoRoot '.git'))) {
  Write-Bad "当前目录不是 git 仓库：$RepoRoot"
  exit 1
}
Set-Location $RepoRoot

if (-not $Sync -and -not $Push) {
  Write-Host '用法：'
  Write-Host '  .\sync.ps1 -Sync                      # 拉取远端（经 ghproxy 加速）'
  Write-Host '  .\sync.ps1 -Push                      # 推送本地已有提交（直连 github）'
  Write-Host '  .\sync.ps1 -Push -Message "提交说明"   # 提交 + 推送'
  exit 0
}

$cur = (Invoke-Git @('rev-parse','--abbrev-ref','HEAD')).Out
if ($cur -ne $Branch) { Write-Note "当前分支 $cur（脚本按 $Branch 操作）" }

if ($Sync) {
  Write-Step '拉取远端（ghproxy 加速，仅本次命令生效，不改全局配置）'
  $r = Invoke-Git @('-c', $ProxyExpr, 'fetch', 'origin', $Branch, '--prune')
  if ($r.Code -ne 0) { Write-Bad "fetch 失败：$($r.Out)"; exit 1 }
  Write-Ok 'fetch 完成'

  $remoteRef = "origin/$Branch"
  $behind = [int](Invoke-Git @('rev-list','--count',"HEAD..$remoteRef")).Out
  $ahead  = [int](Invoke-Git @('rev-list','--count',"$remoteRef..HEAD")).Out
  Write-Note "落后远端 $behind 个提交，领先 $ahead 个提交"

  if ($behind -eq 0) {
    Write-Ok '本地已是最新'
  } elseif ($ahead -eq 0) {
    Write-Step '快进到远端最新'
    $m = Invoke-Git @('merge','--ff-only',$remoteRef)
    if ($m.Code -ne 0) { Write-Bad "快进失败：$($m.Out)"; exit 1 }
    Write-Ok "已快进到 $((Invoke-Git @('rev-parse','--short','HEAD')).Out)"
  } else {
    Write-Bad '本地与远端已分叉（既有落后又有领先），脚本不自动处理，请手动 merge / rebase'
  }
}

if ($Push) {
  if ($Message -ne '') {
    Write-Step '暂存并提交'
    $null = Invoke-Git @('add','-A')
    $c = Invoke-Git @('commit','-m',$Message)
    if ($c.Code -ne 0) {
      if ($c.Out -match 'nothing to commit|无文件要提交') { Write-Note '没有需要提交的改动' }
      else { Write-Bad "提交失败：$($c.Out)"; exit 1 }
    } else { Write-Ok '提交完成' }
  }

  $pending = [int](Invoke-Git @('rev-list','--count',"origin/$Branch..HEAD")).Out
  if ($pending -eq 0) { Write-Ok '没有待推送的提交，推送跳过'; exit 0 }
  Write-Note "待推送 $pending 个提交"

  Write-Step '推送到 github.com（直连）'
  $ok = $false
  for ($i = 1; $i -le $MaxRetry; $i++) {
    $p = Invoke-Git @('push','origin',$Branch)
    if ($p.Code -eq 0) { Write-Ok "推送成功（第 $i 次尝试）"; $ok = $true; break }
    $firstLines = ($p.Out -split "`n" | Where-Object { $_.Trim() -ne '' } | Select-Object -First 2) -join ' | '
    Write-Bad "第 $i 次失败：$firstLines"
    if ($i -lt $MaxRetry) { Start-Sleep -Seconds 4 }
  }

  if (-not $ok) {
    Write-Bad '推送最终失败（本机直连 github.com:443 不稳定）'
    Write-Host '     1) 打开代理后重试：.\sync.ps1 -Push'
    Write-Host '     2) 或用 gh api 走 API 通道（api.github.com 通常可达）'
    exit 1
  }
  Write-Note "本地 HEAD: $((Invoke-Git @('rev-parse','--short','HEAD')).Out)"
}
