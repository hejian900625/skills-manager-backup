# README

## Installation

Git clone this project by running in terminal:

```
git clone https://github.com/Fanisting/orders-scraper.git
```

Set up a virtual env with `python venv`. Run this in terminal:

```
python -m venv env
```

It creates the `venv` with name = env. Please **activate the env in terminal**.

Now install pre-requisites:

```powershell
pip install playwright pyqt5 pyqt5-tools bs4 logging pyinstaller
```

Here we should set up more in playwright, run this in terminal:

```
python -m playwright install
```

## Make your own app with Pyinstaller

After activate `venv` in terminal, run command to compile the app/exe in terminal.

### Windows

```powershell
# powershell
$env:PLAYWRIGHT_BROWSERS_PATH="0" 
playwright install chromium
pyinstaller -n choose -F --windowed choose.py
```

### Mac OS

```bash
PLAYWRIGHT_BROWSERS_PATH=0 playwright install chromium
pyinstaller -n choose -F --windowed choose.py
```

You will find the compiled app in `dist/` folder, try to run it.


## Output

Once you run the app and choose a platform, you will find a `.html/.txt` file in local folder.
