#!/usr/bin/env python3
"""Offline runtime-contract harness for generated Lycoles utility scripts.

This harness does not claim Roblox runtime verification. It validates behavioral
contracts offline using mocked player/character/tool state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


CATEGORY_BUTTONS = ("Overview", "Loadout", "Movement", "Settings", "Diagnostics")
LOADOUT_REFRESH_OPTIONS = (0.1, 0.2, 0.5, 1.0)
MOVEMENT_REFRESH_OPTIONS = (0.1, 0.2, 0.5, 1.0)
LOADOUT_KEYBINDS = ("RightShift", "RightAlt", "LeftShift", "LeftAlt")
MOVEMENT_KEYBINDS = ("RightControl", "LeftControl", "Z", "X")


@dataclass
class MockTool:
    name: str


@dataclass
class MockContainer:
    tools: list[MockTool] = field(default_factory=list)


@dataclass
class MockHumanoid:
    walk_speed: float = 16.0
    floor_material: str = "Concrete"
    state_name: str = "Running"


@dataclass
class MockRootPart:
    velocity_magnitude: float = 0.0


@dataclass
class MockCharacter:
    tools: list[MockTool] = field(default_factory=list)
    humanoid: Optional[MockHumanoid] = None
    root_part: Optional[MockRootPart] = None


@dataclass
class MockPlayer:
    character: Optional[MockCharacter] = None
    backpack: MockContainer = field(default_factory=MockContainer)
    hud_indicators: dict[str, str] = field(default_factory=dict)


@dataclass
class ModuleState:
    enabled: bool = False
    refresh_seconds: float = 0.2
    keybind: str = ""
    change_count: int = 0
    _last_hash: str = ""


class RuntimeContractHarness:
    def __init__(self, module_contract: dict[str, Any]) -> None:
        modules = module_contract.get("modules") if isinstance(module_contract, dict) else {}
        loadout_default = (modules.get("loadout") or {}).get("defaultKeybind", "RightShift")
        movement_default = (modules.get("movement") or {}).get("defaultKeybind", "RightControl")

        self.loadout = ModuleState(keybind=str(loadout_default))
        self.movement = ModuleState(keybind=str(movement_default))
        self.connection_count = 0
        self.theme_index = 0

    @staticmethod
    def validate_gui_structure(script_source: str) -> dict[str, bool]:
        if not isinstance(script_source, str):
            raise ValueError("script source must be text")
        return {name: f'button("{name}"' in script_source for name in CATEGORY_BUTTONS}

    @staticmethod
    def _cycle_value(options: tuple[Any, ...], value: Any) -> Any:
        try:
            index = options.index(value)
        except ValueError:
            return options[0]
        return options[(index + 1) % len(options)]

    @staticmethod
    def _tool_names(tools: list[MockTool]) -> list[str]:
        return sorted(item.name for item in tools)

    def _loadout_snapshot_hash(self, player: MockPlayer) -> str:
        equipped = self._tool_names(player.character.tools) if player.character else []
        backpack = self._tool_names(player.backpack.tools)
        hud = sorted(f"{key}:{value}" for key, value in player.hud_indicators.items())
        return "|".join(equipped) + "::" + "|".join(backpack) + "::" + "|".join(hud)

    def _movement_snapshot_hash(self, player: MockPlayer) -> str:
        if not player.character or not player.character.humanoid or not player.character.root_part:
            return "missing-runtime"
        humanoid = player.character.humanoid
        speed = float(player.character.root_part.velocity_magnitude)
        move_state = "moving" if speed > 0.5 else "idle"
        altitude = "grounded" if humanoid.floor_material != "Air" else "airborne"
        return f"{move_state}::{altitude}::{humanoid.state_name}::{speed:.2f}"

    def toggle_loadout(self, player: MockPlayer) -> dict[str, Any]:
        if not self.loadout.enabled:
            self.connection_count += 1
        self.loadout.enabled = not self.loadout.enabled
        snapshot_hash = self._loadout_snapshot_hash(player)
        if snapshot_hash != self.loadout._last_hash:
            self.loadout.change_count += 1
            self.loadout._last_hash = snapshot_hash
        return {
            "enabled": self.loadout.enabled,
            "changeCount": self.loadout.change_count,
            "refreshSeconds": self.loadout.refresh_seconds,
            "keybind": self.loadout.keybind,
        }

    def toggle_movement(self, player: MockPlayer) -> dict[str, Any]:
        if not self.movement.enabled:
            self.connection_count += 1
        self.movement.enabled = not self.movement.enabled
        snapshot_hash = self._movement_snapshot_hash(player)
        if snapshot_hash != self.movement._last_hash:
            self.movement.change_count += 1
            self.movement._last_hash = snapshot_hash
        return {
            "enabled": self.movement.enabled,
            "changeCount": self.movement.change_count,
            "refreshSeconds": self.movement.refresh_seconds,
            "keybind": self.movement.keybind,
        }

    def apply_settings_cycle(self) -> dict[str, Any]:
        self.loadout.refresh_seconds = self._cycle_value(LOADOUT_REFRESH_OPTIONS, self.loadout.refresh_seconds)
        self.movement.refresh_seconds = self._cycle_value(MOVEMENT_REFRESH_OPTIONS, self.movement.refresh_seconds)
        self.loadout.keybind = self._cycle_value(LOADOUT_KEYBINDS, self.loadout.keybind)
        self.movement.keybind = self._cycle_value(MOVEMENT_KEYBINDS, self.movement.keybind)
        self.theme_index = (self.theme_index + 1) % 4
        return {
            "loadoutRefresh": self.loadout.refresh_seconds,
            "movementRefresh": self.movement.refresh_seconds,
            "loadoutKeybind": self.loadout.keybind,
            "movementKeybind": self.movement.keybind,
            "themeIndex": self.theme_index,
        }

    def handle_respawn(self, player: MockPlayer, new_character: Optional[MockCharacter]) -> dict[str, Any]:
        player.character = new_character
        loadout_hash = self._loadout_snapshot_hash(player)
        movement_hash = self._movement_snapshot_hash(player)
        if self.loadout.enabled and loadout_hash != self.loadout._last_hash:
            self.loadout.change_count += 1
            self.loadout._last_hash = loadout_hash
        if self.movement.enabled and movement_hash != self.movement._last_hash:
            self.movement.change_count += 1
            self.movement._last_hash = movement_hash
        return {
            "loadoutChangeCount": self.loadout.change_count,
            "movementChangeCount": self.movement.change_count,
            "characterPresent": player.character is not None,
        }

    def handle_keybind(self, player: MockPlayer, key: str) -> str:
        if key == self.loadout.keybind:
            self.toggle_loadout(player)
            return "loadout"
        if key == self.movement.keybind:
            self.toggle_movement(player)
            return "movement"
        return "none"

    def cleanup(self) -> dict[str, Any]:
        self.loadout.enabled = False
        self.movement.enabled = False
        self.connection_count = 0
        return {
            "alive": False,
            "loadoutEnabled": self.loadout.enabled,
            "movementEnabled": self.movement.enabled,
            "connectionCount": self.connection_count,
        }
