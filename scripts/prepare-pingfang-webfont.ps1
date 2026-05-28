# 从 macOS 系统字体生成 PingFang SC webfont（需在本机已安装苹方）
#
# 用法（在 Mac 上）:
#   ./scripts/prepare-pingfang-webfont.ps1
#   或手动将 TTF/OTF 转为 woff2 后放入 public/fonts/pingfang/
#
# Windows 默认使用 npm 打包的 HarmonyOS Sans SC，无需运行此脚本。

param(
    [string]$OutputDir = "$PSScriptRoot/../web/react_frontend/public/fonts/pingfang"
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

Write-Host "苹方为 Apple 商业字体，请确认你有合法授权后再打包。" -ForegroundColor Yellow
Write-Host ""
Write-Host "推荐方式："
Write-Host "  1. 项目已默认打包 HarmonyOS Sans SC（npm install 后 build 即可）"
Write-Host "  2. 若有苹方授权，用 fonttools / cn-font-split 生成 woff2 后放入："
Write-Host "     web/react_frontend/public/fonts/pingfang/"
Write-Host "  3. 在 src/styles/fonts.css 取消 PingFang @font-face 注释"
Write-Host ""
Write-Host "HarmonyOS 官方下载："
Write-Host "  https://developer.huawei.com/consumer/cn/doc/design-guides/font-0000001828772001"
