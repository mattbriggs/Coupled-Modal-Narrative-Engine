# Install and launch

## Fact: supported local path

The verified packaging path is an **unsigned macOS app**. It builds a React frontend, Rust Tauri shell, and PyInstaller Python sidecar. A current Python 3.11+, Node 22+ with npm, Rust 1.90+ with Cargo, and macOS Tauri prerequisites are required. The packaged app includes Python; the development app uses a local virtual environment.

## Procedure: install dependencies yourself

From the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[bundle]'
cd app
npm ci
cd ..
```

`.[bundle]` installs CMNE and PyInstaller into `.venv`. `npm ci` reads the committed `app/package-lock.json`. React and Tauri are built by the next command.

## Procedure: build and launch the packaged app

```sh
./build_app.sh --skip-install
./launch_app.sh
```

If dependencies are not installed yet, run `./build_app.sh` without the flag. It creates `.venv` if needed and installs Python and Node dependencies before building. The output is `app/src-tauri/target/release/bundle/macos/CMNE Workbench.app`. The launcher opens that bundle.

!!! note "Rebuild after changing Python code"
    `launch_app.sh` opens the most recent bundle. After changing `src/cmne/` or `src/cmne_sidecar/`, run `./build_app.sh --skip-install` again. Quit a running copy of the app before relaunching it.

## Procedure: run from source

```sh
source .venv/bin/activate
cd app
npm run tauri -- dev
```

The Tauri development command prepares a sidecar wrapper and starts Vite. Return to the repository root before using commands shown elsewhere in this manual.

## Procedure: verify the installation

```sh
source .venv/bin/activate
python -m unittest discover -s tests -v
(cd app && npm run build)
(cd app/src-tauri && cargo check)
```

The tests cover selected kernel and sidecar behavior; they are not the complete target SRS acceptance suite. See [current limits](../design/roadmap.md).

## Result

At first launch, the app creates or opens `~/Documents/CMNE/Mara and Len`. If it has already been opened, the app first tries the last project saved in browser-local state. The sample project's files stay on the local machine.
