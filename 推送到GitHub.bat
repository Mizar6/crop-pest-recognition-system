@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo  一键推送到 GitHub
echo ============================================
echo.
echo 请先在 https://github.com/new 建一个空仓库
echo （不要勾 README / gitignore / license）
echo.

set /p REPO=粘贴仓库地址（如 https://github.com/Mizar6/crop-disease-detection）: 
if "%REPO%"=="" (
  echo 地址不能为空
  pause
  exit /b 1
)

set /p TOKEN=粘贴 Personal Access Token（输入时看不见，粘贴后回车）: 
if "%TOKEN%"=="" (
  echo Token 不能为空
  pause
  exit /b 1
)

REM 把 token 塞进远程地址（只在本机这一条命令里用，不落盘到仓库配置）
set REMOTE=https://x-access-token:%TOKEN%@github.com/%REPO:~19%

echo.
echo 正在推送，144MB 左右，请耐心等…
git remote remove origin >nul 2>&1
git remote add origin %REMOTE%
git push -u origin HEAD:main
if errorlevel 1 (
  echo.
  echo 推送失败：检查仓库地址、Token 权限（需要 repo）、网络
  pause
  exit /b 1
)

REM 推完把远程地址里的 token 抹掉，避免明文留在配置里
git remote set-url origin %REPO%

echo.
echo ============================================
echo  推送成功
echo  仓库：%REPO%
echo  记得去 GitHub 删掉这个 Token
echo ============================================
pause
