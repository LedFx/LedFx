%windir%\System32\cmd.exe "/K" C:\Users\Matt\Anaconda3\Scripts\activate.bat C:\Users\mattremote\.conda\envs\ledfx-mattallmighty" && npm run build
pause
python setup.py develop
pause
ledfx --open-ui