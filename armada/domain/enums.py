from enum import Enum

class CellType(Enum):
    Bridge = "bridge"
    Weapon = "weapon"
    Armor  = "armor"
    Supply = "supply"
    Hull   = "hull"

class ModuleType(Enum):
    Torpedo          = "torpedo"
    BallisticMissile = "ballistic_missile"
    Mortar           = "mortar"
    Bomber           = "bomber"
    AaGun            = "aa_gun"

class Direction(Enum):
    North = "N"
    East  = "E"
    South = "S"
    West  = "W"

class ShipState(Enum):
    Active = "active"
    Dying  = "dying"
    Dead   = "dead"

class TerrainHeight(Enum):
    DeepSea      = 0
    ShallowWater = 1
    Land         = 2
    Mountain     = 3

class CellObjectType(Enum):
    Port    = "port"
    OilRig  = "oil_rig"
    Mine    = "mine"
    NpcShip = "npc_ship"

class CellEffectType(Enum):
    Ice   = "ice"
    Storm = "storm"
    Fog   = "fog"
    Fire  = "fire"

class MarkerType(Enum):
    Hit             = "hit"
    Miss            = "miss"
    AmmoLoss        = "ammo_loss"
    ObjectDetection = "object_detection"
    EffectTrace     = "effect_trace"
