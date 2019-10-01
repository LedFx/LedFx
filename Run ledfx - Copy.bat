%windir%\System32\cmd.exe "/K" C:\Users\Matt\Anaconda3\Scripts\activate.bat C:\Users\Matt\Anaconda3\envs\ledfx-mattallmighty" && npm run build
pause
python setup.py develop
pause
ledfx --open-ui