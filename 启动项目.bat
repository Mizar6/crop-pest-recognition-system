@echo off
chcp 936 >nul
setlocal enabledelayedexpansion
title 农作物病虫害识别系统
set "ROOT=%~dp0"
set "BACKEND_PORT=8001"
set "FRONTEND_PORT=5176"

echo.
echo   ============================================
echo    农作物病虫害识别系统 - 一键启动
echo   ============================================
echo.

netstat -ano | findstr /r /c:":%BACKEND_PORT% .*LISTENING" >nul
if not errorlevel 1 goto backend_running
echo   [后端] 启动中...   FastAPI  :%BACKEND_PORT%
start "后端 %BACKEND_PORT%" /D "%ROOT%server" cmd /k "python -m uvicorn main:app --host 127.0.0.1 --port %BACKEND_PORT% --reload"
call :wait_ready "http://127.0.0.1:%BACKEND_PORT%/api/stats/overview" 60 后端
goto backend_done
:backend_running
echo   [后端] 已在运行  http://127.0.0.1:%BACKEND_PORT%
:backend_done

set "FEDIR="
if exist "%ROOT%web-v4" set "FEDIR=web-v4"
if not defined FEDIR if exist "%ROOT%web" set "FEDIR=web"

netstat -ano | findstr /r /c:":%FRONTEND_PORT% .*LISTENING" >nul
if not errorlevel 1 goto frontend_running
if not defined FEDIR goto no_dir
echo   [前端] 启动中...   禾鉴版  :%FRONTEND_PORT%  (%FEDIR%)
start "前端 %FRONTEND_PORT%" /D "%ROOT%%FEDIR%" cmd /k "npm run dev -- --port %FRONTEND_PORT% --strictPort"
call :wait_ready "http://127.0.0.1:%FRONTEND_PORT%/" 90 前端
goto frontend_done
:frontend_running
echo   [前端] 已在运行  http://127.0.0.1:%FRONTEND_PORT%
goto frontend_done
:no_dir
echo   [前端] 找不到目录 web-v4 或 web
:frontend_done

netstat -ano | findstr /r /c:":%FRONTEND_PORT% .*LISTENING" >nul
if errorlevel 1 goto no_browser
echo.
echo   正在打开浏览器...
start "" "http://127.0.0.1:%FRONTEND_PORT%/"
:no_browser

echo.
echo   --------------------------------------------
echo    前端页面   http://127.0.0.1:%FRONTEND_PORT%
echo    接口文档   http://127.0.0.1:%BACKEND_PORT%/docs
echo    停止服务   关闭弹出的两个服务窗口
echo   --------------------------------------------
echo.
ping -n 5 127.0.0.1 >nul
exit /b 0

:wait_ready
set "URL=%~1"
set "TRIES=%~2"
set "LABEL=%~3"
set /a _i=0
:wait_loop
curl -s -o nul --max-time 2 "%URL%" >nul 2>&1
if not errorlevel 1 goto ready_ok
set /a _i+=1
if !_i! geq %TRIES% goto ready_fail
ping -n 2 127.0.0.1 >nul
goto wait_loop
:ready_ok
echo   [%LABEL%] 就绪
exit /b 0
:ready_fail
echo   [%LABEL%] 启动超时，请查看该窗口的报错
exit /b 1
