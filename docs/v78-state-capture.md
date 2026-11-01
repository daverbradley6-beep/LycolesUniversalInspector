# v78: passive multi-state recorder

Generate the Luau recorder:

```powershell
py tools/state_capture_v78.py --place-id 85896571713843 --output build/release-v78
```

Run `build/release-v78/state-recorder-v78.luau` in the Roblox client. Test hatch E, movement, inventory open/close, and equipping a tool. Capture complete `LYCOLES_V78_EVENT` lines into `events-v78.txt`. Use **Refresh** for newly created GUI controls.

Analyze:

```powershell
py tools/state_capture_v78.py --place-id 85896571713843 --event-log events-v78.txt --output build/release-v78
py -m unittest discover -s tests -p 'test_state_capture_v78.py' -v
```

The output `state-review-v78.json` contains observational hypotheses, not verified actions. Recorder tracks leaderstats, tool counts and equipped name, rounded character position, and up to 1500 ScreenGui/Frame visibility properties. Visibility is local, not ancestor-effective. No automatic gameplay execution or bypasses are provided. Python unit tests do not validate runtime Roblox behavior.
